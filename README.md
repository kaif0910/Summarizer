# AI Audio Summarizer & Assistant Service

A production-ready FastAPI microservice that records meeting audio, transcribes speech using Groq's `whisper-large-v3-turbo` model, generates structured meeting summaries via LangChain & Groq LLM (`llama-3.3-70b-versatile`), stores vector embeddings in ChromaDB for semantic search, and processes background tasks asynchronously using Celery and Redis. Includes a single-page HTML/JS web client utilizing the browser `MediaRecorder` API.

---

## Key Features

- **Audio Recording & File Upload**: In-browser recording via `MediaRecorder` API uploaded to FastAPI backend.
- **Fast Transcription**: Groq SDK integration with `whisper-large-v3-turbo` model and exponential backoff retry logic.
- **Structured LLM Summaries**: LangChain chain using `with_structured_output(MeetingSummary)` returning executive summary, key points, action items, and participants.
- **Async Task Queue**: Celery worker queue backed by Redis for offloading transcription and summarization tasks.
- **Semantic Vector Search**: ChromaDB persistent vector store indexing transcripts with metadata (`session_id`, `date`) for similarity search (`GET /api/v1/search?q=...`).
- **PostgreSQL Database**: Async SQLAlchemy models & Alembic migration support.
- **Lightweight Polling**: `GET /api/v1/sessions/{id}/status` optimized for rapid frontend progress updates.

---

## Required Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | **Required**. Groq API Key for Whisper & LLM access | `"gsk_..."` |
| `DATABASE_URL` / `SQLALCHEMY_DATABASE_URI` | PostgreSQL connection string | `"postgresql+asyncpg://postgres:postgres@postgres:5432/app"` |
| `REDIS_URL` / `REDIS_URI` | Redis broker & backend URI | `"redis://redis:6379/0"` |
| `POSTGRES_SERVER` | PostgreSQL server hostname | `postgres` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_USER` | PostgreSQL username | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `postgres` |
| `POSTGRES_DB` | PostgreSQL database name | `app` |
| `REDIS_HOST` | Redis hostname | `redis` |
| `REDIS_PORT` | Redis port | `6379` |

---

## Running with Docker Compose (Recommended)

Docker Compose starts all four required services (`api`, `celery_worker`, `postgres`, and `redis`) with volume mounts for persistence.

### 1. Launch Services
```bash
docker compose up --build -d
```

### 2. Run Database Migrations
```bash
docker compose exec api alembic upgrade head
```

### 3. Access Application
- **Web App UI**: `http://localhost:8000/`
- **Interactive OpenAPI Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/api/v1/health`

### 4. Stop Services
```bash
docker compose down
```

---

## Local Development Setup (Manual)

If you prefer to run services locally outside of Docker:

### 1. Prerequisites
- Python 3.11+
- PostgreSQL server
- Redis server

### 2. Create Virtual Environment & Install Dependencies
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Run Database Migrations
```bash
alembic upgrade head
```

### 4. Start Celery Worker
```bash
celery -A app.celery_app.celery_app worker --loglevel=info
```

### 5. Start FastAPI Dev Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/sessions` | Create a new session (`status=idle`) |
| `POST` | `/api/v1/sessions/{id}/start` | Transition status to `recording` |
| `POST` | `/api/v1/sessions/{id}/stop` | Upload audio file, set status to `processing`, dispatch Celery task |
| `GET` | `/api/v1/sessions/{id}` | Retrieve complete session record with transcript & summary |
| `GET` | `/api/v1/sessions/{id}/status` | **Lightweight polling endpoint** returning `id`, `status`, and `error` |
| `GET` | `/api/v1/search?q=...` | Perform semantic vector search across past sessions in ChromaDB |
| `GET` | `/api/v1/health` | Comprehensive health check for PostgreSQL, Redis, and Celery workers |

---

## Running Pytest Test Suite

The test suite uses an in-memory SQLite database and mocks all Groq API network calls.

```bash
pytest tests/ -v
```
