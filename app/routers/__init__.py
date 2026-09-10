from fastapi import APIRouter
from app.routers.health import router as health_router
from app.routers.items import router as items_router
from app.routers.sessions import router as sessions_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(items_router, prefix="/items", tags=["Items"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["Sessions"])

__all__ = ["api_router"]
