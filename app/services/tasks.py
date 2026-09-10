from typing import Any, Dict
from celery import shared_task
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.recording_session import RecordingSession, SessionStatus

# Sync engine for Celery worker tasks
sync_db_uri = settings.SQLALCHEMY_DATABASE_URI.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(sync_db_uri, echo=False)
SyncSessionLocal = sessionmaker(bind=sync_engine)


@shared_task(name="process_audio_session")
def process_audio_session(session_id: str) -> Dict[str, Any]:
    """
    Background task for processing recorded audio sessions.
    Simulates transcription and LLM-based summarization.
    """
    with SyncSessionLocal() as db:
        session = db.execute(
            select(RecordingSession).where(RecordingSession.id == session_id)
        ).scalar_one_or_none()

        if not session:
            return {"error": f"Session {session_id} not found"}

        # Simulate audio transcription & LLM summary generation
        session.transcript = (
            "This is an automated transcription of the recorded audio session. "
            "The speaker discussed system architecture, FastAPI endpoint setup, "
            "PostgreSQL database integration, and Celery background task processing."
        )
        session.summary = {
            "title": "Audio Recording Summary",
            "key_points": [
                "FastAPI project boilerplate initialization",
                "RecordingSession model and state transitions",
                "Celery integration for async audio processing"
            ],
            "action_items": [
                "Deploy services with Docker Compose",
                "Verify session endpoints and status flow"
            ]
        }
        session.status = SessionStatus.SUMMARIZED
        db.commit()

        return {
            "session_id": session_id,
            "status": session.status.value,
            "transcript_length": len(session.transcript)
        }
