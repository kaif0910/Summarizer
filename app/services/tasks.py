import os
import uuid
import logging
from typing import Any, Dict
from celery import shared_task
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.models.recording_session import RecordingSession, SessionStatus
from app.services.transcription import transcribe_audio
from app.services.summarization import summarize_transcript
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)

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
    Celery task that loads the audio file for a session, performs Groq whisper transcription,
    generates a structured MeetingSummary via LangChain Groq LLM, persists outputs to Postgres,
    indexes transcript in ChromaDB, and updates session status to summarized.
    Audited for failure modes (Groq rate limits/timeouts, 0-byte audio, DB transaction errors).
    """
    with SyncSessionLocal() as db:
        try:
            # Ensure UUID object for database queries across Postgres & SQLite
            if isinstance(session_id, str):
                try:
                    target_uuid = uuid.UUID(session_id)
                except ValueError:
                    target_uuid = session_id
            else:
                target_uuid = session_id

            session = db.execute(
                select(RecordingSession).where(RecordingSession.id == target_uuid)
            ).scalar_one_or_none()

            if not session:
                logger.error(f"Session {session_id} not found in database.")
                return {"error": f"Session {session_id} not found"}

            if not session.audio_file_path or not os.path.exists(session.audio_file_path):
                error_msg = f"Audio file path missing or invalid for session {session_id}."
                session.status = SessionStatus.FAILED
                session.summary = {"error": error_msg}
                db.commit()
                return {"error": error_msg}

            if os.path.getsize(session.audio_file_path) == 0:
                error_msg = "Audio file is empty (0 bytes)."
                session.status = SessionStatus.FAILED
                session.summary = {"error": error_msg}
                db.commit()
                return {"error": error_msg}

            # Step 1: Groq Whisper Audio Transcription
            try:
                transcript_text = transcribe_audio(session.audio_file_path)
                session.transcript = transcript_text
            except Exception as tr_err:
                error_msg = f"Transcription failed: {str(tr_err)}"
                logger.error(error_msg)
                session.status = SessionStatus.FAILED
                session.summary = {"error": error_msg}
                db.commit()
                return {"session_id": str(session_id), "status": session.status.value, "error": error_msg}

            # Step 2: LangChain Groq LLM Summarization
            try:
                meeting_summary = summarize_transcript(transcript_text)
                session.summary = meeting_summary.model_dump()
            except Exception as sum_err:
                error_msg = f"Summarization failed: {str(sum_err)}"
                logger.error(error_msg)
                session.status = SessionStatus.FAILED
                session.summary = {"error": error_msg}
                db.commit()
                return {"session_id": str(session_id), "status": session.status.value, "error": error_msg}

            # Step 3: Transition session status to SUMMARIZED
            session.status = SessionStatus.SUMMARIZED
            db.commit()

            # Step 4: Index transcript in ChromaDB vector store
            try:
                created_date = session.created_at.isoformat() if session.created_at else ""
                VectorService.index_session(
                    session_id=str(session.id),
                    text=transcript_text,
                    date_str=created_date,
                    metadata_extra={"session_id": str(session.id), "date": created_date}
                )
            except Exception as vec_err:
                logger.warning(f"ChromaDB indexing warning for session {session_id}: {vec_err}")

            return {
                "session_id": str(session_id),
                "status": session.status.value,
                "transcript_length": len(transcript_text),
                "summary": session.summary
            }

        except SQLAlchemyError as db_err:
            db.rollback()
            logger.error(f"Database transaction error during task execution for session {session_id}: {db_err}")
            return {"session_id": str(session_id), "error": f"Database error: {str(db_err)}"}
        except Exception as general_err:
            logger.error(f"Unhandled task error for session {session_id}: {general_err}")
            return {"session_id": str(session_id), "error": f"Unhandled error: {str(general_err)}"}


@shared_task(name="process_audio_session")
def process_audio_session(session_id: str) -> Dict[str, Any]:
    """Alias/wrapper task forwarding to transcribe_and_process."""
    return transcribe_and_process(session_id)
