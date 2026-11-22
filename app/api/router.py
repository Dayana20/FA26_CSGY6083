from fastapi import APIRouter
from app.api.routes.health import router as health_router
from app.api.routes.mysql_health import router as mysql_health_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(mysql_health_router, prefix="/health", tags=["health"])