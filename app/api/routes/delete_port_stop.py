"""Delete a port stop from a trip."""

import logging

import mysql.connector
from fastapi import APIRouter, HTTPException, status

from app.database.mysql import get_connection

router = APIRouter(tags=["port stops"])
logger = logging.getLogger("uvicorn.error")


@router.delete("/delete_port_stop/{trip_id}/{stop_no}", status_code=status.HTTP_200_OK)
def delete_port_stop(trip_id: int, stop_no: int):
    """Delete the stop identified by its trip ID and stop number."""
    connection = None
    cursor = None
    logger.info("Delete port stop request received trip_id=%s stop_no=%s", trip_id, stop_no)
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            DELETE FROM ADH_PORT_STOP
            WHERE TRIP_ID = %s AND STOP_NO = %s
            """,
            (trip_id, stop_no),
        )
        if cursor.rowcount == 0:
            logger.warning(
                "Delete port stop rejected: trip_id=%s stop_no=%s not found",
                trip_id,
                stop_no,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Port stop {stop_no} for trip {trip_id} not found",
            )
        connection.commit()
        logger.info("Committed port stop deletion trip_id=%s stop_no=%s", trip_id, stop_no)
    except mysql.connector.IntegrityError as exc:
        logger.exception(
            "Delete port stop blocked by constraints trip_id=%s stop_no=%s", trip_id, stop_no
        )
        if connection is not None:
            connection.rollback()
            logger.info("Rolled back port stop deletion trip_id=%s stop_no=%s", trip_id, stop_no)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Port stop cannot be deleted due to database constraints",
        ) from exc
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        logger.exception(
            "Database error deleting port stop trip_id=%s stop_no=%s", trip_id, stop_no
        )
        if connection is not None:
            connection.rollback()
            logger.info("Rolled back port stop deletion trip_id=%s stop_no=%s", trip_id, stop_no)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not delete port stop from MySQL",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()

    return {"message": f"Port stop {stop_no} for trip {trip_id} deleted successfully"}
