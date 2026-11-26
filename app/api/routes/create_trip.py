"""Cruise-trip API endpoints."""

from datetime import date
from typing import Dict, Union

import mysql.connector
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.database.mysql import get_connection

router = APIRouter(tags=["trips"])


class TripCreate(BaseModel):
    start_date: date = Field(description="Trip departure date")
    end_date: date = Field(description="Trip return date, after start_date")
    ship_id: int = Field(gt=0, description="ID of an existing cruise ship")


@router.post("/create_trip", status_code=status.HTTP_201_CREATED)
def create_trip(trip: TripCreate):
    """Create a trip record for an existing cruise ship."""
    if trip.end_date <= trip.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be after start_date",
        )

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO ADH_TRIP (START_DATE, END_DATE, SHIP_ID)
            VALUES (%s, %s, %s)
            """,
            (trip.start_date, trip.end_date, trip.ship_id),
        )
        trip_id = cursor.lastrowid
        connection.commit()
    except mysql.connector.IntegrityError as exc:
        if connection is not None:
            connection.rollback()
        if exc.errno == 1452:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="ship_id does not refer to an existing cruise ship",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trip conflicts with a database constraint",
        ) from exc
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create trip in MySQL",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()

    return {
        "trip_id": trip_id,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "ship_id": trip.ship_id,
    }
