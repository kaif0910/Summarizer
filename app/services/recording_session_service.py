import os
import uuid
from typing import Optional
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recording_session import RecordingSession, SessionStatus
from app.schemas.recording_session import RecordingSessionStatusResponse
from app.core.celery_app import celery_app

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class RecordingSessionService:
    @staticmethod
    async def create_session(db: AsyncSession) -> RecordingSession:
        """Create a new recording session with status=idle."""
        session = RecordingSession(
            id=uuid.uuid4(),
            status=SessionStatus.IDLE
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def start_session(db: AsyncSession, session_id: uuid.UUID) -> RecordingSession:
        """Transition session status from idle to recording."""
        result = await db.execute(
            select(RecordingSession).where(RecordingSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recording session {session_id} not found"
            )
        if session.status != SessionStatus.IDLE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot start session in '{session.status.value}' state. Expected 'idle'."
            )

        session.status = SessionStatus.RECORDING
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def stop_session(
        db: AsyncSession,
        session_id: uuid.UUID,
        audio_file: UploadFile
    ) -> RecordingSession:
        """Save uploaded audio file, transition status to processing, and dispatch transcribe_and_process Celery task."""
        result = await db.execute(
            select(RecordingSession).where(RecordingSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recording session {session_id} not found"
            )

        # Validate non-empty audio upload
        content = await audio_file.read()
        if not content or len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded audio file is empty (0 bytes)."
            )

        # Save uploaded audio file to disk
        file_filename = audio_file.filename or "recording.wav"
        saved_filename = f"{session_id}_{file_filename}"
        file_path = os.path.join(UPLOAD_DIR, saved_filename)

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        session.audio_file_path = file_path
        session.status = SessionStatus.PROCESSING
        await db.commit()
        await db.refresh(session)

        # Dispatch Celery background task transcribe_and_process
        celery_app.send_task("transcribe_and_process", args=[str(session_id)])

        return session

    @staticmethod
    async def get_session(db: AsyncSession, session_id: uuid.UUID) -> RecordingSession:
        """Retrieve recording session details by UUID."""
        result = await db.execute(
            select(RecordingSession).where(RecordingSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recording session {session_id} not found"
            )
        return session

    @staticmethod
    async def get_session_status(db: AsyncSession, session_id: uuid.UUID) -> RecordingSessionStatusResponse:
        """Retrieve lightweight recording session status for polling."""
        result = await db.execute(
            select(RecordingSession).where(RecordingSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recording session {session_id} not found"
            )

        error_msg = None
        if isinstance(session.summary, dict) and "error" in session.summary:
            error_msg = session.summary["error"]

        return RecordingSessionStatusResponse(
            id=session.id,
            status=session.status,
            error=error_msg
        )
