from typing import Any, Dict
from celery import shared_task
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.recording_session import RecordingSession, SessionStatus
from app.services.transcription import transcribe_audio
from app.services.summarization import summarize_transcript
from app.services.vector_service import VectorService

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
    """
    with SyncSessionLocal() as db:
        session = db.execute(
            select(RecordingSession).where(RecordingSession.id == session_id)
        ).scalar_one_or_none()

        if not session:
            return {"error": f"Session {session_id} not found"}

        if not session.audio_file_path:
            session.status = SessionStatus.FAILED
            session.summary = {"error": f"Session {session_id} has no audio_file_path"}
            db.commit()
            return {"error": f"Session {session_id} has no audio_file_path"}

        try:
            # Step 1: Transcribe audio using Groq whisper-large-v3-turbo
            transcript_text = transcribe_audio(session.audio_file_path)
            session.transcript = transcript_text

            # Step 2: Summarize transcript using LangChain ChatGroq (llama-3.3-70b-versatile)
            meeting_summary = summarize_transcript(transcript_text)
            session.summary = meeting_summary.model_dump()

            # Step 3: Update session status to SUMMARIZED
            session.status = SessionStatus.SUMMARIZED
            db.commit()

            # Step 4: Index transcript in ChromaDB vector store with metadata (session_id, date)
            try:
                created_date = session.created_at.isoformat() if session.created_at else ""
                VectorService.index_session(
                    session_id=str(session.id),
                    text=transcript_text,
                    date_str=created_date,
                    metadata_extra={"session_id": str(session.id), "date": created_date}
                )
            except Exception as vec_err:
                pass

            return {
                "session_id": session_id,
                "status": session.status.value,
                "transcript_length": len(transcript_text),
                "summary": session.summary
            }
        except Exception as e:
            session.status = SessionStatus.FAILED
            session.summary = {"error": str(e)}
            db.commit()
            return {
                "session_id": session_id,
                "status": session.status.value,
                "error": str(e)
            }


@shared_task(name="process_audio_session")
def process_audio_session(session_id: str) -> Dict[str, Any]:
    """Alias/wrapper task forwarding to transcribe_and_process."""
    return transcribe_and_process(session_id)
