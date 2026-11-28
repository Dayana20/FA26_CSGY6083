"""Create a port stop for a trip."""

from datetime import datetime
import logging

import mysql.connector
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.database.mysql import get_connection

router = APIRouter(tags=["port stops"])
logger = logging.getLogger("uvicorn.error")


class PortStopDetails(BaseModel):
    stop_no: int = Field(ge=1, le=32767)
    pstart_date: datetime
    pend_date: datetime
    port_id: int = Field(gt=0, le=2147483647)

    @field_validator("pstart_date", "pend_date")
    @classmethod
    def validate_datetime(cls, value: datetime) -> datetime:
        if value.utcoffset() is not None:
            raise ValueError("Port stop dates must not include a time zone")
        if value.microsecond:
            raise ValueError("Port stop dates must not include fractional seconds")
        return value


class PortStopCreate(PortStopDetails):
    trip_id: int = Field(gt=0, le=2147483647)


@router.post("/create_port_stop", status_code=status.HTTP_201_CREATED)
def create_port_stop(port_stop: PortStopCreate):
    """Create a port stop using its trip ID and stop number."""
    logger.info(
        "Creating port stop trip_id=%s stop_no=%s port_id=%s arrival=%s departure=%s",
        port_stop.trip_id, port_stop.stop_no, port_stop.port_id,
        port_stop.pstart_date, port_stop.pend_date,
    )
    if port_stop.pend_date < port_stop.pstart_date:
        logger.warning(
            "Port stop creation rejected: departure before arrival trip_id=%s stop_no=%s",
            port_stop.trip_id, port_stop.stop_no,
        )
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
        logger.info(
            "Committed port stop trip_id=%s stop_no=%s port_id=%s",
            port_stop.trip_id, port_stop.stop_no, port_stop.port_id,
        )
    except mysql.connector.IntegrityError as exc:
        logger.exception(
            "Port stop creation failed due to a database constraint trip_id=%s stop_no=%s",
            port_stop.trip_id, port_stop.stop_no,
        )
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
        logger.exception(
            "Port stop creation failed due to a database or configuration error trip_id=%s stop_no=%s",
            port_stop.trip_id, port_stop.stop_no,
        )
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
