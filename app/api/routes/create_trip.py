"""Cruise-trip API endpoints."""

from datetime import date
import logging

import mysql.connector
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.database.mysql import get_connection
from app.api.routes.create_port_stop import PortStopDetails

router = APIRouter(tags=["trips"])
logger = logging.getLogger("uvicorn.error")


class TripCreate(BaseModel):
    start_date: date = Field(description="Trip departure date")
    end_date: date = Field(description="Trip return date, after start_date")
    ship_id: int = Field(gt=0, description="ID of an existing cruise ship")
    port_stops: list[PortStopDetails] = Field(default_factory=list)


@router.post("/create_trip", status_code=status.HTTP_201_CREATED)
def create_trip(trip: TripCreate):
    """Create a trip record for an existing cruise ship."""
    logger.info(
        "Creating trip ship_id=%s start_date=%s end_date=%s port_stop_count=%s",
        trip.ship_id, trip.start_date, trip.end_date, len(trip.port_stops),
    )
    if trip.end_date <= trip.start_date:
        logger.warning("Trip creation rejected: end date must be after start date")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be after start_date",
        )

    previous_departure = None
    for index, stop in enumerate(trip.port_stops, start=1):
        if (
            stop.stop_no != index
            or stop.pend_date <= stop.pstart_date
            or stop.pstart_date.date() < trip.start_date
            or stop.pend_date.date() > trip.end_date
            or (previous_departure is not None and stop.pstart_date < previous_departure)
        ):
            logger.warning(
                "Trip creation rejected: invalid port stop stop_no=%s port_id=%s arrival=%s departure=%s",
                stop.stop_no, stop.port_id, stop.pstart_date, stop.pend_date,
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Port stops must be numbered in order, within the trip dates, and follow the previous stop",
            )
        previous_departure = stop.pend_date

    connection = None
    cursor = None
    inserting_stops = False
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
        inserting_stops = True
        for stop in trip.port_stops:
            logger.info(
                "Inserting port stop trip_id=%s stop_no=%s port_id=%s arrival=%s departure=%s",
                trip_id, stop.stop_no, stop.port_id, stop.pstart_date, stop.pend_date,
            )
            cursor.execute(
                """
                INSERT INTO ADH_PORT_STOP
                    (STOP_NO, PSTART_DATE, PEND_DATE, TRIP_ID, PORT_ID)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (stop.stop_no, stop.pstart_date, stop.pend_date, trip_id, stop.port_id),
            )
        connection.commit()
        logger.info(
            "Committed trip trip_id=%s port_stop_count=%s",
            trip_id, len(trip.port_stops),
        )
    except mysql.connector.IntegrityError as exc:
        logger.exception("Trip creation failed due to a database constraint")
        if connection is not None:
            connection.rollback()
            logger.info("Rolled back trip creation")
        if exc.errno == 1452:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "port_id does not refer to an existing port"
                    if inserting_stops
                    else "ship_id does not refer to an existing cruise ship"
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trip conflicts with a database constraint",
        ) from exc
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        logger.exception("Trip creation failed due to a database or configuration error")
        if connection is not None:
            connection.rollback()
            logger.info("Rolled back trip creation")
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
