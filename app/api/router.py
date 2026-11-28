"""Collects every API route module into one router for main.py.

To add a new group of endpoints, create a module in app/api/routes/, import
its router here, and include it below.
"""

from fastapi import APIRouter
from app.api.current_port_stops import router as current_port_stops_router
from app.api.routes.health import router as health_router
from app.api.routes.home import router as home_router
from app.api.routes.create_trip import router as trips_router
from app.api.routes.current_trips import router as current_trips_router
from app.api.routes.available_trips import router as available_trips_router
from app.api.routes.delete_trip import router as delete_trip_router
from app.api.routes.current_ships import router as current_ships_router
from app.api.routes.current_ports import router as current_ports_router
from app.api.routes.create_port import router as create_port_router
from app.api.routes.delete_port import router as delete_port_router
from app.api.routes.create_port_stop import router as create_port_stop_router
from app.api.routes.delete_port_stop import router as delete_port_stop_router
from app.api.routes.create_ship import router as create_ship_router
from app.api.routes.delete_ship import router as delete_ship_router

# The router main.py registers with the app.
api_router = APIRouter()

# Register page routes, health checks, and trip API routes.
api_router.include_router(home_router)
api_router.include_router(health_router)

api_router.include_router(trips_router)
api_router.include_router(current_trips_router)
api_router.include_router(available_trips_router)
api_router.include_router(delete_trip_router)

api_router.include_router(create_ship_router)
api_router.include_router(current_ships_router)
api_router.include_router(delete_ship_router)

api_router.include_router(current_ports_router)
api_router.include_router(create_port_router)
api_router.include_router(delete_port_router)
api_router.include_router(current_port_stops_router)
api_router.include_router(create_port_stop_router)
api_router.include_router(delete_port_stop_router)
