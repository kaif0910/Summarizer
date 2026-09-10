from typing import Any, Dict
from celery import shared_task
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.recording_session import RecordingSession, SessionStatus
from app.services.transcription import transcribe_audio
from app.services.summarization import summarize_transcript

# Sync engine for Celery worker tasks
sync_db_uri = settings.SQLALCHEMY_DATABASE_URI.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(sync_db_uri, echo=False)
SyncSessionLocal = sessionmaker(bind=sync_engine)


@shared_task(name="health_check_task")
def health_check_task() -> Dict[str, Any]:
    """Health check task to verify Celery worker connectivity."""
    return {"status": "ok", "worker": "connected"}


@shared_task(name="transcribe_and_process")
def transcribe_and_process(session_id: str) -> Dict[str, Any]:
    """
    Celery task that loads the audio file for a session, calls Groq whisper transcription,
    generates a structured MeetingSummary via LangChain Groq LLM, saves the outputs to Postgres,
    and updates the session status to summarized.
    """
    with SyncSessionLocal() as db:
        session = db.execute(
            select(RecordingSession).where(RecordingSession.id == session_id)
        ).scalar_one_or_none()

        if not session:
            return {"error": f"Session {session_id} not found"}

        if not session.audio_file_path:
            session.status = SessionStatus.FAILED
            db.commit()
            return {"error": f"Session {session_id} has no audio_file_path"}

        try:
            # 1. Groq audio transcription
            transcript_text = transcribe_audio(session.audio_file_path)
            session.transcript = transcript_text

            # 2. LangChain Groq structured LLM summarization
            if settings.GROQ_API_KEY:
                try:
                    summary_obj = summarize_transcript(transcript_text)
                    session.summary = summary_obj.model_dump()
                except Exception as sum_err:
                    session.summary = {
                        "summary": f"Summarization error: {str(sum_err)}",
                        "key_points": [],
                        "action_items": [],
                        "participants": None
                    }
            else:
                session.summary = {
                    "summary": "GROQ_API_KEY is not configured.",
                    "key_points": [],
                    "action_items": [],
                    "participants": None
                }

            # 3. Update session status to next stage (SUMMARIZED)
            session.status = SessionStatus.SUMMARIZED
            db.commit()

            return {
                "session_id": session_id,
                "status": session.status.value,
                "transcript_length": len(transcript_text)
            }
        except Exception as e:
            session.status = SessionStatus.FAILED
            db.commit()
            return {
                "session_id": session_id,
                "status": session.status.value,
                "error": f"Processing failed: {str(e)}"
            }


@shared_task(name="process_audio_session")
def process_audio_session(session_id: str) -> Dict[str, Any]:
    """Alias/wrapper task forwarding to transcribe_and_process."""
    return transcribe_and_process(session_id)
