from typing import Any, Dict
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "summarizer_tasks",
    broker=settings.REDIS_URI,
    backend=settings.REDIS_URI,
    include=["app.services.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="health_check_task")
def health_check_task() -> Dict[str, Any]:
    """Health check task to verify Celery worker connectivity."""
    return {"status": "ok", "worker": "connected"}
