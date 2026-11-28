"""Create a port stop for a trip."""

from datetime import datetime

import mysql.connector
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.database.mysql import get_connection

router = APIRouter(tags=["port stops"])


class PortStopCreate(BaseModel):
    stop_no: int = Field(ge=1, le=32767)
    pstart_date: datetime
    pend_date: datetime
    trip_id: int = Field(gt=0, le=2147483647)
    port_id: int = Field(gt=0, le=2147483647)

    @field_validator("pstart_date", "pend_date")
    @classmethod
    def validate_datetime(cls, value: datetime) -> datetime:
        if value.utcoffset() is not None:
            raise ValueError("Port stop dates must not include a time zone")
        if value.microsecond:
            raise ValueError("Port stop dates must not include fractional seconds")
        return value


@router.post("/create_port_stop", status_code=status.HTTP_201_CREATED)
def create_port_stop(port_stop: PortStopCreate):
    """Create a port stop using its trip ID and stop number."""
    if port_stop.pend_date < port_stop.pstart_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pend_date must be on or after pstart_date",
        )

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO ADH_PORT_STOP
                (STOP_NO, PSTART_DATE, PEND_DATE, TRIP_ID, PORT_ID)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                port_stop.stop_no,
                port_stop.pstart_date,
                port_stop.pend_date,
                port_stop.trip_id,
                port_stop.port_id,
            ),
        )
        connection.commit()
    except mysql.connector.IntegrityError as exc:
        if connection is not None:
            connection.rollback()
        if exc.errno == 1452:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="trip_id or port_id does not refer to an existing record",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Port stop conflicts with a database constraint",
        ) from exc
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create port stop in MySQL",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()

    return {"trip_id": port_stop.trip_id, "stop_no": port_stop.stop_no}
