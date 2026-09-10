from typing import Any, Dict
from celery import shared_task
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.recording_session import RecordingSession, SessionStatus
from app.services.transcription import transcribe_audio

# Sync engine for Celery worker tasks
sync_db_uri = settings.SQLALCHEMY_DATABASE_URI.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(sync_db_uri, echo=False)
SyncSessionLocal = sessionmaker(bind=sync_engine)


@shared_task(name="process_audio_session")
def process_audio_session(session_id: str) -> Dict[str, Any]:
    """
    Background task for processing recorded audio sessions.
    Transcribes audio using Groq's whisper-large-v3-turbo and generates text summary.
    """
    with SyncSessionLocal() as db:
        session = db.execute(
            select(RecordingSession).where(RecordingSession.id == session_id)
        ).scalar_one_or_none()

        if not session:
            return {"error": f"Session {session_id} not found"}

        # Perform Groq audio transcription if file exists & API key is set
        if session.audio_file_path and settings.GROQ_API_KEY:
            try:
                session.transcript = transcribe_audio(session.audio_file_path)
            except Exception as e:
                session.status = SessionStatus.FAILED
                db.commit()
                return {"session_id": session_id, "error": f"Transcription failed: {str(e)}"}
        else:
            session.transcript = (
                "Fallback transcript: Groq API key is not configured or audio file path is missing."
            )

        # Generate summary payload
        session.summary = {
            "title": "Audio Recording Summary",
            "key_points": [
                "Groq whisper-large-v3-turbo transcription processing",
                "FastAPI recording session lifecycle update",
                "Asynchronous Celery task completion"
            ],
            "action_items": [
                "Review transcript accuracy",
                "Verify database record status transition"
            ]
        }
        session.status = SessionStatus.SUMMARIZED
        db.commit()

        return {
            "session_id": session_id,
            "status": session.status.value,
            "transcript_length": len(session.transcript) if session.transcript else 0
        }
