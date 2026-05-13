# 🚀 Connexio Full-Stack Integration: Master Blueprint

> **Date:** 2026-05-11 | **Status:** Pending Implementation
> **Author:** Sallah Ahmed (AI Agent & RAG Model Developer)
> **Purpose:** This document is the single source of truth for integrating ALL Connexio components. Any AI tool or developer reading this should have enough context to continue the work.

---

## TABLE OF CONTENTS

1. [System Overview & Components](#1-system-overview--components)
2. [Repository Map & Critical Files](#2-repository-map--critical-files)
3. [Database Schema Comparison](#3-database-schema-comparison)
4. [Hosting & Infrastructure Strategy](#4-hosting--infrastructure-strategy)
5. [Integration Plan (Step-by-Step)](#5-integration-plan-step-by-step)
6. [Open Questions](#6-open-questions)

---

## 1. SYSTEM OVERVIEW & COMPONENTS

Connexio is a **project management platform with AI-powered assistance**. It has 4 independent components that must work together:

### Component A: Node.js Backend (The Core API)

- **Repo:** `https://github.com/Hassan19Z/Connexio-backend`
- **Tech:** Express.js, MySQL, MongoDB, Socket.IO, JWT Auth
- **Role:** Handles ALL user-facing operations: authentication, projects, tasks, friends, chat, file uploads.
- **Hosting:** Hostinger shared hosting (connexio.icu) — **already deployed**
- **Database:** MySQL (Hostinger-provided)
- **Auth:** JWT tokens signed with `JWT_SECRET`, payload contains `{ UID, email, user_type }`

### Component B: RAG Model (Connexio — The Knowledge Engine)

- **Local Path:** `C:\Users\salla\connexios`
- **Tech:** Python, FastAPI, LangChain, PostgreSQL + PGVector, Celery + RabbitMQ, Groq LLM
- **Role:** Document ingestion (PDF/TXT), vector indexing, hybrid semantic search (RRF), intent detection, Corrective RAG (Wikipedia/Google/GitHub/Python fallback), multi-persona chat with streaming SSE.
- **Hosting:** NOT YET DEPLOYED (runs locally)
- **Database:** PostgreSQL with PGVector extension (local Docker)

### Component C: AI Agent (MasarX — The Orchestrator)

- **Local Path:** `F:\MasarX_A`
- **Tech:** Python, FastAPI, LangGraph (multi-subgraph supervisor), PostgreSQL, Celery
- **Role:** Automated project management workflows: task creation, team matching, README generation, sprint retros, risk detection, PR translation, skill endorsement, comprehensive audits. Has Human-in-the-Loop (HITL) approval system.
- **Hosting:** NOT YET DEPLOYED (runs locally)
- **Database:** PostgreSQL (local, shares infra with Connexio)

### Component D: Frontend

- **Repo:** ⚠️ **NOT YET PROVIDED — must be shared by the user**
- **Role:** User interface for the platform

### How They Connect (Target Architecture)

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER / BROWSER                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  FRONTEND   │  (React/Next.js — TBD)
                    │  (Hostinger │
                    │  or Vercel) │
                    └──────┬──────┘
                           │ REST API calls
                    ┌──────▼──────────────────┐
                    │   NODE.JS BACKEND       │  connexio.icu (Hostinger)
                    │   Express + MySQL       │
                    │   Auth, Projects, Tasks │
                    └──┬─────────────┬────────┘
                       │             │
            ┌──────────▼──┐    ┌─────▼──────────┐
            │  RAG MODEL  │    │   AI AGENT     │
            │  (Connexio) │    │   (MasarX)     │
            │  FastAPI    │    │   FastAPI +     │
            │  Python     │    │   LangGraph    │
            └──────┬──────┘    └─────┬──────────┘
                   │                 │
            ┌──────▼─────────────────▼──────┐
            │   SHARED POSTGRESQL DATABASE  │
            │   + PGVector Extension        │
            │   (Neon.tech — Free Tier)     │
            └───────────────────────────────┘
```

---

## 2. REPOSITORY MAP & CRITICAL FILES

### 🔵 Node.js Backend — Files to Read First

| File                                          | Why It Matters                                                                                                                                                                                                                                                                                        |
| :-------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app.js`                                      | Entry point. Creates Express server + Socket.IO. Connects MySQL + MongoDB.                                                                                                                                                                                                                            |
| `bootstrap.js`                                | All routes registered here: `/api/auth`, `/api/users`, `/api/tasks`, `/api/projects`, `/api/posts`, `/api/friends`, `/api/chats`, `/api/calls`, `/api/upload`                                                                                                                                         |
| `database/dbconnection.js`                    | **CRITICAL.** Full MySQL schema with all `CREATE TABLE` statements. Tables: `users`, `projects`, `tasks`, `project_members`, `task_dependencies`, `team_ratings`, `friends`, `friend_requests`, `blocked_users`, `groups`, `group_members`, `technical_skills`, `non_technical_skills`, `user_skills` |
| `middleware/authMiddleware.js`                | JWT verification middleware. Uses `JWT_SECRET` to decode tokens. Attaches `req.user = { UID, email, user_type }`                                                                                                                                                                                      |
| `modules/auth/auth.controller.js`             | Signup, signin, Google OAuth, email verification, OTP-based password reset                                                                                                                                                                                                                            |
| `modules/fileUpload/fileUpload.controller.js` | File upload to local `/uploads` directory. Has routes for profile pictures, post images, message attachments, and **project files** (important for RAG)                                                                                                                                               |
| `config/upload.js`                            | Multer config for file handling                                                                                                                                                                                                                                                                       |

### 🟢 RAG Model (Connexio) — Files to Read First

| File                                                     | Why It Matters                                                                                                                                                                                                                                  |
| :------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/main.py`                                            | FastAPI startup. Initializes DB engine, LLM clients (Groq/OpenAI), embedding client, VectorDB client (PGVector), template parser                                                                                                                |
| `src/controllers/NLPController.py`                       | **THE BRAIN.** 528 lines. Handles: intent detection → workflow routing → hybrid retrieval (vector + trigram RRF) → Corrective RAG (Wikipedia/Google/GitHub/Python) → persona-based response generation → SSE streaming                          |
| `src/controllers/WorkflowController.py`                  | Intent detection and language detection using utility LLM                                                                                                                                                                                       |
| `src/controllers/helpers/ToolManager.py`                 | Manages all external tools: knowledge base search, Google (SerpApi), Wikipedia, GitHub, Python interpreter                                                                                                                                      |
| `src/Routes/agent.py`                                    | API endpoints: `POST /api/v1/nlp/agent/chat/{project_id}` and `GET /api/v1/nlp/agent/chat/stream/{project_id}`                                                                                                                                  |
| `src/Routes/data.py`                                     | Data endpoints: upload files, process chunks, push to vector DB                                                                                                                                                                                 |
| `src/models/db_schemas/connexio/schemas/data_chunk.py`   | `chunks` table schema: `chunk_id`, `chunk_uuid`, `chunk_text`, `chunk_metadata (JSONB)`, `chunk_order`, `chunk_project_id (FK→projects)`, `chunk_asset_id (FK→assets)`                                                                          |
| `src/models/db_schemas/connexio/schemas/project.py`      | `projects` table: `project_id`, `project_uuid`, `project_name`, `progress`                                                                                                                                                                      |
| `src/models/db_schemas/connexio/schemas/asset.py`        | `assets` table: uploaded file metadata                                                                                                                                                                                                          |
| `src/models/db_schemas/connexio/schemas/chat_session.py` | `rag_chat_sessions` table: persistent chat history with persona/language tracking                                                                                                                                                               |
| `src/stores/vectordb/providers/PGVectorProvider.py`      | **CRITICAL.** Creates dynamic tables named `collection_{embedding_size}_{project_id}` with columns: `id`, `text`, `vector`, `metadata (JSONB)`, `chunk_id (FK→chunks)`. Uses HNSW index + GIN trigram index. Implements hybrid search with RRF. |
| `src/celery_app.py`                                      | Celery worker config for async document processing                                                                                                                                                                                              |

### 🟠 AI Agent (MasarX) — Files to Read First

| File                                            | Why It Matters                                                                                                                                                                                                                                       |
| :---------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/main.py`                                   | FastAPI startup for the agent service                                                                                                                                                                                                                |
| `src/helpers/config.py`                         | Pydantic Settings model. All env vars defined here. Key: `POSTGRES_URL`, `PGVECTOR_URL`, `GROQ_API_KEY`, `GITHUB_TOKEN`, `TAVILY_API_KEY`                                                                                                            |
| `src/controllers/WorkflowController.py`         | **CORE.** LangGraph supervisor graph. Routes intents to 7 subgraphs: `team`, `docs`, `monitor`, `task`, `pr_translator`, `skill_endorsement`, `audit`. Has circuit breaker, caching, timeout handling.                                               |
| `src/controllers/subgraphs/task_subgraph.py`    | Task planning with HITL approval flow                                                                                                                                                                                                                |
| `src/controllers/subgraphs/team_subgraph.py`    | Team matching, onboarding, skill recommender                                                                                                                                                                                                         |
| `src/controllers/subgraphs/doc_subgraph.py`     | README generation, sprint retros. **Already uses `retriever` from `stores/vectordb`** to fetch RAG context                                                                                                                                           |
| `src/controllers/subgraphs/monitor_subgraph.py` | Risk detection, workload monitoring                                                                                                                                                                                                                  |
| `src/controllers/subgraphs/audit_subgraph.py`   | Full project audit (combines readme + risks + team)                                                                                                                                                                                                  |
| `src/Routes/webhook_routes.py`                  | **CRITICAL.** The API surface for the backend. Event-driven webhooks (`/api/v1/masarx/webhook/event/{event_type}/{project_id}`) and manual triggers (`/api/v1/masarx/agent/{intent}/{project_id}`). Supports 12 intents. Has HITL approval endpoint. |
| `src/models/db_schemas/live_models.py`          | All SQLAlchemy models: `User`, `Project`, `Task`, `DataChunk`, `Notification`, `PendingPlan`                                                                                                                                                         |
| `src/stores/vectordb/rag_tool.py`               | MasarX's own RAG retriever. Queries the **same PGVector tables** that Connexio creates (`collection_{size}_{project_id}`). Uses cosine similarity.                                                                                                   |
| `src/stores/vectordb/retriever.py`              | Thin wrapper around `rag_tool.py`                                                                                                                                                                                                                    |
| `src/utils/tools/db_tool.py`                    | Database operations: get_project, get_tasks, get_team_members, save_document, etc.                                                                                                                                                                   |

---

## 3. DATABASE SCHEMA COMPARISON

### The Two-Database Reality

| Database                    | Engine                   | Used By                     | Tables                                                                                                                                       |
| :-------------------------- | :----------------------- | :-------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------- |
| **MySQL** (Hostinger)       | MySQL 8.x                | Node.js Backend             | `users`, `projects`, `tasks`, `project_members`, `task_dependencies`, `team_ratings`, `friends`, `groups`, etc.                              |
| **PostgreSQL** (Local/Neon) | PostgreSQL 15 + PGVector | Connexio RAG + MasarX Agent | `projects`, `chunks`, `assets`, `rag_chat_sessions`, `collection_1024_{pid}` (vector tables), `masarx_notifications`, `masarx_pending_plans` |

### ⚠️ Critical Schema Mismatches to Fix

**1. Project ID Mapping:**

- MySQL Backend: `projects.PID` (INT, auto-increment)
- PostgreSQL (Connexio): `projects.project_id` (INT, auto-increment)
- PostgreSQL (MasarX): `projects.project_id` (INT, auto-increment)
- **Problem:** The `PID` from MySQL and `project_id` from PostgreSQL are independent sequences. We need a mapping strategy.

**2. User ID Mapping:**

- MySQL Backend: `users.UID` (INT)
- MasarX: `user.UID` (INT)
- **These must match.** MasarX should use the same UID from the backend JWT.

**3. DataChunk Model Mismatch:**

- Connexio has: `chunk_asset_id` (FK→assets), `updated_at`
- MasarX has: NO `chunk_asset_id`, NO `updated_at`
- **Fix:** Add `chunk_asset_id` and `updated_at` to MasarX's `live_models.py`

**4. Vector Collection Naming:**

- Both use: `collection_{embedding_size}_{project_id}` ✅ Already aligned.
- Both use 1024-dim embeddings with `bge-m3` model ✅ Already aligned.

---

## 4. HOSTING & INFRASTRUCTURE STRATEGY

### The Problem

Hostinger shared hosting (non-VPS) **cannot run**:

- Docker containers
- PostgreSQL / PGVector
- Python FastAPI servers
- Celery workers / RabbitMQ

### The Solution: Hybrid Cloud (Free Tier)

| Service                   | Provider                           | Free Tier Limits                             | Purpose                         |
| :------------------------ | :--------------------------------- | :------------------------------------------- | :------------------------------ |
| **PostgreSQL + PGVector** | [Neon.tech](https://neon.tech)     | 0.5 GB storage, always-on                    | Shared database for RAG + Agent |
| **RAG + Agent APIs**      | [Render.com](https://render.com)   | 750 hrs/month, sleeps after 15min inactivity | Host both FastAPI services      |
| **Task Queue**            | [CloudAMQP](https://cloudamqp.com) | Free "Little Lemur" plan                     | RabbitMQ for Celery             |
| **Redis**                 | [Upstash](https://upstash.com)     | 10K commands/day free                        | Celery result backend           |
| **Node.js Backend**       | Hostinger                          | Current paid plan                            | Keep as-is                      |
| **Frontend**              | Hostinger or Vercel                | Current plan / Free                          | TBD                             |

### Environment Variables to Update

**For Neon.tech (both Connexio & MasarX):**

```env
# Connexio .env
POSTGRES_USERNAME="neondb_owner"
POSTGRES_PASSWORD="<neon_password>"
POSTGRES_HOST="ep-xxx.us-east-2.aws.neon.tech"
POSTGRES_PORT=5432
POSTGRES_MAIN_DATABASE="connexio"

# MasarX .env
POSTGRES_URL="postgresql+asyncpg://neondb_owner:<password>@ep-xxx.us-east-2.aws.neon.tech/connexio?sslmode=require"
PGVECTOR_URL="postgresql+asyncpg://neondb_owner:<password>@ep-xxx.us-east-2.aws.neon.tech/connexio?sslmode=require"
```

---

## 5. INTEGRATION PLAN (STEP-BY-STEP)

### Phase 1: Shared Database Foundation

**Goal:** Both Python services read/write the same PostgreSQL instance.

#### Step 1.1 — Create Neon.tech Database

1. Sign up at [neon.tech](https://neon.tech)
2. Create a new project named "connexio"
3. Enable the `vector` and `pg_trgm` extensions via SQL console
4. Copy the connection string

#### Step 1.2 — Fix MasarX DataChunk Model

**File:** `F:\MasarX_A\src\models\db_schemas\live_models.py`

- Add `chunk_asset_id = Column(Integer, nullable=True)` (no FK constraint since assets table is managed by Connexio)
- Add `updated_at = Column(DateTime(timezone=True), onupdate=func.now())`
- This ensures MasarX can read chunks created by Connexio without errors

#### Step 1.3 — Update .env Files

- Update both `C:\Users\salla\connexios\src\.env` and `F:\MasarX_A\src\.env` to point to the Neon.tech URL
- Verify both services can connect by running their startup sequences

#### Step 1.4 — Run Connexio Migrations

- Use Alembic in the Connexio project to create the `projects`, `assets`, `chunks`, `rag_chat_sessions` tables on Neon
- MasarX will auto-create `masarx_notifications` and `masarx_pending_plans` on startup

---

### Phase 2: JWT Bridge (Identity Sync)

**Goal:** MasarX trusts the Node.js backend's JWT tokens.

#### Step 2.1 — Create JWT Verification in MasarX

**New File:** `F:\MasarX_A\src\utils\auth.py`

```python
import jwt
from helpers.config import get_settings

settings = get_settings()

def verify_backend_token(token: str) -> dict:
    """Verify a JWT issued by the Node.js backend."""
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    return {"uid": payload["UID"], "email": payload["email"], "user_type": payload["user_type"]}
```

#### Step 2.2 — Add Config

**File:** `F:\MasarX_A\src/.env`

```env
JWT_SECRET="<same value as JWT_SECRET in Node.js backend>"
```

**File:** `F:\MasarX_A\src/helpers/config.py` — Add `JWT_SECRET: Optional[str] = None`

#### Step 2.3 — Protect MasarX Endpoints

Add a FastAPI dependency that extracts and verifies the `Authorization: Bearer <token>` header on all `/api/v1/masarx/` routes.

---

### Phase 3: Backend → Agent Integration

**Goal:** The Node.js backend can trigger AI workflows.

#### Step 3.1 — Add AI Service Module to Backend

**New File:** `Connexio-backend/services/aiService.js`

```javascript
import axios from "axios";

const AI_AGENT_URL = process.env.AI_AGENT_URL; // e.g., https://masarx.onrender.com
const AI_AGENT_API_KEY = process.env.AI_AGENT_API_KEY;

export const triggerAIIntent = async (intent, projectId, payload = {}) => {
  const response = await axios.post(
    `${AI_AGENT_URL}/api/v1/masarx/agent/${intent}/${projectId}`,
    payload,
    { headers: { "X-API-Key": AI_AGENT_API_KEY }, timeout: 60000 },
  );
  return response.data;
};

export const triggerAIEvent = async (eventType, projectId, payload = {}) => {
  const response = await axios.post(
    `${AI_AGENT_URL}/api/v1/masarx/webhook/event/${eventType}/${projectId}`,
    payload,
    { headers: { "X-API-Key": AI_AGENT_API_KEY }, timeout: 10000 },
  );
  return response.data;
};
```

#### Step 3.2 — Wire Backend Events

Modify existing backend controllers to fire AI events at key moments:

| Backend Action     | Event to Fire            | MasarX Intent     |
| :----------------- | :----------------------- | :---------------- |
| New user signs up  | `user.joined_platform`   | `match_team`      |
| User joins project | `user.joined_project`    | `onboard_member`  |
| Sprint starts      | `project.sprint_started` | `create_tasks`    |
| Task completed     | `task.completed`         | `endorse_skills`  |
| Sprint closes      | `sprint.closed`          | `generate_retro`  |
| Project closes     | `project.closed`         | `generate_readme` |

#### Step 3.3 — Add Chat Route to Backend

**New File:** `Connexio-backend/modules/ai/ai.routes.js`

```javascript
// POST /api/ai/chat/:projectId — proxies to Connexio RAG
// GET  /api/ai/chat/stream/:projectId — proxies SSE stream from Connexio RAG
// POST /api/ai/agent/:intent/:projectId — triggers MasarX intent
// POST /api/ai/approval/:token — forwards HITL decision to MasarX
```

---

### Phase 4: Backend → RAG Integration

**Goal:** Documents uploaded via the backend are automatically indexed for AI search.

#### Step 4.1 — Webhook on File Upload

Modify `modules/fileUpload/fileUpload.controller.js`:
After `uploadProjectFile` succeeds, POST the file URL to Connexio's `/api/v1/data/process-and-push/{project_id}`.

#### Step 4.2 — Project Sync

When a new project is created in the MySQL backend, also create a matching `Project` record in PostgreSQL so that Connexio can index documents against it.

**Option A (Simple):** The backend calls a new endpoint on Connexio: `POST /api/v1/projects/sync` with `{ pid, name, description }`.
**Option B (Direct):** MasarX's `db_tool` reads the MySQL backend directly via a read-only MySQL connection string. (More complex, not recommended for Phase 1.)

---

### Phase 5: Deployment to Cloud

**Goal:** Both Python services are accessible from the internet.

#### Step 5.1 — Deploy Connexio RAG to Render

1. Create a `Dockerfile` in the Connexio repo (or use `render.yaml`)
2. Set env vars in Render dashboard (Neon URL, Groq API key, etc.)
3. Deploy. Note the public URL (e.g., `https://connexio-rag.onrender.com`)

#### Step 5.2 — Deploy MasarX Agent to Render

1. Same process. Deploy from the MasarX repo.
2. Public URL: e.g., `https://masarx-agent.onrender.com`

#### Step 5.3 — Update Backend .env on Hostinger

```env
AI_AGENT_URL=https://masarx-agent.onrender.com
RAG_SERVICE_URL=https://connexio-rag.onrender.com
AI_AGENT_API_KEY=<generate a random secret>
```

#### Step 5.4 — CORS Configuration

Both Python services must allow requests from:

- `https://connexio.icu` (Hostinger backend)
- The frontend domain (TBD)

---

### Phase 6: End-to-End Testing

| Test            | How to Verify                                                        |
| :-------------- | :------------------------------------------------------------------- |
| DB connectivity | Both Python services start without errors against Neon               |
| JWT bridge      | MasarX can decode a token generated by the Node.js backend           |
| RAG indexing    | Upload a PDF via backend → verify chunks appear in PostgreSQL        |
| Vector search   | Query MasarX's RAG tool → verify it returns indexed content          |
| Agent workflow  | Trigger `create_tasks` via backend → verify HITL approval flow works |
| SSE streaming   | Frontend sends a chat query → receives streamed response             |

---

## 6. OPEN QUESTIONS

> [!IMPORTANT]
> **For the team to answer before implementation:**

### Must Answer

1. **Frontend Repo:** Please share the frontend repository URL so the integration points (API calls, SSE handling) can be documented.
2. **Project ID Sync Strategy:** Should we use the MySQL `PID` as the canonical project ID everywhere (simplest), or create a UUID-based mapping layer?
3. **File Access:** Are uploaded files on Hostinger publicly accessible via URL, or do they need authentication to download? (Connexio needs to fetch them for indexing.)

### Nice to Answer

4. **Rate Limiting:** Should we limit AI chat messages per user per day? (Groq free tier has limits.)
5. **Corrective RAG:** Should web search fallback (Google/Wikipedia) be enabled in production, or only internal knowledge base?
6. **Celery:** For Phase 1, can we skip Celery and process documents synchronously? (Simpler deployment, fine for low traffic.)

---

> [!TIP]
> **For any AI tool continuing this work:** Start by reading the files listed in Section 2 in the order shown. Then follow Phase 1 → Phase 6 sequentially. Each phase builds on the previous one.
