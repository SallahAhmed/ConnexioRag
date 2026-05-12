# Connexio — Agentic RAG App Overview

## What Is This App?

**Connexio** is an **Agentic RAG (Retrieval-Augmented Generation)** platform. It acts as an intelligent AI advisor for a project collaboration platform (think: GitHub meets LinkedIn for students/teams). Users upload documents (PDFs/text), which get chunked, embedded, and indexed into a PostgreSQL vector database. The agent then answers questions by retrieving relevant context from those documents and/or from Wikipedia and the SQL database.

---

## Core Idea / Goal

The agent is designed to support different **personas** and **workflow nodes**:

| Persona | Who |
|---------|-----|
| `student` | Someone starting a new project |
| `early_career` | A junior professional |
| `educator` | A teacher/mentor |
| `company` | An organization |

| Workflow Node | Trigger |
|--------------|---------|
| `ONBOARDING` | New user, first steps |
| `TEAM_FORMATION` | Looking for teammates |
| `PHASE_TRANSITION` | Moving between project phases |
| `BLOCKER` | Stuck on a problem |
| `MILESTONE_WARNING` | Overdue / deadline risk |
| `GENERAL` | General chat / fallback |

---

## Architecture

```
User → FastAPI → NLPController
                    ↓
           WorkflowController (detects node + language: en/ar)
                    ↓
             ToolManager (multi-source retrieval)
          ┌──────────────────────────────────┐
          │  1. Knowledge Base (PGVector)    │ ← Hybrid vector + full-text
          │  2. Wikipedia (fallback/CRAG)    │
          │  3. SQL Database (LangChain)     │ ← Text-to-SQL
          └──────────────────────────────────┘
                    ↓
             Reranker (SentenceTransformer)
                    ↓
             LLM Generation (Ollama/OpenAI)
                    ↓
          Session History Saved to Postgres
```

---

## Services Required to Run

| Service | How it runs | Port (host access) |
|---------|-------------|-------------------|
| PostgreSQL + PGVector | Docker | `172.17.80.1:5433` (from WSL) |
| RabbitMQ | Docker | `172.17.80.1:5672` |
| Redis | Docker | `172.17.80.1:6379` |
| Ollama (LLM) | Windows host | `172.17.80.1:11434` |
| FastAPI | WSL | `localhost:8000` |
| Celery Worker | WSL | (background) |

---

## How to Start Everything

### 1. Start Docker Services (Windows PowerShell)
```powershell
docker compose -f docker/docker-compose.yml up -d pgvector rabbitmq redis
```

### 2. Start Ollama (Windows PowerShell)
```powershell
$env:OLLAMA_HOST="0.0.0.0"
ollama serve
```
Make sure models are pulled:
```powershell
ollama pull gemma4:e2b
ollama pull nomic-embed-text:latest
```

### 3. Start Celery Worker (WSL, from `/mnt/c/Users/salla/mini-rag-app/src`)
```bash
python -m celery -A celery_app worker --loglevel=info \
  --queues=file_processing,default \
  --without-mingle --without-gossip --without-heartbeat
```
> The `--without-mingle/gossip/heartbeat` flags are required due to a RabbitMQ 4.x incompatibility with Celery's transient queue declarations.

### 4. Start FastAPI (WSL, from `/mnt/c/Users/salla/mini-rag-app/src`)
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## API Endpoints Summary

### Data Ingestion
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/data/upload/{project_id}` | Upload PDF/TXT file |
| POST | `/api/v1/data/process/{project_id}` | Chunk and store file |

### Vector Indexing (Sync — via FastAPI directly)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/nlp/index/push` | Embed chunks → push to PGVector |
| POST | `/api/v1/nlp/index/info` | View collection stats |
| POST | `/api/v1/nlp/index/search` | Semantic search |
| POST | `/api/v1/nlp/index/answer` | RAG Q&A |

### Agent Chat
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/nlp/agent/chat` | Full agentic chat (with node detection, CRAG, history) |
| POST | `/api/v1/nlp/agent/chat/stream` | Same but SSE streaming |
| POST | `/api/v1/nlp/agent/portfolio` | Auto-generate user portfolio |
| POST | `/api/v1/nlp/agent/supervisor/risks` | Project risk assessment |
| POST | `/api/v1/nlp/agent/coach/path` | Skill coaching path |
| POST | `/api/v1/nlp/agent/doc-gen` | Generate README/Retrospective |
| POST | `/api/v1/nlp/agent/task-architect/plan` | Task resolution plan |

### Background Processing (via Celery)
- **Task**: `tasks.file_processing.process_project_files`
- **Queue**: `file_processing`
- Currently triggered manually; endpoint in `data.py` triggers it

---

## End-to-End Test Flow (Happy Path)

1. **Upload a file** → `POST /api/v1/data/upload/1` with a PDF
2. **Process it** → `POST /api/v1/data/process/1` with `chunk_size=512, overlap_size=50`
3. **Index it** → `POST /api/v1/nlp/index/push` with `project_id: 1`
4. **Chat with it** → `POST /api/v1/nlp/agent/chat` with a question about the document

---

## Open Questions for User

1. **What is the main domain of the uploaded documents?** (project management docs, tech specs, student guides, etc.) — this affects which workflow nodes get triggered correctly.
2. **Is there a separate "main Connexio DB"** (with tables like `user`, `project`, `task`, `technology`) that some ToolManager queries reference? Or is the RAG database the only one?
3. **Is the `/api/v1/data/process` endpoint supposed to stay synchronous** (blocking FastAPI) or was the plan to delegate ALL processing to Celery background tasks going forward?
