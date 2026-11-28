"""Unit tests for prepared statements, transaction rollbacks, and safe schema reconciliation."""

from unittest.mock import MagicMock, patch

import mysql.connector
import pytest

from app.core.security import hash_password
from app.database.schema import SchemaConflictError, initialize_auth_schema
from app.repositories.user_repository import (
    DuplicateEmailError,
    get_user_by_email,
    register_customer,
)


def _build_mock_connection():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


@patch("app.database.session.get_connection")
def test_register_customer_uses_prepared_cursor_and_commits(mock_get_connection):
    mock_conn, mock_cursor = _build_mock_connection()
    mock_get_connection.return_value = mock_conn
    mock_cursor.fetchone.return_value = None
    type(mock_cursor).lastrowid = property(
        lambda self: getattr(self, "_ids", [42, 7]).pop(0)
    )
    mock_cursor._ids = [42, 7]

    user = register_customer(
        first_name="Grace",
        last_name="Hopper",
        email="grace@example.com",
        phone="212-555-0100",
        address="100 Ocean Ave, NY",
        password_hash=hash_password("ValidPass123!"),
    )

    assert user.customer_id == 42
    assert user.user_id == 7
    assert user.role == "C"
    mock_conn.cursor.assert_called_once_with(prepared=True)
    assert mock_conn.autocommit is False
    mock_conn.commit.assert_called_once()
    mock_conn.rollback.assert_not_called()
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()


@patch("app.database.session.get_connection")
def test_register_customer_rolls_back_when_adh_user_insert_fails(mock_get_connection):
    mock_conn, mock_cursor = _build_mock_connection()
    mock_get_connection.return_value = mock_conn
    mock_cursor.fetchone.return_value = None
    mock_cursor.lastrowid = 101

    call_count = {"n": 0}

    def execute_side_effect(sql, params=None):
        call_count["n"] += 1
        if call_count["n"] == 3:
            raise mysql.connector.DatabaseError("Simulated ADH_USER insert failure")

    mock_cursor.execute.side_effect = execute_side_effect

    with pytest.raises(mysql.connector.DatabaseError, match="Simulated ADH_USER"):
        register_customer(
            first_name="Alan",
            last_name="Turing",
            email="alan@example.com",
            phone="212-555-0101",
            address="10 Bletchley Park",
            password_hash=hash_password("ValidPass123!"),
        )

    mock_conn.cursor.assert_called_once_with(prepared=True)
    mock_conn.commit.assert_not_called()
    mock_conn.rollback.assert_called_once()
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()


@patch("app.database.session.get_connection")
def test_register_customer_rolls_back_on_duplicate_email_integrity_error(
    mock_get_connection,
):
    mock_conn, mock_cursor = _build_mock_connection()
    mock_get_connection.return_value = mock_conn
    mock_cursor.fetchone.return_value = None
    mock_cursor.lastrowid = 55

    call_count = {"n": 0}

    def execute_side_effect(sql, params=None):
        call_count["n"] += 1
        if call_count["n"] == 3:
            raise mysql.connector.IntegrityError(msg="Duplicate entry", errno=1062)

    mock_cursor.execute.side_effect = execute_side_effect

    with pytest.raises(DuplicateEmailError):
        register_customer(
            first_name="Race",
            last_name="Condition",
            email="race@example.com",
            phone="212-555-0199",
            address="1 Harbor Way",
            password_hash=hash_password("ValidPass123!"),
        )

    mock_conn.commit.assert_not_called()
    mock_conn.rollback.assert_called_once()


@patch("app.database.session.get_connection")
def test_sql_injection_payload_passed_as_bound_parameter(mock_get_connection):
    mock_conn, mock_cursor = _build_mock_connection()
    mock_get_connection.return_value = mock_conn
    mock_cursor.fetchone.return_value = None

    payload = "' OR '1'='1' -- "
    assert get_user_by_email(payload) is None

    mock_conn.cursor.assert_called_once_with(prepared=True)
    executed_sql, executed_params = mock_cursor.execute.call_args.args
    assert "%s" in executed_sql
    assert payload not in executed_sql
    assert executed_params == (payload.strip().lower(),)


def test_initialize_auth_schema_creates_missing_tables():
    mock_conn = MagicMock()
    inspect_cursor = MagicMock()
    ddl_cursor = MagicMock()
    mock_conn.cursor.side_effect = [inspect_cursor, ddl_cursor]

    # SELECT DATABASE(), engine for ADH_CUSTOMER (None), engine for ADH_USER (None)
    inspect_cursor.fetchone.side_effect = [("da2410hc4288as23663",), None, None]

    report, created = initialize_auth_schema(connection=mock_conn)

    assert report.database == "da2410hc4288as23663"
    assert report.is_compatible is True
    assert created == ["ADH_CUSTOMER", "ADH_USER"]
    assert ddl_cursor.execute.call_count == 2
    mock_conn.commit.assert_called_once()


def test_initialize_auth_schema_stops_on_incompatible_existing_table():
    mock_conn = MagicMock()
    inspect_cursor = MagicMock()
    mock_conn.cursor.return_value = inspect_cursor

    # SELECT DATABASE(), engine for ADH_CUSTOMER (MyISAM - incompatible), engine for ADH_USER (None)
    inspect_cursor.fetchone.side_effect = [("da2410hc4288as23663",), ("MyISAM",), None]
    # Existing ADH_CUSTOMER missing required columns
    inspect_cursor.fetchall.return_value = [
        ("CUSTOMER_ID", "int", "NO", None, "PRI", "auto_increment"),
        ("FULL_NAME", "varchar", "NO", None, "", ""),
    ]

    with pytest.raises(SchemaConflictError) as exc_info:
        initialize_auth_schema(connection=mock_conn)

    assert any("MyISAM" in conflict for conflict in exc_info.value.conflicts)
    assert any("missing required columns" in conflict for conflict in exc_info.value.conflicts)
    mock_conn.commit.assert_not_called()
