import os
from typing import AsyncGenerator
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.db import Base, get_db
from app.schemas.summary import MeetingSummary

TEST_DB_FILE = "./test_app.db"
ASYNC_TEST_DB_URI = f"sqlite+aiosqlite:///{TEST_DB_FILE}"
SYNC_TEST_DB_URI = f"sqlite:///{TEST_DB_FILE}"

test_engine = create_async_engine(ASYNC_TEST_DB_URI, echo=False)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

sync_test_engine = create_engine(SYNC_TEST_DB_URI, echo=False)
SyncTestingSessionLocal = sessionmaker(bind=sync_test_engine)


@pytest.fixture(autouse=True)
async def setup_test_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
    sync_test_engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_meeting_summary() -> MeetingSummary:
    return MeetingSummary(
        summary="This is a mocked executive summary of the meeting.",
        key_points=[
            "Discussed database migration strategy",
            "Configured Groq Whisper transcription service",
            "Integrated Celery background task processing"
        ],
        action_items=[
            "Deploy containers with Docker Compose",
            "Verify pytest test coverage"
        ],
        participants=["Alice", "Bob"]
    )
