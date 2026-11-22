from unittest.mock import patch

import mysql.connector
import pytest

from app.database.mysql import get_connection


@pytest.fixture
def mysql_environment(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("MYSQL_PORT", "3306")
    monkeypatch.setenv("MYSQL_USER", "test_user")
    monkeypatch.setenv("MYSQL_PASSWORD", "test_password")
    monkeypatch.setenv("MYSQL_DATABASE", "test_db")


@patch("app.database.mysql.mysql.connector.connect")
def test_get_connection_uses_environment_settings(mock_connect, mysql_environment):
    mock_connect.return_value = object()
    assert get_connection() is mock_connect.return_value
    mock_connect.assert_called_once_with(
        host="127.0.0.1",
        port=3306,
        user="test_user",
        password="test_password",
        database="test_db",
    )


@patch("app.database.mysql.mysql.connector.connect")
def test_get_connection_raises_when_mysql_is_unavailable(mock_connect, mysql_environment):
    mock_connect.side_effect = mysql.connector.Error("connection refused")
    with pytest.raises(mysql.connector.Error, match="connection refused"):
        get_connection()
