from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.recording_session import RecordingSessionResponse
from app.services.recording_session_service import RecordingSessionService

router = APIRouter()


@router.post("", response_model=RecordingSessionResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=RecordingSessionResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_session(db: AsyncSession = Depends(get_db)):
    """Create a new recording session with status=idle."""
    return await RecordingSessionService.create_session(db=db)


@router.post("/{session_id}/start", response_model=RecordingSessionResponse)
async def start_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    """Start a recording session (transitions status from idle to recording)."""
    return await RecordingSessionService.start_session(db=db, session_id=session_id)


@router.post("/{session_id}/stop", response_model=RecordingSessionResponse)
async def stop_session(
    session_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Stop a recording session, save uploaded audio file, and trigger Celery task."""
    return await RecordingSessionService.stop_session(db=db, session_id=session_id, audio_file=file)


@router.get("/{session_id}", response_model=RecordingSessionResponse)
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get recording session details (status, transcript, summary)."""
    return await RecordingSessionService.get_session(db=db, session_id=session_id)
