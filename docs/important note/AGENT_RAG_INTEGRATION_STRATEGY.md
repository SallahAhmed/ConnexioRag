# Connexio Full-Stack Integration: Master Blueprint

> **Created:** 2026-05-11 | **Updated:** 2026-05-12 | **Status:** Phase 1–2 ✅ | Phase 3 ⏳ Waiting (Hassan) | Phase 4.1–4.2 ✅ | Phase 4.3–4.4 ⏳ Waiting (Hassan) | Phase 5 ✅ (RAG DB fix pending: set POSTGRES_PORT=5432 in HF Space) | Phase 6 ⏳
> **Author:** Sallah Ahmed (AI Agent & RAG Model Developer)
> **Purpose:** Single source of truth for integrating ALL Connexio components. Any AI tool or developer reading this has enough context to continue the work without asking repeated questions.

---

## TABLE OF CONTENTS

1. [System Overview & Components](#1-system-overview--components)
2. [Finalized Decisions Log](#2-finalized-decisions-log)
3. [Account & Infrastructure Setup](#3-account--infrastructure-setup)
4. [Repository Map & Critical Files](#4-repository-map--critical-files)
5. [Database Schema & Ownership](#5-database-schema--ownership)
6. [Integration Plan — Phase by Phase](#6-integration-plan--phase-by-phase)
7. [Open Questions](#7-open-questions)

---

## 1. SYSTEM OVERVIEW & COMPONENTS

Connexio is a **collaborative project management platform with AI-powered assistance**. It has 4 components:

### Component A: Node.js Backend (Core API) — DEPLOYED

- **Repo:** `https://github.com/Hassan19Z/Connexio-backend`
- **Tech:** Express.js, MySQL, MongoDB, Socket.IO, JWT Auth
- **Live URL:** `connexio.icu` (Hostinger shared hosting)
- **Role:** Auth, users, projects, tasks, friends, chat, file upload. ALL user-facing operations.
- **Auth:** JWT tokens signed with `JWT_SECRET`, payload: `{ UID, email, user_type }`
- **API docs:** Postman — `https://documenter.getpostman.com/view/32810992/2sBXqMJzSY`

### Component B: Connexios RAG (Knowledge Engine) — ✅ DEPLOYED (HF Spaces: ConnexioRag)

- **Path:** `C:\Users\salla\Connexios`
- **Tech:** Python, FastAPI, LangChain, PostgreSQL + PGVector, Celery + RabbitMQ, Groq
- **Role:** Document ingestion, vector indexing, hybrid search (RRF), intent detection, Corrective RAG (Wikipedia/Google/GitHub/Python fallback), multi-persona chat with SSE streaming.
- **Deploy target:** Hugging Face Spaces (Docker SDK)

### Component C: MasarX Agent (Autonomous PM) — ✅ DEPLOYED (HF Spaces: ConnexioAgent)

- **Path:** `F:\MasarX_A`
- **Tech:** Python, FastAPI, LangGraph (multi-subgraph supervisor), PostgreSQL, Celery
- **Role:** Task creation (HITL-gated), team matching, README generation, sprint retros, risk detection, PR translation, skill endorsement, comprehensive audits. Autonomous scheduled tasks via Celery Beat.
- **Deploy target:** Hugging Face Spaces (Docker SDK)

### Component D: Frontend — NOT STARTED

- Will be the final integration layer once the three backends are fully connected.
- Integration deferred until Node.js + RAG + Agent are production-ready.

### Target Architecture

```
Browser / Frontend (TBD)
        │
        ▼
Node.js Backend  ←──── connexio.icu (Hostinger, already deployed)
Express + MySQL
        │
        ├── X-API-Key ──────────────────► Connexios RAG  (HF Spaces)
        │   POST /api/v1/data/upload-and-process/{pid}
        │   POST /api/v1/nlp/agent/chat/{pid}
        │   GET  /api/v1/nlp/agent/chat/stream/{pid}
        │   POST /api/v1/projects/sync
        │
        └── Service JWT ─────────────────► MasarX Agent  (HF Spaces)
            POST /api/v1/masarx/webhook/event/{type}/{pid}   (fire-and-forget)
            POST /api/v1/masarx/agent/{intent}/{pid}
            POST /api/v1/masarx/approval/{token}

Both Python services share ONE PostgreSQL database (Neon.tech):
  Connexios owns:  projects, assets, chunks, rag_chat_sessions, collection_{size}_{pid}
  MasarX owns:     masarx_notifications, masarx_pending_plans, user, task
  MasarX reads:    projects, chunks  (read-only, schema owned by Connexios)
```

---

## 2. FINALIZED DECISIONS LOG

All questions resolved. These decisions are FINAL and must be followed during implementation.

| #   | Question                         | Decision                                                          | Rationale                                                                                                                                                          |
| --- | -------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | **Project ID sync strategy**     | Mapping table `project_id_map` in PostgreSQL                      | Production-safe. No forced sequence manipulation. Maps `mysql_pid → pg_project_id`.                                                                                |
| 2   | **File upload → RAG indexing**   | Fire-and-forget via `asyncio.create_task` (no Celery for Phase 1) | Avoids HTTP timeout on large files. RAG returns `202 Accepted` immediately. Celery added in Phase 4 if needed.                                                     |
| 3   | **Backend → MasarX auth**        | Short-lived service JWT token                                     | Backend signs `{ uid, project_id, intent, iat, exp: +5min }` with `JWT_SECRET`. Never forwards user's own JWT to MasarX.                                           |
| 4   | **Corrective RAG web fallback**  | Keep enabled                                                      | Already working. Adds value. Disable later if API costs become an issue.                                                                                           |
| 5   | **Celery for Phase 1**           | Skip (graceful non-fatal startup)                                 | Celery startup in Connexios must not crash the FastAPI process if RabbitMQ is unavailable on Hugging Face Spaces.                                                  |
| 6   | **MasarX `create_all` scope**    | Only MasarX-owned tables                                          | MasarX must NOT run `create_all` for `projects` or `chunks`. Connexios's Alembic owns those.                                                                       |
| 7   | **File storage after indexing**  | Backend keeps local copy, RAG discards                            | Backend serves files to users. RAG's HF Space filesystem is ephemeral. Backend reads saved file → forwards as multipart to RAG → RAG indexes and returns.          |
| 8   | **Cron jobs (MasarX)**           | Placeholder code — defer to Phase 4                               | Not yet implemented. Celery Beat skipped for Phase 1.                                                                                                              |
| 9   | **Frontend**                     | Deferred — integrate last                                         | Not started. All backend integration first.                                                                                                                        |
| 10  | **Rate limiting**                | Not needed for now                                                | Testing phase only, no large user base expected.                                                                                                                   |
| 11  | **MasarX webhook events**        | Fire-and-forget (already implemented)                             | `BackgroundTasks` pattern already in `webhook_routes.py`. Returns `202` immediately.                                                                               |
| 12  | **HF Spaces sleep prevention**   | Keepalive ping via cron-job.org (free)                            | Both HF Spaces ping their `/health` endpoint every 10 minutes to prevent inactivity sleep.                                                                         |
| 13  | **Backend API routes**           | ✅ Verified against GitHub source                                 | Routes confirmed. One bug found and fixed: tasks route was wrong (see Section 4 fix).                                                                              |
| 14  | **Embedding for production**     | ✅ Switch to Cohere `embed-multilingual-v3.0`                     | Local Ollama (`bge-m3`) won't exist on Render. Cohere: same 1024 dims, Arabic support, free tier, already implemented in Connexios. Both services switch together. |
| 15  | **File handling after indexing** | ✅ Backend keeps copy, forwards to RAG                            | Backend saves locally (for user downloads), reads file, POSTs multipart to RAG's `upload-and-process` endpoint. RAG indexes and discards.                          |

---

## 3. ACCOUNT & INFRASTRUCTURE SETUP

Do these steps IN ORDER before writing any code. Check each one off as done.

### Step 3.1 — Neon.tech (PostgreSQL)

1. Go to [neon.tech](https://neon.tech) → Sign up (free, no credit card)
2. Create a new **Project** → name it `connexio`
3. Inside the project, create a **Database** → name it `connexio`
4. Open the **SQL Editor** and run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   ```
5. Go to **Dashboard → Connection Details**
6. Copy the connection string in **"Connection string"** format. You need two variants:
   - **Connexios format** (individual params): host, port, user, password, database
   - **MasarX format** (full URL): `postgresql+asyncpg://user:pass@host/connexio?sslmode=require`
7. Save the connection string — you'll need it for both `.env` files.

### Step 3.2 — GitHub Repos for Python Services

Both Connexios and MasarX need to be on GitHub before Hugging Face Spaces can deploy them.

> ⚠️ **Security check first:** Confirm `.env` is listed in `.gitignore` on BOTH repos before pushing.

1. Create two **private** repos on GitHub:
   - `connexios-rag`
   - `masarx-agent`
2. Each repo needs a `Dockerfile` at the root and a `README.md` with HF Space frontmatter — these are created in Phase 5.1 before pushing.
3. Push the local code:

   ```bash
   # Connexios
   cd C:\Users\salla\Connexios
   git remote add origin https://github.com/<your-username>/connexios-rag.git
   git push -u origin main

   # MasarX
   cd F:\MasarX_A
   git remote add origin https://github.com/<your-username>/masarx-agent.git
   git push -u origin main
   ```

### Step 3.3 — Hugging Face Spaces (Python Services Hosting — No Card Required)

**Why Hugging Face Spaces:** Free, no credit card, no account verification. Runs Docker containers with 2 vCPU + 16GB RAM on the free tier — more resources than Render or Koyeb free tiers. Spaces do sleep after extended inactivity but keepalive pings (Step 3.5) prevent this.

Do this AFTER Step 3.2 (GitHub repos must exist first).

1. Go to [huggingface.co](https://huggingface.co) → Sign up (free, no credit card)
2. Create **Space #1** — "connexios-rag":
   - Click **"New Space"** → name it `connexios-rag`
   - SDK: **Docker**
   - Visibility: **Public** (free tier is public — OK since endpoints are protected by X-API-Key)
   - Click **"Create Space"**
   - Go to **Settings → Repository secrets** and add all production environment variables (Phase 5.1)
   - Connect to GitHub: Settings → "Link to a GitHub repository" → select `connexios-rag`
3. Create **Space #2** — "masarx-agent":
   - Same steps → name `masarx-agent` → SDK: Docker → Public
   - Add environment variables in Settings → Repository secrets (Phase 5.1)
   - Connect to `masarx-agent` GitHub repo
4. Public Space URLs format: `https://<username>-connexios-rag.hf.space` and `https://<username>-masarx-agent.hf.space`
5. Do NOT set environment variables yet — do that as part of Phase 5.

> **Note:** Spaces are public — anyone can call the URLs. This is fine because all RAG endpoints require `X-API-Key` and all MasarX endpoints will require the service JWT. Unauthenticated calls return `401`.

### Step 3.4 — Cohere (Production Embedding API)

The local Ollama embedding (`bge-m3`) does not exist on Hugging Face Spaces. Both Python services must switch to Cohere for production.

1. Go to [cohere.com](https://cohere.com) → Sign up (free, no credit card)
2. Go to **API Keys** → create a key named `connexio-production`
3. Copy the key — you will add it to the HF Space secrets in Phase 5
4. The embedding config to use for production:

   ```env
   EMBEDDING_BACKEND=COHERE
   EMBEDDING_MODEL_ID=embed-multilingual-v3.0
   EMBEDDING_MODEL_SIZE=1024
   ```

   > Note: `embed-multilingual-v3.0` is 1024 dimensions — no schema changes needed. Supports both English and Arabic.

5. Since no production data is indexed yet, switching models is clean — all indexing on Neon starts fresh with Cohere embeddings.

> **Keep the local `.env` as-is** with Ollama for local development. Only the HF Space uses Cohere — set `EMBEDDING_BACKEND=COHERE` only in HF Space secrets (Phase 5), not locally.

### Step 3.5 — cron-job.org (Keepalive Pings)

HF Spaces can sleep after extended inactivity. Prevent this with free keepalive pings.

Do this AFTER Step 3.3 (need the Space URLs).

1. Go to [cron-job.org](https://cron-job.org) → Sign up (free, no card)
2. Create two cron jobs pinging every 10 minutes:
   - `https://<username>-connexios-rag.hf.space/health`
   - `https://<username>-masarx-agent.hf.space/api/v1/masarx/health`

---

## 4. REPOSITORY MAP & CRITICAL FILES

### Node.js Backend — Verified API Routes

Full route list confirmed from GitHub source:

**Users** (`/api/users`) — all public:

- `GET /api/users/:id` — get user profile
- `GET /api/users/` — list users
- `GET /api/users/stats/:id` — user stats

**Projects** (`/api/projects`) — all require auth:

- `POST /api/projects` — create project → returns object with `PID` field (MySQL auto-increment)
- `GET /api/projects/:id` — get project (returns members[], total_tasks, completed_tasks, githubDetails)
- `GET /api/projects/:id/members` — get members (returns UID, FullName, email, photo, rate, role, joined_at)
- `PUT /api/projects/:id` — update project
- `DELETE /api/projects/:id` — delete project

**Tasks** (`/api/tasks`) — all require auth:

- `GET /api/tasks/project/:projectId` — ⚠️ get tasks by project (NOT `?project_id=` query param — BackendApiClient bug)
- `POST /api/tasks` — create task
- `GET /api/tasks/:id` — get single task
- `PUT /api/tasks/:id` — update task

**File Upload** (`/api/upload`) — all require auth:

- `POST /api/upload/project-file` — upload project file → returns metadata + file path. Hook point for Phase 4.3.

### Node.js Backend — Files to Touch During Integration

| File                                          | Change Needed                                                                   |
| --------------------------------------------- | ------------------------------------------------------------------------------- |
| `bootstrap.js`                                | Register new AI routes: `/api/ai`                                               |
| `modules/ai/ai.routes.js`                     | **CREATE** — proxy routes for chat + agent                                      |
| `services/aiService.js`                       | **CREATE** — calls Connexios RAG + MasarX Agent                                 |
| `modules/fileUpload/fileUpload.controller.js` | In `uploadProjectFile` function: after `saveFileLocally`, forward to RAG        |
| `modules/projects/projects.controller.js`     | In `createProject` function: after MySQL INSERT succeeds, call RAG project sync |
| `.env`                                        | Add: `RAG_SERVICE_URL`, `AI_AGENT_URL`, `CONNEXIO_RAG_API_KEY`, `JWT_SECRET`    |
| `middleware/authMiddleware.js`                | Reference only — JWT decode logic for service token signing                     |

### Connexios RAG — Files to Create / Modify

| File                                                       | Change                                                                                         |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `src/Routes/data.py`                                       | **ADD** `POST /api/v1/data/upload-and-process/{pid}` — fire-and-forget embedding endpoint      |
| `src/Routes/data.py`                                       | **ADD** `POST /api/v1/projects/sync` — creates PG project record with explicit MySQL PID       |
| `src/models/db_schemas/connexio/schemas/project_id_map.py` | **CREATE** mapping table schema                                                                |
| `src/main.py`                                              | Make Celery import non-fatal (try/except) — required for HF Spaces (no RabbitMQ broker)        |
| `src/utils/backend_client.py`                              | **BUG FIX** — change task route from `/api/tasks?project_id={id}` to `/api/tasks/project/{id}` |
| `src/.env` (local)                                         | `MAIN_BACKEND_URL` → `https://connexio.icu` (currently wrong Docker-internal URL)              |
| `src/.env` (local)                                         | `EMBEDDING_BACKEND=COHERE`, `EMBEDDING_MODEL_ID=embed-multilingual-v3.0`, add `COHERE_API_KEY` |
| `Dockerfile` (root)                                        | **CREATE** — required for HF Spaces Docker SDK recognition                                     |
| HF Space secrets                                           | All vars from Phase 5.1 — use Neon PG, Cohere embedding, production URLs                       |

### MasarX Agent — Files to Create / Modify

| File                                   | Change                                                                                              |
| -------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `src/models/db_schemas/live_models.py` | Add `chunk_asset_id` + `updated_at` to `DataChunk`. Scope `create_all` to MasarX-owned tables only. |
| `src/utils/auth.py`                    | **CREATE** — service JWT verification dependency                                                    |
| `src/helpers/config.py`                | Add `JWT_SECRET: Optional[str] = None`                                                              |
| `src/Routes/webhook_routes.py`         | Apply JWT auth dependency to all routes                                                             |
| `src/.env` (local)                     | `POSTGRES_URL` and `PGVECTOR_URL` → Neon URLs (currently wrong separate local DB)                   |
| `src/.env` (local)                     | `EMBEDDING_BACKEND=COHERE`, `EMBEDDING_MODEL_ID=embed-multilingual-v3.0`, add `COHERE_API_KEY`      |
| `src/.env` (local)                     | Add `JWT_SECRET` (Phase 2)                                                                          |
| `Dockerfile` (root)                    | **CREATE** — required for HF Spaces Docker SDK recognition                                          |
| HF Space secrets                       | All vars from Phase 5.1                                                                             |

### Security Checklist — Before Any GitHub Push

- [ ] `src/.env` is in `.gitignore` for BOTH repos (Connexios and MasarX)
- [ ] `docker/env/*.env.*` files are in `.gitignore` for Connexios
- [ ] Verify with `git status` before first push — no `.env` files should appear as untracked

---

## 5. DATABASE SCHEMA & OWNERSHIP

### Two Databases

| Database                   | Engine                   | Owner               | Purpose                                                         |
| -------------------------- | ------------------------ | ------------------- | --------------------------------------------------------------- |
| **MySQL** (Hostinger)      | MySQL 8.x                | Node.js Backend     | All user-facing data: users, projects, tasks, friends, chat     |
| **PostgreSQL** (Neon.tech) | PostgreSQL 17 + PGVector | Connexios (Alembic) | RAG indexing, chat sessions, vector collections, AI agent state |

### PostgreSQL Table Ownership Rules

| Table                     | Owned By                | Notes                                                                     |
| ------------------------- | ----------------------- | ------------------------------------------------------------------------- |
| `projects`                | **Connexios (Alembic)** | MasarX reads only. `project_id` must equal MySQL `PID` via sync endpoint. |
| `assets`                  | **Connexios (Alembic)** | Uploaded file metadata                                                    |
| `chunks`                  | **Connexios (Alembic)** | Text chunks. MasarX model must match schema exactly.                      |
| `rag_chat_sessions`       | **Connexios (Alembic)** | Per-user chat history                                                     |
| `collection_{size}_{pid}` | **Connexios (runtime)** | Dynamic vector tables, one per project                                    |
| `project_id_map`          | **Connexios (Alembic)** | Maps `mysql_pid → pg_project_id`. Created in Phase 1.                     |
| `user`                    | **MasarX (create_all)** | AI agent's user model                                                     |
| `task`                    | **MasarX (create_all)** | AI agent's task model                                                     |
| `masarx_notifications`    | **MasarX (create_all)** | In-app notifications                                                      |
| `masarx_pending_plans`    | **MasarX (create_all)** | HITL approval state                                                       |

### DataChunk Model — Required Fix (Phase 1.2)

MasarX's `DataChunk` is missing two columns that Connexios's schema has. Must be added to `live_models.py` before shared DB migration:

```python
chunk_asset_id = Column(Integer, nullable=True)   # no FK — assets table is Connexios-only
updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### Project ID Sync — Mapping Table

```sql
CREATE TABLE project_id_map (
    id          SERIAL PRIMARY KEY,
    mysql_pid   INTEGER NOT NULL UNIQUE,   -- PID from Node.js backend
    pg_pid      INTEGER NOT NULL UNIQUE,   -- project_id in PostgreSQL
    synced_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

When the backend calls `POST /api/v1/projects/sync`, Connexios:

1. Inserts a row into `projects` with `project_id = mysql_pid` (explicit, bypassing sequence)
2. Inserts a mapping row into `project_id_map`

All subsequent calls use `mysql_pid` directly as `project_id` in both Python services.

---

## 6. INTEGRATION PLAN — PHASE BY PHASE

### PHASE 1 — Shared Database Foundation ✅ COMPLETE

**Goal:** Both Python services connected to Neon.tech PostgreSQL. Schemas aligned.
**Prerequisite:** Section 3.1 (Neon.tech) complete.

#### 1.1 — Fix MasarX DataChunk Model ✅

**File:** `F:\MasarX_A\src\models\db_schemas\live_models.py`

- Add `chunk_asset_id` and `updated_at` to `DataChunk` (see Section 5)
- Scope `Base.metadata.create_all` in `main.py` to MasarX-owned tables ONLY:
  ```python
  MASARX_OWNED_TABLES = {"user", "task", "masarx_notifications", "masarx_pending_plans"}
  tables_to_create = [t for t in Base.metadata.sorted_tables if t.name in MASARX_OWNED_TABLES]
  await conn.run_sync(lambda conn: Base.metadata.create_all(conn, tables=tables_to_create))
  ```

#### 1.2 — Add project_id_map Schema to Connexios ✅

**File:** `C:\Users\salla\Connexios\src\models\db_schemas\connexio\schemas\project_id_map.py`

Create the `ProjectIDMap` SQLAlchemy model (see Section 5). Add it to Alembic and generate a migration.

#### 1.3 — Update .env Files (Both Services) ✅

Update both `.env` files to point to Neon.tech. Run each service startup locally and confirm no DB errors.

#### 1.4 — Run Connexios Alembic Migrations Against Neon ⏳ PENDING

```bash
cd C:\Users\salla\Connexios\src
alembic upgrade head
```

This creates: `projects`, `assets`, `chunks`, `rag_chat_sessions`, `project_id_map`.

MasarX creates its own tables on startup (`user`, `task`, `masarx_notifications`, `masarx_pending_plans`).

#### 1.5 — Make Celery Startup Non-Fatal in Connexios ✅

In `src/celery_app.py` and any Celery imports in tasks, wrap with try/except so a missing RabbitMQ broker only logs a warning and does not crash the FastAPI process. This is required for Render deployment where no Celery broker runs.

---

### PHASE 2 — JWT Bridge (MasarX Auth) ✅ COMPLETE

**Goal:** MasarX verifies service tokens issued by the Node.js backend.

#### 2.1 — Add JWT_SECRET to MasarX Config ✅

**File:** `F:\MasarX_A\src\helpers\config.py`

```python
JWT_SECRET: Optional[str] = None
```

#### 2.2 — Create Auth Utility ✅

**New file:** `F:\MasarX_A\src\utils\auth.py`

```python
import jwt
from fastapi import Header, HTTPException, status
from helpers.config import get_settings

async def verify_service_token(authorization: str = Header(None)) -> dict:
    settings = get_settings()
    if not settings.JWT_SECRET:
        return {}  # dev bypass — same pattern as Connexios X-API-Key
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing service token")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload  # { uid, project_id, intent, iat, exp }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Service token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid service token")
```

#### 2.3 — Apply Auth to MasarX Router ✅

**File:** `F:\MasarX_A\src\Routes\webhook_routes.py`

Add `dependencies=[Depends(verify_service_token)]` to the router definition (same pattern as Connexios).

#### 2.4 — Add JWT_SECRET to MasarX .env ⏳ PENDING (add to HF Space secrets)

Same value as `JWT_SECRET` in the Node.js backend `.env`.

---

### PHASE 3 — Backend → MasarX Integration ⏳ WAITING (Hassan — do after RAG DB confirmed working)

**Goal:** Node.js backend can fire events to MasarX and proxy HITL decisions.

#### 3.1 — Create aiService.js ⏳ HASSAN

**New file:** `Connexio-backend/services/aiService.js`

```javascript
import axios from "axios";
import jwt from "jsonwebtoken";

const AI_AGENT_URL = process.env.AI_AGENT_URL;
const RAG_SERVICE_URL = process.env.RAG_SERVICE_URL;
const JWT_SECRET = process.env.JWT_SECRET;
const CONNEXIO_RAG_API_KEY = process.env.CONNEXIO_RAG_API_KEY;

// Creates a short-lived service token (5 min). Never forwards user's JWT.
function makeServiceToken(uid, projectId, intent) {
  return jwt.sign({ uid, project_id: projectId, intent }, JWT_SECRET, {
    expiresIn: "5m",
  });
}

// Fire-and-forget — returns 202 immediately, no await on result
export const fireEvent = async (eventType, projectId, uid, payload = {}) => {
  const token = makeServiceToken(uid, projectId, eventType);
  await axios.post(
    `${AI_AGENT_URL}/api/v1/masarx/webhook/event/${eventType}/${projectId}`,
    payload,
    { headers: { Authorization: `Bearer ${token}` }, timeout: 10000 },
  );
};

// Blocking call — used only for intents the user waits for
export const triggerIntent = async (intent, projectId, uid, payload = {}) => {
  const token = makeServiceToken(uid, projectId, intent);
  const response = await axios.post(
    `${AI_AGENT_URL}/api/v1/masarx/agent/${intent}/${projectId}`,
    payload,
    { headers: { Authorization: `Bearer ${token}` }, timeout: 120000 },
  );
  return response.data;
};

// Forward HITL approval decision from user
export const submitApproval = async (approvalToken, approved) => {
  const response = await axios.post(
    `${AI_AGENT_URL}/api/v1/masarx/approval/${approvalToken}`,
    { approved },
  );
  return response.data;
};

// Proxy RAG chat (non-streaming)
export const ragChat = async (projectId, query, userId, persona, apiKey) => {
  const response = await axios.post(
    `${RAG_SERVICE_URL}/api/v1/nlp/agent/chat/${projectId}`,
    { query, user_id: userId, persona },
    { headers: { "x-api-key": apiKey }, timeout: 30000 },
  );
  return response.data;
};
```

#### 3.2 — Wire Backend Events ⏳ HASSAN

Add `fireEvent` calls in existing backend controllers at these moments:

| Backend Action          | File to Edit                | Event to Fire            |
| ----------------------- | --------------------------- | ------------------------ |
| New user signs up       | `auth.controller.js`        | `user.joined_platform`   |
| User joins project      | `projects controller`       | `user.joined_project`    |
| Sprint starts           | `projects/tasks controller` | `project.sprint_started` |
| Task marked complete    | `tasks controller`          | `task.completed`         |
| Sprint closed           | `tasks/projects controller` | `sprint.closed`          |
| Milestone completed     | `tasks controller`          | `milestone.completed`    |
| PR merged (if tracked)  | GitHub webhook handler      | `pullrequest.merged`     |
| Project closed/archived | `projects controller`       | `project.closed`         |

#### 3.3 — Create AI Routes in Backend ⏳ HASSAN

**New file:** `Connexio-backend/modules/ai/ai.routes.js`

```javascript
router.post("/chat/:projectId", authMiddleware, async (req, res) => {
  // Proxy to Connexios RAG, non-streaming
});

router.get("/chat/stream/:projectId", authMiddleware, async (req, res) => {
  // Proxy SSE stream from Connexios RAG
  // Set headers: Content-Type: text/event-stream
  // Pipe the axios stream directly to res
});

router.post("/agent/:intent/:projectId", authMiddleware, async (req, res) => {
  // Trigger MasarX intent, wait for result
});

router.post("/approval/:token", authMiddleware, async (req, res) => {
  // Forward HITL decision to MasarX
});
```

Register in `bootstrap.js`: `app.use("/api/ai", aiRoutes)`

#### 3.4 — Add Backend .env Variables ⏳ HASSAN

```env
AI_AGENT_URL=https://<hf-username>-masarx-agent.hf.space
RAG_SERVICE_URL=https://<hf-username>-connexios-rag.hf.space
CONNEXIO_RAG_API_KEY=<same value as CONNEXIO_INTERNAL_API_KEY in Connexios .env>
JWT_SECRET=<same value as JWT_SECRET>
```

---

### PHASE 4 — Backend → RAG Integration (4.1–4.2 ✅ | 4.3–4.4 ⏳ HASSAN)

**Goal:** File uploads are automatically indexed. Projects are synced.

#### 4.1 — Create upload-and-process Endpoint (Connexios) ✅

**File:** `C:\Users\salla\Connexios\src\Routes\data.py`

New endpoint: `POST /api/v1/data/upload-and-process/{project_id}` (X-API-Key protected)

Behavior:

1. Accept `multipart/form-data`: `file` + `chunk_size` + `overlap_size` + `do_reset`
2. Save file + create `Asset` record (sync)
3. Return `{"status": "accepted", "file_id": "..."}` with HTTP `202`
4. In `asyncio.create_task(...)`: chunk → embed → push to PGVector

The background task uses the logic already in `tasks/file_processing.py` and `tasks/data_indexing.py` but called directly (no Celery broker needed).

#### 4.2 — Create project-sync Endpoint (Connexios) ✅

**File:** `C:\Users\salla\Connexios\src\Routes\data.py`

New endpoint: `POST /api/v1/projects/sync` (X-API-Key protected)

Body: `{ "pid": 5, "name": "Project Alpha", "description": "..." }`

Behavior:

1. INSERT into `projects` with explicit `project_id = pid` (bypass sequence using `INSERT ... ON CONFLICT DO NOTHING`)
2. INSERT into `project_id_map`
3. Return `{"project_id": 5, "status": "synced"}`

#### 4.3 — Wire Backend File Upload ⏳ HASSAN

**File:** `Connexio-backend/modules/fileUpload/fileUpload.controller.js`

After `uploadProjectFile` saves the file locally:

```javascript
// Read the saved file and forward to RAG for indexing
const fileBuffer = fs.readFileSync(savedFilePath);
const formData = new FormData();
formData.append("file", fileBuffer, { filename: originalName });
formData.append("chunk_size", "500");
formData.append("overlap_size", "50");
formData.append("do_reset", "false");

await axios
  .post(
    `${RAG_SERVICE_URL}/api/v1/data/upload-and-process/${projectId}`,
    formData,
    {
      headers: { "x-api-key": CONNEXIO_RAG_API_KEY, ...formData.getHeaders() },
    },
  )
  .catch((err) =>
    console.warn("[RAG] Indexing failed (non-fatal):", err.message),
  );
// Non-fatal: file upload to backend succeeds regardless of RAG indexing
```

#### 4.4 — Wire Backend Project Creation ⏳ HASSAN

**File:** `Connexio-backend/modules/projects` (project creation controller)

After a project is created in MySQL, call:

```javascript
await axios
  .post(
    `${RAG_SERVICE_URL}/api/v1/projects/sync`,
    {
      pid: newProject.PID,
      name: newProject.PName,
      description: newProject.Description,
    },
    { headers: { "x-api-key": CONNEXIO_RAG_API_KEY } },
  )
  .catch((err) =>
    console.warn("[RAG] Project sync failed (non-fatal):", err.message),
  );
```

---

### PHASE 5 — Deploy to Hugging Face Spaces ✅ COMPLETE (RAG DB fix pending — set POSTGRES_PORT=5432 in HF Space secrets)

**Goal:** Both Python services publicly accessible from `connexio.icu`.
**Prerequisite:** Section 3.2 and 3.3 complete (GitHub repos + HF Spaces created).

#### 5.1 — Create Dockerfiles ✅

HF Spaces Docker SDK requires a `Dockerfile` at the repo root. Create one for each service.

**`C:\Users\salla\Connexios\Dockerfile`:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
```

**`F:\MasarX_A\Dockerfile`:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
```

> **Note:** HF Spaces routes external HTTPS to port 7860 internally. Both services must listen on `7860`.

Also create a `README.md` with HF Space frontmatter at each repo root (this triggers Docker SDK recognition):

```yaml
---
title: Connexios RAG # or: MasarX Agent
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---
```

#### 5.2 — Set HF Space Repository Secrets ✅ (⚠️ ConnexioRag: change POSTGRES_PORT from 5433 → 5432)

In each Space → **Settings → Repository secrets**, add the following. These are injected as environment variables at runtime — no `.env` file is used on HF Spaces.

**For Connexios RAG (`connexios-rag` Space):**

```env
GENERATION_BACKEND=GROQ
EMBEDDING_BACKEND=COHERE
VECTOR_DB_BACKEND=PGVECTOR
POSTGRES_USERNAME=<neon username>
POSTGRES_PASSWORD=<neon password>
POSTGRES_HOST=<neon host>
POSTGRES_PORT=5432
POSTGRES_MAIN_DATABASE=connexio
VECTOR_DB_PATH=./assets/qdrant
VECTOR_DB_DISTANCE_METHOD=cosine
VECTOR_DB_PGVEC_INDEX_THRESHOLD=400
GROQ_API_KEY=<your groq key>
COHERE_API_KEY=<your cohere key>
GENERATION_MODEL_ID=llama-3.3-70b-versatile
UTILITY_MODEL_ID=llama-3.1-8b-instant
EMBEDDING_MODEL_ID=embed-multilingual-v3.0
EMBEDDING_MODEL_SIZE=1024
CONNEXIO_INTERNAL_API_KEY=<same value as in your local .env>
MAIN_BACKEND_URL=https://connexio.icu
PRIMARY_LANG=en
DEFAULT_LANG=en
APP_NAME=Connexios
APP_VERSION=1.0.0
FILE_ALLOWED_TYPES=["application/pdf","text/plain"]
FILE_MAX_SIZE=10
FILE_DEFAULT_CHUNK_SIZE=1024
GENERATION_DEFAULT_MAX_TOKENS=1024
GENERATION_DEFAULT_TEMPERATURE=0.1
TOTAL_CONTEXT_CHAR_BUDGET=12000
```

**For MasarX Agent (`masarx-agent` Space):**

```env
POSTGRES_URL=postgresql+asyncpg://<user>:<pass>@<host>/connexio?sslmode=require
PGVECTOR_URL=postgresql+asyncpg://<user>:<pass>@<host>/connexio?sslmode=require
GROQ_API_KEY=<your groq key>
COHERE_API_KEY=<your cohere key>
GENERATION_BACKEND=GROQ
EMBEDDING_BACKEND=COHERE
GENERATION_MODEL_ID=llama-3.3-70b-versatile
UTILITY_MODEL_ID=llama-3.1-8b-instant
EMBEDDING_MODEL_ID=embed-multilingual-v3.0
EMBEDDING_MODEL_SIZE=1024
JWT_SECRET=<same as JWT_SECRET in Node.js backend>
HITL_SECRET_KEY=<same as in your local .env>
HITL_TOKEN_TTL_MINUTES=60
APP_NAME=MasarX
APP_VERSION=0.1.1
DB_FAIL_FAST=false
MASARX_PUSH_README=false
MASARX_DOCS_CONTEXT_LIMIT=15000
TIMEZONE=UTC
```

#### 5.3 — Trigger Deployments ✅ (MasarX fully operational; RAG DB fix triggers rebuild)

Push to GitHub → HF Spaces auto-deploys via the linked GitHub repo. Monitor build logs in the Space dashboard.

```bash
# Connexios — create Dockerfile first, then push
cd C:\Users\salla\Connexios && git add Dockerfile README.md && git push origin main

# MasarX — create Dockerfile first, then push
cd F:\MasarX_A && git add Dockerfile README.md && git push origin main
```

HF Space build logs: `https://huggingface.co/spaces/<username>/connexios-rag/logs`

#### 5.4 — Update Backend .env on Hostinger ⏳ HASSAN (add AI_AGENT_URL + RAG_SERVICE_URL after RAG is confirmed working)

SSH into Hostinger or use the file manager to update the Node.js backend `.env` with the HF Space URLs:

```env
AI_AGENT_URL=https://<hf-username>-masarx-agent.hf.space
RAG_SERVICE_URL=https://<hf-username>-connexios-rag.hf.space
```

#### 5.5 — CORS Configuration ⏳ PENDING (add after backend URLs confirmed)

Both Python services must allow:

- `https://connexio.icu`
- Frontend domain (add later when known)

```python
# Add to both main.py files
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://connexio.icu"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### PHASE 6 — End-to-End Testing ⏳ PENDING (start after Phase 3 + 4.3/4.4 complete)

| Test            | How to Verify                                                                                                                   |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| DB connectivity | Both Python services start clean against Neon — no schema errors                                                                |
| Project sync    | Create a project in MySQL backend → verify `projects` row appears in PG with correct `project_id = PID`                         |
| File indexing   | Upload a PDF via backend → verify `chunks` rows in PG + `collection_1024_{pid}` table exists                                    |
| Vector search   | Call RAG `/api/v1/nlp/agent/chat/{pid}` with a relevant query → verify RAG returns content from the indexed doc                 |
| MasarX auth     | Call MasarX endpoint with a valid service token → verify `200`. Call with expired token → verify `401`.                         |
| Agent workflow  | Fire `project.sprint_started` event → verify `202` accepted, then poll `GET /webhook/results/{pid}` → verify task plan appeared |
| HITL flow       | Trigger `create_tasks` intent → get `approval_token` → POST approval → verify graph resumes                                     |
| SSE streaming   | Call `GET /api/v1/nlp/agent/chat/stream/{pid}` → verify chunked `text/event-stream` response                                    |
| Keepalive       | Wait 15+ minutes, ping `/health` → verify `200` (no cold-start delay)                                                           |

---

## 7. OPEN QUESTIONS

> ⚠️ These must be answered before or during the relevant phase.

| #   | Question                                | Blocks    | Status                                                                         |
| --- | --------------------------------------- | --------- | ------------------------------------------------------------------------------ |
| 1   | **Backend API routes**                  | Phase 1.3 | ✅ Verified from GitHub source — see Section 4                                 |
| 2   | **Node.js project creation hook point** | Phase 4.4 | ✅ `projects.controller.js` → `createProject`, returns `result.rows[0].PID`    |
| 3   | **Node.js file upload hook point**      | Phase 4.3 | ✅ `fileUpload.controller.js` → `uploadProjectFile` function                   |
| 4   | **Embedding model for production**      | Phase 1.3 | ✅ Cohere `embed-multilingual-v3.0` — see Decision #14                         |
| 5   | **BackendApiClient task route bug**     | Phase 1.3 | ✅ Fix `/api/tasks?project_id=` → `/api/tasks/project/` in `backend_client.py` |
| 6   | **Connexios MAIN_BACKEND_URL**          | Phase 1.3 | ✅ Change Docker-internal URL to `https://connexio.icu`                        |
| 7   | **MasarX POSTGRES_URL**                 | Phase 1.3 | ✅ Change from local `masarx` DB to Neon shared DB                             |
| 8   | **Frontend domain for CORS**            | Phase 5.5 | ⏳ Add domain to `allow_origins` when frontend is ready                        |
| 9   | **createProject return field**          | Phase 4.4 | ✅ MySQL compat layer simulates `RETURNING *`. Use `result.rows[0].PID`        |
| 10  | **Hosting platform**                    | Phase 5   | ✅ Hugging Face Spaces (no card required, Docker SDK, 2 vCPU + 16GB free).     |

---

> **For any AI tool or developer continuing this work:**
>
> 1. Read Section 2 (Decisions) first — all major questions are answered there.
> 2. Check Section 7 (Open Questions) for anything still unresolved.
> 3. Follow phases 1 → 6 strictly in order. Each phase builds on the previous one.
> 4. The CLAUDE.md at `C:\Users\salla\Connexios\CLAUDE.md` has the full technical reference for both Python services.
