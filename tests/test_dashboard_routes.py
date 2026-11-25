from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_user_dashboard_page():
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Your trips" in response.text
    assert "Sign Out" in response.text


def test_admin_dashboard_page():
    response = client.get("/admin/dashboard")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Admin dashboard" in response.text
    assert "Manage bookings" in response.text


def test_admin_cruise_trip_management_page():
    response = client.get("/admin/cruise-trips")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Create cruise itineraries" in response.text
    assert "Start date" in response.text
    assert "End date" in response.text
    assert "Itinerary" in response.text
    assert "reset when this page is refreshed" in response.text
