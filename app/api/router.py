from fastapi import APIRouter
from app.api.routes.account import router as account_router
from app.api.routes.auth import router as auth_router
from app.api.routes.employee import router as employee_router
from app.api.routes.health import router as health_router
from app.api.routes.home import router as home_router
from app.api.routes.mysql_health import router as mysql_health_router

api_router = APIRouter()

api_router.include_router(home_router)
api_router.include_router(auth_router)
api_router.include_router(account_router)
api_router.include_router(employee_router)
api_router.include_router(health_router)
api_router.include_router(mysql_health_router, prefix="/health", tags=["health"])