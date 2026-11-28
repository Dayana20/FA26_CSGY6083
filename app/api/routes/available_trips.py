"""Available-trips endpoint: GET /available_trips.

Public: lists the trips anyone can browse on the Book a cruise page.
"""

import mysql.connector
from fastapi import APIRouter, HTTPException, status

from app.database.trips import get_available_trips

router = APIRouter(tags=["trips"])


@router.get("/available_trips")
def list_available_trips():
    """Return every trip starting today or later, with its ship and port stops.

    Returns {"trips": [...]}, an empty list when nothing is scheduled, or
    HTTP 503 if MySQL can't be reached.
    """
    try:
        trips = get_available_trips()
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        # mysql.connector.Error: MySQL unreachable or the query failed.
        # KeyError / ValueError: a MYSQL_* setting is missing or invalid.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not retrieve available trips from MySQL",
        ) from exc

    return {"trips": trips}
