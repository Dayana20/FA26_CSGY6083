"""Collects every API route module into one router for main.py.

To add a new group of endpoints, create a module in app/api/routes/, import
its router here, and include it below.
"""

from fastapi import APIRouter
from app.api.routes.health import router as health_router

# The router main.py registers with the app.
api_router = APIRouter()

# GET /health and GET /health/mysql: is the API running, and can it reach the
# database?
api_router.include_router(health_router)
