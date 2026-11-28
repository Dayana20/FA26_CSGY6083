"""Delete a port stop from a trip."""

import mysql.connector
from fastapi import APIRouter, HTTPException, status

from app.database.mysql import get_connection

router = APIRouter(tags=["port stops"])


@router.delete("/delete_port_stop/{trip_id}/{stop_no}", status_code=status.HTTP_200_OK)
def delete_port_stop(trip_id: int, stop_no: int):
    """Delete the stop identified by its trip ID and stop number."""
    connection = None
    cursor = None
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Port stop {stop_no} for trip {trip_id} not found",
            )
        connection.commit()
    except mysql.connector.IntegrityError as exc:
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Port stop cannot be deleted due to database constraints",
        ) from exc
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        if connection is not None:
            connection.rollback()
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
