import os
import logging
from groq import Groq, GroqError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from app.core.config import settings

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((GroqError, IOError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def transcribe_audio(file_path: str) -> str:
    """
    Sends an audio file to Groq's whisper-large-v3-turbo endpoint using the groq SDK
    and returns the transcript text. Retries up to 3 times with exponential backoff.
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in environment or settings.")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found at path: {file_path}")

    client = Groq(api_key=settings.GROQ_API_KEY)

    with open(file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(file_path), audio_file.read()),
            model="whisper-large-v3-turbo",
            response_format="text"
        )

    if isinstance(transcription, str):
        return transcription.strip()

    return getattr(transcription, "text", str(transcription)).strip()
