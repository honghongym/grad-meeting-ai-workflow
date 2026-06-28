# Grad Meeting AI Workflow

A lightweight AI assistant for graduate research meetings. It turns long meeting transcripts into structured minutes, task plans, review notes, and reusable meeting memory.

The project is designed for small research groups that need a practical local-first tool, not a heavy enterprise meeting platform.

## Features

- **Transcript to minutes**: Paste exported meeting transcripts and generate structured meeting summaries.
- **Dynamic meeting types**: Supports progress meetings, paper reading sessions, experiment reviews, and defense rehearsals.
- **Task extraction**: Produces editable Work Plans with assignees, expected outputs, deadlines, confidence labels, and evidence.
- **Cross-meeting memory**: Confirmed meeting results can be reused as context for later meetings.
- **Human review first**: AI output is treated as a draft until the user confirms it.
- **Progress tracking**: The web UI shows processing status while the workflow is running.
- **Browser extension**: Chrome/Edge extension can extract visible transcript text from a webpage and submit it to the local backend.
- **Local-first setup**: SQLite works out of the box. PostgreSQL and Docker are optional for shared deployment.

## Screens

- Meeting workspace
- New transcript submission
- Structured meeting detail view
- Editable Work Plan
- Review notes and workflow logs
- Browser extension popup

## Architecture Overview

The system uses a lightweight workflow instead of a large multi-service stack:

```text
Transcript
  -> chunking
  -> meeting type validation
  -> segment extraction
  -> deterministic validation
  -> memory lookup
  -> planning
  -> human review
  -> confirmed memory
```

Core components:

- **FastAPI**: backend API and web pages.
- **Jinja2 + Tailwind CSS**: lightweight web UI.
- **SQLAlchemy**: database access.
- **SQLite**: default local database.
- **PostgreSQL / pgvector**: optional deployment database and vector storage.
- **OpenAI-compatible LLM client**: configured for Alibaba Cloud Bailian compatible API by default.
- **Chrome/Edge extension**: optional transcript capture entry point.

## Tech Stack

- Python 3.12
- FastAPI
- SQLAlchemy
- Pydantic v2
- Jinja2
- Tailwind CSS CDN
- OpenAI Python SDK
- SQLite by default
- Optional PostgreSQL + pgvector
- pytest

## Quick Start

Create a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
```

Create local config:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=sqlite:///./meeting_ai.db
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_PROVIDER=bailian
EXTRACTOR_MODEL=deepseek-v4-flash
PLANNER_MODEL=qwen3.7-plus
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSION=1536
```

Run the app:

```powershell
python -m uvicorn app.main:app --reload
```

Open:

```text
http://localhost:8000/meetings
```

## Browser Extension

The extension lives in `browser-extension/`.

To load it:

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable developer mode.
3. Click "Load unpacked".
4. Select the `browser-extension/` folder.
5. Start the backend locally.
6. Open a transcript page and use the extension popup to submit the text.

The extension does not store model API keys. API keys remain in the backend `.env` file.

## API Highlights

```text
POST /api/meetings
GET  /api/meetings
GET  /api/meetings/{meeting_id}/progress
GET  /api/meetings/{meeting_id}/result
GET  /api/meetings/{meeting_id}/markdown
POST /api/meetings/{meeting_id}/confirm
```

Optional API protection:

```env
API_TOKEN=your-local-token
```

When enabled, clients should send:

```text
X-API-Token: your-local-token
```

## Project Structure

```text
app/
  main.py
  config.py
  db.py
  models.py
  schemas.py
  services/
  templates/
browser-extension/
tests/
docker/
```

## Testing

```powershell
python -m pytest
python -m compileall app tests
```

## Deployment Notes

For local use, SQLite is enough.

For a shared lab deployment, use PostgreSQL:

```env
DATABASE_URL=postgresql+psycopg://meeting:meeting@localhost:5432/meeting_ai
```

Docker Compose files are included as an optional deployment path.

## Security Notes

- Do not commit `.env`.
- Do not commit local database files such as `meeting_ai.db`.
- Rotate any token that was exposed in chat, logs, screenshots, or terminal history.

## License

Add a license before public reuse or redistribution.
