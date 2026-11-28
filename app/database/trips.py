"""Database queries for cruise trips.

The API calls these functions instead of writing SQL itself, so every trip
query lives in one place.
"""

from app.database.mysql import get_connection


# =============================================================================
# Queries
# =============================================================================

# Trips that haven't departed yet, with their ship. CURDATE() is "today" on the
# MySQL server, so a trip leaving today still counts as available.
AVAILABLE_TRIPS_SQL = """
    SELECT
        t.TRIP_ID,
        t.START_DATE,
        t.END_DATE,
        DATEDIFF(t.END_DATE, t.START_DATE) AS NIGHTS,
        s.SHIP_ID,
        s.SHIP_NAME
    FROM ADH_TRIP t
    JOIN ADH_CRUISE_SHIP s ON s.SHIP_ID = t.SHIP_ID
    WHERE t.START_DATE >= CURDATE()
    ORDER BY t.START_DATE, t.TRIP_ID
"""

# The port stops of the given trips, in sailing order. The {placeholders} are
# filled with one %s per trip ID, so the IDs are still passed as parameters.
PORT_STOPS_SQL = """
    SELECT
        ps.TRIP_ID,
        ps.STOP_NO,
        ps.PSTART_DATE,
        ps.PEND_DATE,
        p.PORT_ID,
        p.PORT_NAME,
        p.CITY,
        p.COUNTRY
    FROM ADH_PORT_STOP ps
    JOIN ADH_PORT p ON p.PORT_ID = ps.PORT_ID
    WHERE ps.TRIP_ID IN ({placeholders})
    ORDER BY ps.TRIP_ID, ps.STOP_NO
"""


# =============================================================================
# Functions
# =============================================================================

def get_available_trips() -> list[dict]:
    """Return every trip starting today or later, soonest first.

    Each trip is a dict with TRIP_ID, START_DATE, END_DATE, NIGHTS, SHIP_ID,
    SHIP_NAME and PORT_STOPS (its stops in order, each with STOP_NO,
    PSTART_DATE, PEND_DATE, PORT_ID, PORT_NAME, CITY and COUNTRY). Returns an
    empty list when there are no upcoming trips. MySQL errors are raised to the
    caller.
    """
    with get_connection() as connection, connection.cursor(dictionary=True) as cursor:
        # 1. The trips themselves.
        cursor.execute(AVAILABLE_TRIPS_SQL)
        trips = cursor.fetchall()
        if not trips:
            return []

        # 2. Their port stops, fetched in one query rather than one per trip.
        trip_ids = [trip["TRIP_ID"] for trip in trips]
        placeholders = ", ".join(["%s"] * len(trip_ids))
        cursor.execute(PORT_STOPS_SQL.format(placeholders=placeholders), trip_ids)
        stops = cursor.fetchall()

    # 3. Attach each stop to its trip (stops arrive in sailing order).
    stops_by_trip: dict[int, list[dict]] = {trip_id: [] for trip_id in trip_ids}
    for stop in stops:
        stops_by_trip[stop.pop("TRIP_ID")].append(stop)
    for trip in trips:
        trip["PORT_STOPS"] = stops_by_trip[trip["TRIP_ID"]]
    return trips
