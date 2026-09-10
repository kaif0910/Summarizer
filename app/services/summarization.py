import logging
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.schemas.summary import MeetingSummary

logger = logging.getLogger(__name__)


def summarize_transcript(transcript: str) -> MeetingSummary:
    """
    Takes a transcript string and returns a structured MeetingSummary instance
    using Groq's LLM API (llama-3.3-70b-versatile) via LangChain's with_structured_output.
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in environment or settings.")

    if not transcript or not transcript.strip():
        raise ValueError("Transcript content cannot be empty.")

    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        groq_api_key=settings.GROQ_API_KEY,
        temperature=0.2,
    )

    structured_llm = llm.with_structured_output(MeetingSummary)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert AI executive assistant specializing in meeting summarization. "
            "Analyze the provided meeting transcript and extract an executive summary, key points discussed, "
            "action items with assignments, and identified participants."
        ),
        ("human", "Meeting Transcript:\n{transcript}")
    ])

    chain = prompt | structured_llm

    result = chain.invoke({"transcript": transcript})
    return result
