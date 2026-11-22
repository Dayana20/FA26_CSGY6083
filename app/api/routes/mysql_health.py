import mysql.connector
from fastapi import APIRouter, HTTPException

from app.database.mysql import get_connection

router = APIRouter()


@router.get("/mysql")
def mysql_health_check():
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        row = cursor.fetchone()
        database_name = row[0] if row else None
        if database_name is None:
            raise HTTPException(
                status_code=503,
                detail="No MySQL database selected",
            )
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="MySQL database unavailable",
        ) from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()

    return {"status": "ok", "database": database_name}
