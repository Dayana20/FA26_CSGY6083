"""Delete trip API endpoint."""

import logging
from dataclasses import Field
from datetime import date
from typing import Dict, Union
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

import mysql.connector

from app.database.mysql import get_connection

router = APIRouter(tags=["trips"])
logger = logging.getLogger("uvicorn.error")

@router.delete("/delete_trip/{trip_id}", status_code=status.HTTP_200_OK)
def delete_trip(trip_id: int):
    """Delete a cruise trip record."""
    connection = None
    cursor = None
    logger.info("Delete trip request received trip_id=%s", trip_id)
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            DELETE FROM ADH_TRIP
            WHERE TRIP_ID = %s
            """,
            (trip_id,),
        )
        if cursor.rowcount == 0:
            logger.warning("Delete trip rejected: trip_id=%s not found", trip_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cruise trip with ID {trip_id} not found",
            )
        connection.commit()
        logger.info(
            "Committed trip deletion trip_id=%s (its port stops were cascade-deleted)",
            trip_id,
        )
    except mysql.connector.IntegrityError as exc:
        logger.exception("Delete trip blocked by constraints trip_id=%s", trip_id)
        if connection is not None:
            connection.rollback()
            logger.info("Rolled back trip deletion trip_id=%s", trip_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cruise trip cannot be deleted due to database constraints",
        ) from exc
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        logger.exception("Database error deleting trip trip_id=%s", trip_id)
        if connection is not None:
            connection.rollback()
            logger.info("Rolled back trip deletion trip_id=%s", trip_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not delete cruise trip from MySQL",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()

    return {"message": f"Cruise trip with ID {trip_id} deleted successfully"}