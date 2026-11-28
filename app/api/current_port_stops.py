"""Retrieve current port stops from the database."""

import mysql.connector
from fastapi import APIRouter, HTTPException, status

from app.database.mysql import get_connection

router = APIRouter(tags=["port stops"])


@router.get("/current_port_stops")
def get_current_port_stops():
    """Return all port stops in the database."""
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT STOP_NO, PSTART_DATE, PEND_DATE, TRIP_ID, PORT_ID
            FROM ADH_PORT_STOP
            ORDER BY TRIP_ID, STOP_NO
            """
        )
        port_stops = cursor.fetchall()
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not retrieve port stops from MySQL",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()

    return {"port_stops": port_stops}