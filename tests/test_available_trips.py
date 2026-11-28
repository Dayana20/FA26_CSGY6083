"""Tests for the Book a cruise flow: get_available_trips(), GET /available_trips
and the /book-cruise page.

MySQL itself is never contacted: get_connection is replaced with a mock, so
these tests run without XAMPP.
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import mysql.connector
from fastapi.testclient import TestClient

from app.database.trips import get_available_trips
from main import app


client = TestClient(app)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def fake_connection(*results):
    """A mock connection whose cursor returns each of results in turn from fetchall()."""
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.side_effect = list(results)
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value = cursor
    return connection, cursor


TRIP_ROWS = [
    {"TRIP_ID": 1, "START_DATE": date(2027, 1, 10), "END_DATE": date(2027, 1, 17),
     "NIGHTS": 7, "SHIP_ID": 1, "SHIP_NAME": "Ocean Waves"},
    {"TRIP_ID": 3, "START_DATE": date(2027, 2, 7), "END_DATE": date(2027, 2, 12),
     "NIGHTS": 5, "SHIP_ID": 3, "SHIP_NAME": "Starry Night"},
]
STOP_ROWS = [
    {"TRIP_ID": 1, "STOP_NO": 1, "PSTART_DATE": datetime(2027, 1, 10, 11), "PEND_DATE": datetime(2027, 1, 10, 16),
     "PORT_ID": 1, "PORT_NAME": "PortMiami", "CITY": "Miami", "COUNTRY": "USA"},
    {"TRIP_ID": 1, "STOP_NO": 2, "PSTART_DATE": datetime(2027, 1, 12, 8), "PEND_DATE": datetime(2027, 1, 12, 17),
     "PORT_ID": 8, "PORT_NAME": "Port of San Juan", "CITY": "San Juan", "COUNTRY": "Puerto Rico"},
]


# -----------------------------------------------------------------------------
# get_available_trips()
# -----------------------------------------------------------------------------

def test_query_only_returns_trips_starting_today_or_later():
    connection, cursor = fake_connection([], [])
    with patch("app.database.trips.get_connection", return_value=connection):
        get_available_trips()
    trips_sql = cursor.execute.call_args_list[0].args[0]
    assert "START_DATE >= CURDATE()" in trips_sql
    assert "ORDER BY t.START_DATE" in trips_sql


def test_trips_come_back_with_their_port_stops():
    connection, cursor = fake_connection([dict(r) for r in TRIP_ROWS], [dict(r) for r in STOP_ROWS])
    with patch("app.database.trips.get_connection", return_value=connection):
        trips = get_available_trips()

    assert [t["TRIP_ID"] for t in trips] == [1, 3]
    assert [s["PORT_NAME"] for s in trips[0]["PORT_STOPS"]] == ["PortMiami", "Port of San Juan"]
    assert "TRIP_ID" not in trips[0]["PORT_STOPS"][0]
    assert trips[1]["PORT_STOPS"] == []
    # The stops query passes the trip IDs as parameters, not pasted into the SQL.
    stops_sql, params = cursor.execute.call_args_list[1].args
    assert "IN (%s, %s)" in stops_sql
    assert params == [1, 3]


def test_no_upcoming_trips_skips_the_stops_query():
    connection, cursor = fake_connection([])
    with patch("app.database.trips.get_connection", return_value=connection):
        assert get_available_trips() == []
    assert cursor.execute.call_count == 1


# -----------------------------------------------------------------------------
# GET /available_trips
# -----------------------------------------------------------------------------

def test_endpoint_returns_trips_as_json():
    trips = [dict(TRIP_ROWS[0], PORT_STOPS=[])]
    with patch("app.api.routes.available_trips.get_available_trips", return_value=trips):
        response = client.get("/available_trips")
    assert response.status_code == 200
    assert response.json()["trips"][0]["SHIP_NAME"] == "Ocean Waves"
    assert response.json()["trips"][0]["START_DATE"] == "2027-01-10"


def test_endpoint_returns_an_empty_list_when_nothing_is_scheduled():
    with patch("app.api.routes.available_trips.get_available_trips", return_value=[]):
        response = client.get("/available_trips")
    assert response.status_code == 200
    assert response.json() == {"trips": []}


def test_endpoint_returns_503_when_mysql_is_unavailable():
    error = mysql.connector.Error("connection refused")
    with patch("app.api.routes.available_trips.get_available_trips", side_effect=error):
        response = client.get("/available_trips")
    assert response.status_code == 503


# -----------------------------------------------------------------------------
# /book-cruise page
# -----------------------------------------------------------------------------

def test_book_cruise_page():
    response = client.get("/book-cruise")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Upcoming cruises" in response.text
    assert "book-cruise.js" in response.text


def test_home_page_links_to_book_cruise():
    response = client.get("/")
    assert 'href="/book-cruise"' in response.text
