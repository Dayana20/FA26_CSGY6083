"""Get all ports currently available."""

import mysql.connector
from fastapi import APIRouter, HTTPException, status

from app.database.mysql import get_connection

router = APIRouter(tags=["ports"])


@router.get("/current_ports")
def get_current_ports():
    """Return all ports in the database."""
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT PORT_ID, PORT_NAME, STREET, CITY, STATE, ZIPCODE, COUNTRY,
                   NEAREST_AIRPORT, PARKING_CAPACITY
            FROM ADH_PORT
            ORDER BY PORT_ID
            """
        )
        ports = cursor.fetchall()
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not retrieve ports from MySQL",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()

    return {"ports": ports}
