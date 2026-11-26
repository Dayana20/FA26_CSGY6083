"""Create ship API endpoint."""

from dataclasses import Field
from datetime import date
from typing import Dict, Union
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field


import mysql.connector


from app.database.mysql import get_connection

router = APIRouter(tags=["cruise ships"])

class CruiseCreate(BaseModel):
    ship_name: str = Field(description="Name of the cruise ship")
    no_of_floors: int = Field(gt=0, description="Number of floors on the cruise ship")

@router.post("/create_cruise", status_code=status.HTTP_201_CREATED)
def create_cruise(cruise: CruiseCreate):
    """Create a cruise ship record."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO ADH_CRUISE_SHIP (SHIP_NAME, NO_OF_FLOORS)
            VALUES (%s, %s)
            """,
            (cruise.ship_name, cruise.no_of_floors),
        )
        ship_id = cursor.lastrowid
        connection.commit()
    except mysql.connector.IntegrityError as exc:
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cruise ship conflicts with a database constraint",
        ) from exc
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create cruise ship in MySQL",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()

    return {"ship_id": ship_id}