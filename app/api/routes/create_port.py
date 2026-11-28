"""Create a new port in the database."""

import logging
from typing import Optional

import mysql.connector
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.database.mysql import get_connection

router = APIRouter(tags=["ports"])
logger = logging.getLogger("uvicorn.error")


class PortCreate(BaseModel):
    port_name: str = Field(max_length=100, pattern=r"\S")
    street: str = Field(max_length=150)
    city: str = Field(max_length=100)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    zipcode: Optional[str] = Field(default=None, min_length=5, max_length=5, pattern=r"^[0-9]{5}$")
    country: str = Field(max_length=30)
    nearest_airport: str = Field(max_length=50)
    parking_capacity: Optional[int] = Field(default=None, ge=0, le=999)


@router.post("/create_port", status_code=status.HTTP_201_CREATED)
def create_port(port: PortCreate):
    """Create a port record."""
    logger.info("Creating port port_name=%r", port.port_name)
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO ADH_PORT
                (PORT_NAME, STREET, CITY, STATE, ZIPCODE, COUNTRY,
                 NEAREST_AIRPORT, PARKING_CAPACITY)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                port.port_name,
                port.street,
                port.city,
                port.state,
                port.zipcode,
                port.country,
                port.nearest_airport,
                port.parking_capacity,
            ),
        )
        port_id = cursor.lastrowid
        connection.commit()
        logger.info("Committed port port_id=%s port_name=%r", port_id, port.port_name)
    except mysql.connector.IntegrityError as exc:
        logger.exception("Port creation failed due to a database constraint")
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Port conflicts with a database constraint",
        ) from exc
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        logger.exception("Port creation failed due to a database or configuration error")
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create port in MySQL",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()

    return {"port_id": port_id}