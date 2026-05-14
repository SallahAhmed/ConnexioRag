# OpenWolf

@.wolf/OPENWOLF.md

This project uses OpenWolf for context management. Read and follow .wolf/OPENWOLF.md every session. Check .wolf/cerebrum.md before generating code. Check .wolf/anatomy.md before reading files.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## System Overview — What This Is

**Connexio** is a collaborative platform that connects learners and builders to create real software projects in intelligent teams. It spans four components that must work together as one production system:

| Component           | Path                                    | Status                              | Role                                                                  |
| ------------------- | --------------------------------------- | ----------------------------------- | --------------------------------------------------------------------- |
| **Node.js Backend** | `github.com/Hassan19Z/Connexio-backend` | Deployed (Hostinger)                | Core API: auth, users, projects, tasks, chat, file upload             |
| **Connexios RAG**   | `C:\Users\salla\Connexios`              | Deployed (HF Spaces: ConnexioRag)   | Knowledge engine: document indexing, hybrid search, intent-aware chat |
| **MasarX Agent**    | `F:\MasarX_A`                           | Deployed (HF Spaces: ConnexioAgent) | Autonomous PM: task creation, team matching, audit, HITL workflows    |
| **Frontend**        | TBD                                     | Not started                         | UI — will be the last integration layer                               |

**Goal:** Make all three backend services production-ready and fully integrated so only the frontend remains to connect.

---

## Integration Architecture

```
Browser / Frontend
       │
       ▼
Node.js Backend (connexio.icu — Hostinger)
Express + MySQL + JWT Auth
       │
       ├── X-API-Key ──────────────────► Connexios RAG (HF Spaces: ConnexioRag)
       │   POST /api/v1/data/upload-and-process/{pid}    (file indexing — 202 fire-and-forget)
       │   POST /api/v1/projects/sync                    (project ID sync)
       │   POST /api/v1/nlp/agent/chat/{pid}             (chat)
       │   GET  /api/v1/nlp/agent/chat/stream/{pid}      (streaming chat)
       │
       └── Service JWT ─────────────────► MasarX Agent (HF Spaces: ConnexioAgent)
           POST /api/v1/masarx/webhook/event/{type}/{pid}  (events, fire-and-forget)
           POST /api/v1/masarx/agent/{intent}/{pid}        (manual triggers)
           POST /api/v1/masarx/approval/{token}            (HITL decisions)

Both Python services share one PostgreSQL (Neon.tech):
  Connexios owns:  projects, assets, chunks, rag_chat_sessions, collection_{size}_{pid}
  MasarX owns:     masarx_notifications, masarx_pending_plans, user, task
  Shared (read):   projects, chunks (MasarX reads but Connexios owns the schema)
```

### Auth Model

- **Backend → Connexios RAG:** `X-API-Key` header matching `CONNEXIO_INTERNAL_API_KEY`. Already implemented. Dev bypass if key is unset.
- **Backend → MasarX:** Short-lived service token (JWT, signed with `JWT_SECRET`, exp: 5 min, payload: `{uid, project_id, intent}`). To be implemented in Phase 2.
- **MasarX internal/Celery Beat calls:** Service-level actor `uid=0, actor="system"` — no JWT, same DB session.

### Project ID Strategy

MySQL `PID` is the canonical project ID across all systems. When the backend creates a project, it must explicitly INSERT `project_id = PID` into PostgreSQL (not use the sequence). A mapping table (`project_id_map`) in PostgreSQL ensures no silent divergence even if sequences drift.

### File Upload → RAG Indexing Flow

Upload is fire-and-forget: backend calls `POST /api/v1/data/upload-and-process/{pid}`, RAG returns `202 Accepted` immediately with a `task_id`, and runs embedding in a FastAPI `asyncio.create_task` background (no Celery needed for Phase 1). Chunk counts are small enough to avoid timeout.

### Database Schema Ownership Rules

Connexios runs Alembic migrations and owns the `chunks` table schema. MasarX must NOT run `create_all` for `chunks` or `projects` — only for `masarx_*`, `user`, `task`. MasarX's `DataChunk` model must exactly mirror Connexios's columns:

- Required additions to MasarX's `live_models.py`: `chunk_asset_id` (Integer, nullable), `updated_at` (DateTime, onupdate)

---

## Connexios RAG (`C:\Users\salla\Connexios`)

### Dev Commands

```bash
# All from src/
cd src

# API server
uvicorn main:app --reload --port 8080

# Celery worker (needs RabbitMQ + Redis)
python -m celery -A celery_app worker --queues=default,file_processing,data_indexing --loglevel=info

# Celery Beat (daily maintenance)
python -m celery -A celery_app beat --loglevel=info

# Flower monitor UI → http://localhost:5556
python -m celery -A celery_app flower --conf=flowerconfig.py

# Full stack (Docker — recommended for infra)
cd docker && docker-compose up -d
cd docker && docker-compose down
```

No automated test suite exists yet.

### Environment (`src/.env`)

Key variables:

| Variable                                   | Purpose                                                   |
| ------------------------------------------ | --------------------------------------------------------- |
| `GENERATION_BACKEND` / `EMBEDDING_BACKEND` | Provider: `GROQ`, `OPENAI`, `COHERE`                      |
| `VECTOR_DB_BACKEND`                        | `QDRANT` or `PGVECTOR`                                    |
| `POSTGRES_*`                               | Host, port, credentials, database                         |
| `GROQ_API_KEY` / `OPENAI_API_KEY`          | LLM credentials                                           |
| `CONNEXIO_INTERNAL_API_KEY`                | Shared secret for X-API-Key auth (unset = dev bypass)     |
| `MAIN_BACKEND_URL`                         | URL of Node.js backend (default: `http://localhost:3000`) |

Docker env files live in `docker/env/` per service.

**HF Spaces deployment:** Port 7860, UID 1000 user. All secrets set as HF Space environment variables (never committed). `POSTGRES_PORT` must be **5432** for Neon.tech pooler (not 5433 which is only for local Docker pgvector).

### Tiered Response Strategy

Response cost is gated by context value. No project context = no RAG value = no generation model.

| Tier | Condition | Model | History | Cost |
|------|-----------|-------|---------|------|
| 0 | `OUT_OF_SCOPE` | None — canned string | — | 0 tokens |
| 1 | `project_id is None` (any node) | `utility_client` (8B) + 12-tok system prompt | Last 4 msgs (2 turns) | ~80–150 tokens |
| 2 | `project_id` set | `generation_client` (70B) + full RAG prompt | Token-budget window | ~300–800 tokens |

`OUT_OF_SCOPE` covers: geography, politics, cooking, weather, celebrity, historical figures (`"who is X"` bypasses the 50-char fast-path via `_SKIP_FAST_PATH`), jailbreak attempts (`"your system prompt"`, `"ignore your instructions"`, `"bypass your rules"`, etc.) and Arabic equivalents.

### Request Flow

```
POST /api/v1/nlp/agent/chat/{project_id}   [X-API-Key required]
    │
    ▼
NLPController._prepare_chat_context()
  1. WorkflowController.detect_language()     # Arabic: Unicode range ؀-ۿ
  2. WorkflowController.detect_node()         # keyword → _SKIP_FAST_PATH check → 50-char fast-path → utility LLM
  3. SessionModel.get_or_create_session()     # PostgreSQL chat history
     └── project_id is None: cap history at last 4 messages (2 turns)
  4. ToolManager.search_knowledge_base()      # vector search — SKIPPED if no project_id
  5. WorkflowController.grade_relevance()     # utility LLM: YES/NO
  6. [CRAG] ONLY fires when project_id is set: WIKIPEDIA / GOOGLE / GITHUB / PYTHON / NONE
  7. BackendApiClient.get_rich_context()      # live user/project/tasks — SKIPPED if no project_id
    │
    ▼
  Tier 0: OUT_OF_SCOPE → canned refusal returned immediately (0 LLM calls)
  Tier 1: project_id is None → utility_client.generate_text() (8B, minimal prompt)
  Tier 2: project_id set    → generation_client.generate_text() (70B, full RAG prompt)
    │
    ▼
SessionModel.append_message()          # persist history
traces/trace_{uuid}.json               # written to disk per request
```

### Architecture

**Provider Factory Pattern** — `LLMProviderFactory` and `VectorDBProviderFactory` swap implementations via `.env` without touching business logic.

**Three LLM clients:**

- `generation_client` — large model for final answers (`GENERATION_MODEL_ID`) — used only when `project_id` is set
- `utility_client` — small/fast for classification, grading, tool selection, and projectless sessions (`UTILITY_MODEL_ID`, default: `llama-3.1-8b-instant`)
- `embedding_client` — embedding model (`EMBEDDING_MODEL_ID`)

**Workflow nodes** (`WorkflowNodeEnum`): `ONBOARDING`, `TEAM_FORMATION`, `PHASE_TRANSITION`, `BLOCKER`, `MILESTONE_WARNING`, `GENERAL`, `OUT_OF_SCOPE`.

**Vector collection naming:** `collection_{embedding_size}_{project_id}` — single source of truth in `NLPController.create_collection_name()`. MasarX's `RAGTool` uses the same convention.

**CRAG:** Only activates when `project_id` is set. If vector search is irrelevant or empty, the agent falls back to external tools (Wikipedia, Google, GitHub, Python). `BackendApiClient` fetches live user/project/member/task data via REST (5-min cache for stable data, no cache for tasks).

**No direct DB to Node.js backend** — all live data flows through `BackendApiClient` REST calls only.

### Module Map

```
src/
├── main.py                  # Startup: DB + LLM clients + VectorDB + BackendApiClient singleton
├── celery_app.py            # Celery config, 4 queues, beat schedule
├── Routes/
│   ├── base.py              # /health, version
│   ├── data.py              # /upload, /process, /process-and-push, /upload-and-process  [X-API-Key]
│   ├── projects.py          # /sync — project ID sync from Node.js MySQL PID  [X-API-Key]
│   ├── nlp.py               # embed/search endpoints                [X-API-Key]
│   └── agent.py             # /chat/{pid}, /chat/stream/{pid}       [X-API-Key]
├── controllers/
│   ├── NLPController.py     # Core RAG orchestration (CRAG pipeline, streaming)
│   ├── WorkflowController.py # Intent + language detection, relevance grading
│   └── helpers/
│       ├── ToolManager.py   # Wikipedia, Google, GitHub, Python, KB search
│       └── TraceManager.py  # JSON trace per request → traces/
├── stores/
│   ├── llm/providers/       # OpenAIProvider, GroqProvider, CoHereProvider
│   └── vectordb/providers/  # QdrantDBProvider, PGVectorProvider
├── utils/
│   ├── security.py          # verify_api_key FastAPI dependency
│   └── backend_client.py    # BackendApiClient (REST to Node.js backend, in-memory cache)
└── helpers/config.py        # Pydantic Settings (loads src/.env)
```

### Prompt Templates

Python files in `stores/llm/templates/locales/{en,ar}/`. Keys: `"rag"` (system_prompt, footer_prompt), `"workflow"` (classification prompts), `"relevance_grading"` (grader prompts). Language set per-request via `TemplateParser.set_language()`.

### Docker Stack (12 services)

`fastapi` (8000), `nginx` (80), `celery-worker`, `celery-beat`, `flower` (5556), `pgvector` (5433), `qdrant` (6333/6334), `rabbitmq` (5672/15672), `redis` (6379), `prometheus` (9090), `grafana` (3000), `node-exporter` (9100).

---

## MasarX Agent (`F:\MasarX_A`)

### Dev Commands

```bash
# All from src/
cd src

# API server
uvicorn main:app --reload --port 8000

# Celery worker
python -m celery -A celery_app worker --loglevel=info

# Celery Beat (scheduled autonomous tasks)
python -m celery -A celery_app beat --loglevel=info

# Full Docker stack
cd docker && docker compose up -d
cd docker && docker compose down

# Database migrations
alembic upgrade head
```

### Environment (`src/.env`)

Key variables:

| Variable                                                            | Purpose                                                            |
| ------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `POSTGRES_URL`                                                      | Async PG URL (`postgresql+asyncpg://...`) for main DB              |
| `PGVECTOR_URL`                                                      | Async PG URL for vector search (same DB, Connexios tables)         |
| `GROQ_API_KEY`                                                      | Primary LLM                                                        |
| `GENERATION_MODEL_ID` / `UTILITY_MODEL_ID`                          | Model IDs                                                          |
| `EMBEDDING_BACKEND` / `EMBEDDING_MODEL_ID` / `EMBEDDING_MODEL_SIZE` | For RAGTool                                                        |
| `HITL_SECRET_KEY`                                                   | Signs HITL approval tokens                                         |
| `HITL_TOKEN_TTL_MINUTES`                                            | Approval token lifetime                                            |
| `GITHUB_TOKEN`                                                      | For GitHub tool                                                    |
| `TAVILY_API_KEY`                                                    | Web search tool                                                    |
| `LANGSMITH_API_KEY`                                                 | Optional tracing                                                   |
| `DB_FAIL_FAST`                                                      | If true, exit on DB init failure                                   |
| `JWT_SECRET`                                                        | **To add (Phase 2):** shared secret for service token verification |

### Architecture — LangGraph Supervisor

MasarX uses a supervisor + subgraph multi-graph pattern. The `WorkflowController` compiles and routes state to one of 7 specialized subgraphs.

**`MasarXState` TypedDict (21 fields):**

- Routing: `intent`, `subgraph_target`
- Context: `project_id`, `sprint_id`, `user_id`, `member_ids`
- Invocation: `invocation_id`, `triggered_by`, `actor`, `thread_id`
- HITL: `pending_plan`, `plan_approved`, `approval_token`, `approval_expires`
- RAG: `retrieved_context`
- Output: `output`, `draft_content`, `draft_status`
- Tracking: `last_risk_scan_at`, `last_readme_generated_at`
- `error`, `parallel_results`

**7 Subgraphs:**

| Subgraph          | File                            | Intents                                                        |
| ----------------- | ------------------------------- | -------------------------------------------------------------- |
| Task              | `task_subgraph.py`              | `create_tasks` (HITL-gated)                                    |
| Team              | `team_subgraph.py`              | `match_team`, `onboard_member`, `refine_recommender`           |
| Doc               | `doc_subgraph.py`               | `generate_readme`, `generate_milestone_doc`, `generate_retro`  |
| Monitor           | `monitor_subgraph.py`           | `detect_risks`, `monitor_workload`                             |
| PR Translator     | `pr_translator_subgraph.py`     | `translate_pr`                                                 |
| Skill Endorsement | `skill_endorsement_subgraph.py` | `endorse_skills`                                               |
| Audit             | `audit_subgraph.py`             | `comprehensive_audit` (runs readme + risks + team in parallel) |

### API Surface (`src/Routes/webhook_routes.py`)

All routes under `/api/v1/masarx/`. **Currently no auth — Phase 2 adds JWT verification.**

```
POST /webhook/event/{event_type}/{project_id}   Fire-and-forget; returns 202 immediately
GET  /webhook/results/{project_id}              Get all stored webhook results
GET  /webhook/result/{project_id}/{event_type}  Get latest result for one event type
POST /agent/comprehensive_audit/{project_id}    Blocking audit (waits for completion)
POST /agent/{intent}/{project_id}               Manual trigger (waits for completion)
POST /approval/{approval_token}                 Submit HITL decision (approve/reject)
```

**Event → Intent mapping:**

| Event                    | Intent                   |
| ------------------------ | ------------------------ |
| `user.joined_platform`   | `match_team`             |
| `user.joined_project`    | `onboard_member`         |
| `project.sprint_started` | `create_tasks`           |
| `task.completed`         | `endorse_skills`         |
| `sprint.closed`          | `generate_retro`         |
| `milestone.completed`    | `generate_milestone_doc` |
| `pullrequest.merged`     | `translate_pr`           |
| `project.closed`         | `generate_readme`        |

### HITL Flow

1. `create_tasks` intent runs → LLM generates a task plan → saves `PendingPlan` to DB with signed `approval_token` + expiry
2. Response includes `approval_token`
3. Backend surfaces approval decision to user
4. User submits `POST /approval/{token}` with `{"approved": true/false}`
5. MasarX resumes the LangGraph checkpoint from the interrupt point

### RAGTool — Reading Connexios Vector Tables

`src/stores/vectordb/rag_tool.py` queries Connexios's `collection_{size}_{project_id}` tables directly via `PGVECTOR_URL` (same Neon DB). Uses cosine similarity (`<=>` operator). Does NOT go through the Connexios API — reads the shared PG tables directly.

This only works correctly when both services point to the same PostgreSQL instance.

### Database Models (`src/models/db_schemas/live_models.py`)

MasarX-owned tables: `user`, `task`, `masarx_notifications`, `masarx_pending_plans`

Shared tables (Connexios owns schema): `projects`, `chunks`

MasarX's `DataChunk` model is missing `chunk_asset_id` and `updated_at` — must be added before shared DB migration (Phase 1.2). MasarX must NOT run `create_all` for `chunks` or `projects`.

### Autonomous Scheduled Tasks (Celery Beat)

- Daily motivational quotes (fully autonomous)
- Weekly sprint digests (fully autonomous)
- Workload alerting (fully autonomous)
- Risk scans (triggered on demand or scheduled)

### Module Map

```
src/
├── main.py                          # Startup: DB + LLM clients + LangSmith
├── Routes/
│   ├── base.py                      # /health
│   └── webhook_routes.py            # All MasarX endpoints
├── controllers/
│   ├── WorkflowController.py        # LangGraph supervisor compilation + routing
│   └── subgraphs/                   # 7 compiled subgraphs
├── models/
│   ├── db_schemas/live_models.py    # SQLAlchemy ORM (User, Project, Task, DataChunk, Notification, PendingPlan)
│   └── schemas/                     # Pydantic state + output schemas
├── stores/
│   ├── llm/                         # LLMProviderFactory (Groq, OpenAI, Ollama)
│   ├── memory/                      # LangGraph checkpointers (PG, SQLite, in-memory)
│   └── vectordb/rag_tool.py         # RAGTool: reads Connexios PGVector tables directly
├── tasks/
│   └── cron_jobs.py                 # Celery Beat scheduled tasks
└── utils/
    ├── tools/                       # db_tool, github_tool, email_tool, tavily_tool, wolfram_tool
    └── prompts/                     # 8 prompt templates per subgraph domain
```

---

## Integration Phases — Status Tracker

| Phase | Description                                                    | Status                                  |
| ----- | -------------------------------------------------------------- | --------------------------------------- |
| **1** | Shared PostgreSQL (Neon.tech), schema alignment, env updates   | Pending                                 |
| **2** | JWT bridge — Node.js → MasarX service token auth               | Pending                                 |
| **3** | Backend → MasarX: `aiService.js` + event wiring                | Pending                                 |
| **4** | Backend → RAG: `upload-and-process` endpoint + `projects/sync` | ✅ Done                                 |
| **5** | Deploy both Python services to HF Spaces                       | ✅ Done (MasarX ✅, RAG DB fix pending) |
| **6** | End-to-end testing                                             | Pending                                 |

**Phase 5 notes:**

- MasarX Agent (ConnexioAgent): ✅ Fully operational — PostgreSQL ✅, LLM ✅, Celery ✅
- Connexios RAG (ConnexioRag): Celery ✅, LLM ✅ — DB still timing out. Fix: set `POSTGRES_PORT=5432` in HF Space secrets (was 5433).

**Target hosting:** Node.js stays on Hostinger. Both Python services → Hugging Face Spaces (Docker SDK). PostgreSQL → Neon.tech free tier. Add keepalive cron pings (cron-job.org, free) to prevent HF Spaces sleep.

**Do not make Node.js backend changes (Phases 3–4.3/4.4) until Connexios RAG DB connection is confirmed working.**

---

## Node.js Backend Reference (`github.com/Hassan19Z/Connexio-backend`)

Key files for integration work:

| File                                          | Relevance                                                                                          |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `bootstrap.js`                                | All routes: `/api/auth`, `/api/users`, `/api/tasks`, `/api/projects`, `/api/posts`, `/api/friends` |
| `database/dbconnection.js`                    | Full MySQL schema — canonical source of user/project/task structure                                |
| `middleware/authMiddleware.js`                | JWT decode: `{ UID, email, user_type }` from `JWT_SECRET`                                          |
| `modules/fileUpload/fileUpload.controller.js` | Project file upload — will call RAG after saving                                                   |
| `services/aiService.js`                       | **To create (Phase 3):** calls MasarX + RAG                                                        |
| `modules/ai/ai.routes.js`                     | **To create (Phase 3):** proxy routes for chat + agent triggers                                    |

`BackendApiClient` in Connexios calls these backend paths (must verify exact routes match):

- `GET /api/users/{user_id}`
- `GET /api/projects/{project_id}`
- `GET /api/projects/{project_id}/members`
- `GET /api/tasks?project_id={project_id}`
