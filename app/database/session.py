"""Transactional and prepared-statement helpers built on app.database.mysql."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.database.mysql import get_connection


def decode_db_value(value: Any) -> Any:
    """Decode bytes/bytearray returned by MySQL prepared cursors to str."""
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8")
    return value


@contextmanager
def db_cursor() -> Iterator[Any]:
    """Open a MySQL connection with a server-side prepared cursor for read queries."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(prepared=True)
        yield cursor
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()


@contextmanager
def db_transaction() -> Iterator[Any]:
    """Open a MySQL transaction with a prepared cursor; commit on success, rollback on error."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        connection.autocommit = False
        cursor = connection.cursor(prepared=True)
        yield cursor
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if connection is not None:
                connection.close()
