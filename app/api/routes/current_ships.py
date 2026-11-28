"""Get cruise ships available for trip creation."""

import mysql.connector
from fastapi import APIRouter, HTTPException, status

from app.database.mysql import get_connection

router = APIRouter(tags=["cruise ships"])

@router.get("/get_cruises")
def get_current_ships():
    """Return all cruise ships available in the database."""
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT SHIP_ID, SHIP_NAME, NO_OF_FLOORS
            FROM ADH_CRUISE_SHIP
            ORDER BY SHIP_ID
            """
        )
        ships = cursor.fetchall()
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not retrieve cruise ships from MySQL",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()

    return {"cruises": ships}