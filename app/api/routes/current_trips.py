"""Get current cruise-trip API endpoint."""

from typing import Dict, Union

import mysql.connector
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.database.mysql import get_connection

router = APIRouter(tags=["trips"])


@router.get("/current_trips")
def get_current_trips():
    """Get all current cruise trips."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT TRIP_ID, START_DATE, END_DATE, SHIP_ID
            FROM ADH_TRIP
            ORDER BY TRIP_ID
            """
        )
        trips = cursor.fetchall()
        if not trips:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No current cruise trips found",
            )
        return {"trips": trips}
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not fetch current cruise trips from MySQL",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()
