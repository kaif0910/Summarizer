from typing import Any, Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis.asyncio import Redis

from app.core.db import get_db, get_redis
from app.celery_app import celery_app

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

    # Check Celery worker connection
    celery_status = "healthy"
    try:
        inspect = celery_app.control.inspect(timeout=1.0)
        workers = inspect.ping()
        if not workers:
            celery_status = "degraded: no active workers detected"
    except Exception as e:
        celery_status = f"unhealthy: {str(e)}"

    overall = "ok" if (db_status == "healthy" and redis_status == "healthy" and "healthy" in celery_status) else "degraded"

    return {
        "status": overall,
        "services": {
            "database": db_status,
            "redis": redis_status,
            "celery": celery_status
        }
    }


@router.post("/health/celery-task", status_code=status.HTTP_202_ACCEPTED)
async def trigger_celery_health_check():
    """Trigger the health-check task to verify Celery worker connectivity."""
    task = celery_app.send_task("health_check_task")
    return {
        "message": "Celery health-check task dispatched successfully",
        "task_id": task.id,
        "status": "queued"
    }
