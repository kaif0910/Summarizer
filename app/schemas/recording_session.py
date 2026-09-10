from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.models.recording_session import SessionStatus


class RecordingSessionBase(BaseModel):
    status: SessionStatus = SessionStatus.IDLE
    audio_file_path: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None


class RecordingSessionCreate(BaseModel):
    audio_file_path: Optional[str] = None


class RecordingSessionUpdate(BaseModel):
    status: Optional[SessionStatus] = None
    audio_file_path: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None


class RecordingSessionResponse(RecordingSessionBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
