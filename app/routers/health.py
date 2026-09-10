from typing import Any, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis.asyncio import Redis

from app.core.db import get_db, get_redis

router = APIRouter()


@router.get("/health", response_model=Dict[str, Any])
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    # Check Database connection
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Check Redis connection
    redis_status = "healthy"
    try:
        await redis.ping()
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    overall = "ok" if db_status == "healthy" and redis_status == "healthy" else "degraded"

    return {
        "status": overall,
        "services": {
            "database": db_status,
            "redis": redis_status
        }
    }
