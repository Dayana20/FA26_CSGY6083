"""Health check endpoints: GET /health and GET /health/mysql."""

import mysql.connector
from fastapi import APIRouter, HTTPException

from app.database.mysql import get_connection

# All endpoints in this module live under /health.
router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("")
def health_check() -> dict[str, str]:
    """Confirm the API is running."""
    return {
        "status": "ok"
    }


@router.get("/mysql")
def mysql_health_check() -> dict[str, str]:
    """Confirm the API can connect to MySQL and has a database selected.

    Returns {"status": "ok", "database": <name>} on success, or HTTP 503 if
    MySQL can't be reached, the .env settings are missing or invalid, or no
    database is selected.
    """
    try:
        # Connect with the .env settings and ask which database is in use.
        # The `with` block closes the cursor and connection, even after an error.
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            row = cursor.fetchone()
    except (mysql.connector.Error, KeyError, ValueError) as exc:
        # mysql.connector.Error: MySQL unreachable or login rejected.
        # KeyError: a required MYSQL_* setting is missing from .env.
        # ValueError: MYSQL_PORT isn't a number.
        raise HTTPException(
            status_code=503,
            detail="MySQL database unavailable",
        ) from exc

    database_name = row[0] if row else None
    if database_name is None:
        raise HTTPException(
            status_code=503,
            detail="No MySQL database selected",
        )
    return {"status": "ok", "database": database_name}
