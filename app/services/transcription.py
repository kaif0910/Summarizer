import os
import logging
from groq import (
    Groq,
    GroqError,
    RateLimitError,
    AuthenticationError,
    APITimeoutError,
    APIConnectionError
)
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
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError, IOError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def transcribe_audio(file_path: str) -> str:
    """
    Sends an audio file to Groq's whisper-large-v3-turbo endpoint using the groq SDK
    and returns the transcript text. Retries up to 3 times with exponential backoff.
    Performs comprehensive validation and error normalization for failure modes.
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured in settings or environment variables.")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found at path: {file_path}")

    if os.path.getsize(file_path) == 0:
        raise ValueError("Uploaded audio file is empty (0 bytes).")

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)

        with open(file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(file_path), audio_file.read()),
                model="whisper-large-v3-turbo",
                response_format="text"
            )

        if isinstance(transcription, str):
            result = transcription.strip()
        else:
            result = getattr(transcription, "text", str(transcription)).strip()

        if not result:
            raise ValueError("Groq transcription API returned an empty text string.")

        return result

    except RateLimitError as e:
        logger.error(f"Groq API rate limit reached: {e}")
        raise RuntimeError("Groq API rate limit exceeded. Please try again shortly.") from e
    except AuthenticationError as e:
        logger.error(f"Groq API authentication failed: {e}")
        raise RuntimeError("Groq API authentication failed. Please verify GROQ_API_KEY.") from e
    except (APITimeoutError, APIConnectionError) as e:
        logger.error(f"Groq API connection error: {e}")
        raise RuntimeError("Groq API connection timed out. Please check network connectivity.") from e
    except GroqError as e:
        logger.error(f"Groq API general error: {e}")
        raise RuntimeError(f"Groq API error: {str(e)}") from e
