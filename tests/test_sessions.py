import io
import os
import uuid
from unittest.mock import patch, MagicMock
import pytest
from httpx import AsyncClient

from app.schemas.summary import MeetingSummary
from app.models.recording_session import SessionStatus
from app.services.tasks import transcribe_and_process
from tests.conftest import SyncTestingSessionLocal


@pytest.mark.asyncio
async def test_create_session_idle(async_client: AsyncClient):
    """Verify POST /sessions initializes a new session with status=idle."""
    response = await async_client.post("/api/v1/sessions")
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] == "idle"
    assert data["audio_file_path"] is None
    assert data["transcript"] is None
    assert data["summary"] is None


@pytest.mark.asyncio
async def test_start_session_recording(async_client: AsyncClient):
    """Verify POST /sessions/{id}/start transitions session status from idle to recording."""
    create_res = await async_client.post("/api/v1/sessions")
    session_id = create_res.json()["id"]

    start_res = await async_client.post(f"/api/v1/sessions/{session_id}/start")
    assert start_res.status_code == 200
    data = start_res.json()
    assert data["id"] == session_id
    assert data["status"] == "recording"


@pytest.mark.asyncio
async def test_invalid_start_transition(async_client: AsyncClient):
    """Verify restarting a session that is already in recording state returns HTTP 400 Bad Request."""
    create_res = await async_client.post("/api/v1/sessions")
    session_id = create_res.json()["id"]

    # First start -> recording
    await async_client.post(f"/api/v1/sessions/{session_id}/start")

    # Second start -> invalid transition error
    start_res_2 = await async_client.post(f"/api/v1/sessions/{session_id}/start")
    assert start_res_2.status_code == 400
    assert "Cannot start session" in start_res_2.json()["detail"]


@pytest.mark.asyncio
async def test_empty_file_upload_error(async_client: AsyncClient):
    """Verify uploading an empty 0-byte audio file returns HTTP 400 Bad Request."""
    create_res = await async_client.post("/api/v1/sessions")
    session_id = create_res.json()["id"]

    empty_file = io.BytesIO(b"")

    with patch("app.core.celery_app.celery_app.send_task"):
        stop_res = await async_client.post(
            f"/api/v1/sessions/{session_id}/stop",
            files={"file": ("empty.wav", empty_file, "audio/wav")}
        )
    assert stop_res.status_code == 400
    assert "Uploaded audio file is empty" in stop_res.json()["detail"]


@pytest.mark.asyncio
async def test_stop_session_processing(async_client: AsyncClient):
    """Verify uploading a valid audio file transitions session status to processing and dispatches task."""
    create_res = await async_client.post("/api/v1/sessions")
    session_id = create_res.json()["id"]

    dummy_audio_bytes = b"RIFF....WAVEfmt ....data...."
    file_payload = io.BytesIO(dummy_audio_bytes)

    with patch("app.core.celery_app.celery_app.send_task") as mock_send_task:
        stop_res = await async_client.post(
            f"/api/v1/sessions/{session_id}/stop",
            files={"file": ("sample.wav", file_payload, "audio/wav")}
        )
        assert stop_res.status_code == 200
        data = stop_res.json()
        assert data["status"] == "processing"
        assert data["audio_file_path"] is not None
        mock_send_task.assert_called_once_with("transcribe_and_process", args=[session_id])


@pytest.mark.asyncio
async def test_polling_status_endpoint(async_client: AsyncClient):
    """Verify GET /sessions/{id}/status returns lightweight status object."""
    create_res = await async_client.post("/api/v1/sessions")
    session_id = create_res.json()["id"]

    status_res = await async_client.get(f"/api/v1/sessions/{session_id}/status")
    assert status_res.status_code == 200
    data = status_res.json()
    assert data["id"] == session_id
    assert data["status"] == "idle"
    assert data["error"] is None


@pytest.mark.asyncio
async def test_transcribe_and_process_task_summarized(async_client: AsyncClient, mock_meeting_summary: MeetingSummary):
    """
    Verify the complete end-to-end task execution (transcribe_and_process)
    with mocked Groq API calls, asserting transition from processing to summarized.
    """
    create_res = await async_client.post("/api/v1/sessions")
    session_id = create_res.json()["id"]

    dummy_audio_bytes = b"RIFF....WAVEfmt ....data...."
    file_payload = io.BytesIO(dummy_audio_bytes)

    with patch("app.core.celery_app.celery_app.send_task"):
        await async_client.post(
            f"/api/v1/sessions/{session_id}/stop",
            files={"file": ("test.wav", file_payload, "audio/wav")}
        )

    # Mock Groq transcription, LLM summarization, ChromaDB vector store, and SyncSessionLocal
    mock_transcript = "This is a mocked audio transcription of the session."

    with patch("app.services.tasks.SyncSessionLocal", SyncTestingSessionLocal), \
         patch("app.services.tasks.transcribe_audio", return_value=mock_transcript) as mock_transcribe, \
         patch("app.services.tasks.summarize_transcript", return_value=mock_meeting_summary) as mock_summarize, \
         patch("app.services.tasks.VectorService.index_session") as mock_vector_index:

        # Execute Celery task synchronously
        task_result = transcribe_and_process(session_id)

        assert task_result["status"] == "summarized"
        assert task_result["session_id"] == session_id
        mock_transcribe.assert_called_once()
        mock_summarize.assert_called_once_with(mock_transcript)
        mock_vector_index.assert_called_once()

    # Query GET /sessions/{id} to verify persisted state in database
    get_res = await async_client.get(f"/api/v1/sessions/{session_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["status"] == "summarized"
    assert data["transcript"] == mock_transcript
    assert data["summary"]["summary"] == mock_meeting_summary.summary
    assert len(data["summary"]["key_points"]) == 3


@pytest.mark.asyncio
async def test_task_failure_handling(async_client: AsyncClient):
    """Verify task catches transcription failures, sets status to failed, and stores error string."""
    create_res = await async_client.post("/api/v1/sessions")
    session_id = create_res.json()["id"]

    dummy_audio_bytes = b"RIFF....WAVEfmt ....data...."
    file_payload = io.BytesIO(dummy_audio_bytes)

    with patch("app.core.celery_app.celery_app.send_task"):
        await async_client.post(
            f"/api/v1/sessions/{session_id}/stop",
            files={"file": ("bad_audio.wav", file_payload, "audio/wav")}
        )

    # Mock Groq API throwing RuntimeError (e.g. Rate limit or connection timeout)
    with patch("app.services.tasks.SyncSessionLocal", SyncTestingSessionLocal), \
         patch("app.services.tasks.transcribe_audio", side_effect=RuntimeError("Groq API rate limit exceeded.")):
        task_result = transcribe_and_process(session_id)
        assert task_result["status"] == "failed"
        assert "Groq API rate limit exceeded" in task_result["error"]

    # Verify status endpoint reflects failure
    status_res = await async_client.get(f"/api/v1/sessions/{session_id}/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "failed"
    assert "Groq API rate limit exceeded" in status_data["error"]
