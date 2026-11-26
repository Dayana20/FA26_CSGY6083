"""Delete ship API endpoint."""

from dataclasses import Field
from datetime import date
from typing import Dict, Union
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

import mysql.connector

from app.database.mysql import get_connection

router = APIRouter(tags=["cruise ships"])


@router.delete("/delete_cruise/{ship_id}", status_code=status.HTTP_200_OK)
def delete_cruise(ship_id: int):
    """Delete a cruise ship record."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            DELETE FROM ADH_CRUISE_SHIP
            WHERE SHIP_ID = %s
            """,
            (ship_id,),
        )
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cruise ship with ID {ship_id} not found",
            )
        connection.commit()
    except mysql.connector.IntegrityError as exc:
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cruise ship cannot be deleted due to database constraints",
        ) from exc
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not delete cruise ship from MySQL",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()

    return {"message": f"Cruise ship with ID {ship_id} deleted successfully"}