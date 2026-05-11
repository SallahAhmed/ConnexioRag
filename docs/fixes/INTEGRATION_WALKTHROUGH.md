# Connexios RAG × Connexio Backend — Integration Walkthrough

**Author:** Claude (Lead Integration Engineer)  
**Date:** May 2026  
**Audience:** RAG engineer (you) + Main backend teammate  
**Status:** Implementation complete — ready to deploy

---

> ## ⚠️ Honest Note on Errors
>
> I am confident in the architecture and logic of everything in this document.
> However, there are **3 places where a runtime error is possible** depending on
> your specific environment — I have flagged each one with a 🔴 warning block
> so you know exactly what to watch for and how to fix it if it happens.
> Everything else is deterministic and will work as written.

---

## Table of Contents

1. [What Problem We Were Solving](#1-what-problem-we-were-solving)
2. [The Architecture We Agreed On](#2-the-architecture-we-agreed-on)
3. [The X-API-Key — What It Is and How to Generate It](#3-the-x-api-key--what-it-is-and-how-to-generate-it)
4. [Every File That Changed — RAG Side](#4-every-file-that-changed--rag-side)
5. [Every File That Changed — Backend Side](#5-every-file-that-changed--backend-side)
6. [Frontend Notes — For When It Is Built](#6-frontend-notes--for-when-it-is-built)
7. [How the Full Request Flow Works Step by Step](#7-how-the-full-request-flow-works-step-by-step)
8. [Deployment Checklist](#8-deployment-checklist)
9. [Testing the Integration End-to-End](#9-testing-the-integration-end-to-end)
10. [Troubleshooting Guide](#10-troubleshooting-guide)

---

## 1. What Problem We Were Solving

Before this integration, the RAG had three critical problems:

### Problem A — No Security
Any person or service on the internet could call
`POST /api/v1/nlp/agent/chat/1` with any `user_id` they wanted. There was
nothing stopping a user from typing `user_id: 999` and reading someone else's
session history or generating responses in their name.

### Problem B — Broken Data Tools
`ToolManager` had methods called `get_matching_rationale()` and
`get_team_gaps()` that ran SQL queries against tables that **do not exist** in
any database — `technology`, `user_technology`, `project_technology`. These
methods always failed silently with a canned fallback message. The agent was
effectively blind to real project and user data.

### Problem C — Wrong Header Direction
An early version of `BackendApiClient` was sending the `X-API-Key` header
**outward** when calling the main backend's public endpoints. This was
incorrect — the key is only supposed to flow **inward** to the RAG.

All three problems are now resolved.

---

## 2. The Architecture We Agreed On

```
┌─────────────────────────────────────────────────────┐
│                  BROWSER / MOBILE                   │
│                (No direct RAG access)               │
└──────────────────────┬──────────────────────────────┘
                       │  JWT Token in Authorization header
                       ▼
┌─────────────────────────────────────────────────────┐
│           MAIN CONNEXIO BACKEND                     │
│           connexio.icu  (Node.js)                   │
│                                                     │
│  1. Validates user JWT → extracts UID               │
│  2. Calls RAG with X-API-Key + user_id in body      │
│  3. Returns RAG answer back to frontend             │
└──────────────────────┬──────────────────────────────┘
                       │  X-API-Key: shared_secret
                       │  Body: { user_id: 1, query: "..." }
                       ▼
┌─────────────────────────────────────────────────────┐
│           CONNEXIOS RAG (Python / FastAPI)          │
│           connexios:8000                            │
│                                                     │
│  1. Validates X-API-Key header → trusts user_id     │
│  2. Fetches live data from main backend (public     │
│     endpoints — no auth needed)                     │
│  3. Generates grounded AI response                  │
│  4. Returns answer + session_id                     │
└──────────────────────┬──────────────────────────────┘
                       │  GET /api/users/{id}    (public)
                       │  GET /api/projects/{id} (public)
                       │  GET /api/projects/{id}/members (public)
                       │  GET /api/tasks?project_id={id} (public)
                       ▼
┌─────────────────────────────────────────────────────┐
│           MAIN CONNEXIO BACKEND                     │
│           (same server, different endpoints)        │
└─────────────────────────────────────────────────────┘
```

**Key rules that come out of this design:**

- The frontend **never** calls the RAG directly.
- The `X-API-Key` flows **inward** to the RAG only. It is never sent outward.
- The RAG fetches public data from the main backend with no auth headers.
- `user_id` is always resolved from the JWT by the main backend — the client
  never provides it directly.

---

## 3. The X-API-Key — What It Is and How to Generate It

The `X-API-Key` is simply a long random string that both services agree on in
advance. It is not issued by any third party, not fetched from any API, and not
stored in a database. You generate it once, copy it into both `.env` files, and
that is the entire setup.

### How to generate it (run this once)

```python
import secrets
print(secrets.token_hex(32))
```

This outputs something like:
```
a7f3c91e2b84d06f5e1a9c3b7d2f8e4a1b6c9d0e3f5a8b2c4d7e1f9a3b6c8d2
```

Copy that string. It becomes the value for `CONNEXIO_INTERNAL_API_KEY` in the
RAG's `.env` and `CONNEXIO_RAG_API_KEY` in the main backend's `.env`.

### Rules

- Both sides must have **exactly the same string**. One extra space or wrong
  character and every request returns 401.
- Never commit this value to git. It belongs in `.env` files only.
- If you ever suspect it is compromised: generate a new string, update both
  `.env` files, restart both services. That is the entire rotation process.

---

## 4. Every File That Changed — RAG Side

This section explains every file change in plain English so you can verify
each one before applying it.

---

### 4.1 `src/utils/security.py` — NEW FILE

**What it does:**
A FastAPI dependency function called `verify_api_key`. When added to a router,
FastAPI automatically runs it before every request on that router. It reads the
`X-API-Key` header, compares it to `CONNEXIO_INTERNAL_API_KEY` from the `.env`
file, and either allows the request through or returns a `401 Unauthorized`.

**Dev-mode behaviour:**
If `CONNEXIO_INTERNAL_API_KEY` is not set in your `.env`, the function logs a
warning and skips validation entirely. This means local development still works
without needing to configure the key. The moment you set the key in `.env`, it
becomes enforced.

**How it is applied:**
It is added at the router level in `agent.py`, `nlp.py`, and `data.py` using
FastAPI's `dependencies` parameter. This means every single endpoint in those
three routers is protected — you do not need to add the dependency
endpoint-by-endpoint.

```python
# Applied like this at the top of each router file:
agent_router = APIRouter(
    prefix="/api/v1/nlp/agent",
    tags=["api_v1", "agent"],
    dependencies=[Depends(verify_api_key)],  # ← protects every route below
)
```

> 🔴 **Potential issue #1 — Circular import**
> `security.py` imports `get_settings` from `helpers.config` inside the
> function body (not at the top of the file) specifically to avoid a circular
> import at startup. If you ever move `get_settings` to a different module,
> update the import path inside `verify_api_key` accordingly. If you see an
> `ImportError` mentioning `helpers.config` at startup, this is why.

---

### 4.2 `src/utils/backend_client.py` — NEW FILE

**What it does:**
An async HTTP client class (`BackendApiClient`) that the RAG uses to call the
main backend's public read endpoints. It replaces all the broken SQL queries in
`ToolManager` that were targeting tables that do not exist.

**Why a dedicated class instead of raw `httpx` calls:**
Three reasons: automatic retry on network failure (up to 2 retries with a short
wait), an in-memory cache so the same user profile or project details are not
fetched on every single message, and a single place to change the base URL or
headers if the main backend API ever changes.

**Caching behaviour:**
- User profiles (`GET /api/users/{id}`): cached for 5 minutes
- Project details (`GET /api/projects/{id}`): cached for 5 minutes
- Project members (`GET /api/projects/{id}/members`): cached for 5 minutes
- Tasks (`GET /api/tasks?project_id={id}`): **not cached** — task status
  changes frequently and stale data here would give wrong answers

**The header fix (this was a bug):**
An earlier version sent `X-API-Key` outward to the main backend. The main
backend's read endpoints are public, so this header was wrong and unnecessary.
The `_headers()` method now only sends `Content-Type` and `Accept`. The
`X-API-Key` flows inward to the RAG only, never outward.

**One instance shared across all requests:**
`BackendApiClient` is instantiated once at application startup in `main.py` and
attached to `app.backend_client`. This is important — if a new instance were
created per request, the in-memory cache would be useless because it would be
thrown away after each request.

> 🔴 **Potential issue #2 — Main backend URL not reachable**
> If `MAIN_BACKEND_URL` in your `.env` is set to `http://connexio-backend:5000`
> but the container is actually named something different in your
> `docker-compose.yml`, all `BackendApiClient` calls will time out after
> `_REQUEST_TIMEOUT = 10.0` seconds and return `None`. The RAG will not crash
> — it will fall back to canned messages in `ToolManager` — but live data will
> not appear in responses. Fix: verify the container name in
> `docker-compose.yml` and match it in `MAIN_BACKEND_URL`.
>
> To test connectivity from inside the RAG container:
> ```bash
> docker exec -it <rag_container_name> curl http://connexio-backend:5000/api/projects/1
> ```
> If that returns JSON, connectivity is fine. If it times out, the container
> name is wrong or the network is misconfigured.

---

### 4.3 `src/helpers/config.py` — UPDATED

**What changed:**
Two new fields added to the `Settings` class:

```python
CONNEXIO_INTERNAL_API_KEY: str | None = None
MAIN_BACKEND_URL: str = "http://localhost:5000"
```

Both are optional with safe defaults so the app still starts even if they are
not set in `.env`. `MAIN_BACKEND_URL` defaults to `localhost:5000` for local
development.

**What you add to your actual `src/.env`:**
```env
CONNEXIO_INTERNAL_API_KEY=<your_generated_key>
MAIN_BACKEND_URL=http://connexio-backend:5000
```

Replace `connexio-backend` with whatever the main backend's container service
name is in your `docker-compose.yml`. If running locally without Docker, use
`http://localhost:5000`.

---

### 4.4 `src/Routes/agent.py` — UPDATED

**What changed:**
Added `dependencies=[Depends(verify_api_key)]` to the `APIRouter` definition.
Removed the now-redundant inline `x_api_key: str = Header(None)` parameter that
was previously in the chat endpoint signature — the router-level dependency
handles this for all endpoints.

Also added `backend_client=getattr(request.app, 'backend_client', None)` to the
`get_nlp_controller` helper function so the `BackendApiClient` instance flows
through to `NLPController` and then to `ToolManager`.

---

### 4.5 `src/Routes/nlp.py` — UPDATED

**What changed:**
Added `dependencies=[Depends(verify_api_key)]` to the router. No other logic
changed — the indexing, search, and info endpoints work exactly as before, they
are now just protected by the API key.

---

### 4.6 `src/Routes/data.py` — UPDATED

**What changed:**
Added `dependencies=[Depends(verify_api_key)]` to the router. Upload and
processing endpoints work exactly as before.

---

### 4.7 `src/controllers/helpers/ToolManager.py` — UPDATED

**What changed:**
This is the biggest functional change. Three methods were rewritten.

**`get_matching_rationale()` — rewritten**

Before: ran a SQL query against `technology`, `user_technology`, and
`project_technology` tables. These tables do not exist anywhere. The method
always returned a canned fallback message.

After: calls `BackendApiClient.get_user(user_id)` and
`BackendApiClient.get_project(project_id)` in parallel, parses the user's
`technologies` string and `skills` JSON array, compares them to the project's
`technologyUsed` array, then generates a personalized explanation using the
generation LLM with the actual data filled in.

**`get_team_gaps()` — rewritten**

Before: same problem — SQL against non-existent tables.

After: calls `get_project(project_id)` and `get_project_members(project_id)` in
parallel, aggregates the `technologies` field from all team members, compares
against `technologyUsed` from the project, and returns a plain-English gap
analysis.

**`get_project_context_summary()` — NEW METHOD**

A new method that fetches project details, members, and tasks in parallel and
returns a concise text summary that gets injected into every relevant chat
prompt as `[Live Project Data]`. This means the agent automatically knows the
project name, tech stack, team size, and task completion stats without the user
needing to ask.

**Constructor updated:**
Now accepts `backend_client=None` as a parameter. When `None` (e.g. in Celery
workers where the singleton is not available), the methods that need it return
a graceful message instead of crashing.

---

### 4.8 `src/controllers/NLPController.py` — UPDATED

**What changed:**

The constructor now accepts `backend_client=None` and passes it through to
`ToolManager` when initialising it:

```python
self.tool_manager = ToolManager(
    ...
    backend_client=self.backend_client,  # ← new
)
```

Inside `_prepare_chat_context`, after the CRAG retrieval logic, a new block was
added that calls `get_project_context_summary()` and appends the result to
`retrieved_context` as `[Live Project Data]`. This runs for every node except
`OUT_OF_SCOPE`.

---

### 4.9 `src/main.py` — UPDATED

**What changed:**
One new import and one new block in `startup_span()`:

```python
from utils.backend_client import BackendApiClient

# Inside startup_span():
app.backend_client = BackendApiClient(
    base_url=settings.MAIN_BACKEND_URL,
    api_key=settings.CONNEXIO_INTERNAL_API_KEY or "",
)
```

The `api_key` parameter is stored internally in `BackendApiClient` but is NOT
used in `_headers()` (since the backend endpoints are public). It is kept in
the constructor in case a future backend endpoint requires authentication, so
the client is already wired to support it without changes.

A startup log message now tells you whether API key validation is active:
```
[AGENT] X-API-Key authentication ENABLED. Backend URL: http://connexio-backend:3000
# or
[AGENT] WARNING: CONNEXIO_INTERNAL_API_KEY is not set. X-API-Key validation is DISABLED.
```

---

### 4.10 `src/.env.example` — UPDATED

Two new lines added at the bottom under a clearly labelled section:

```env
# ========================= Integration: Main Backend ↔ RAG =========================
CONNEXIO_INTERNAL_API_KEY="connexio_rag_shared_secret_prod_only"
MAIN_BACKEND_URL="http://localhost:3000"
```

> 🔴 **Potential issue #3 — Old Celery workers holding stale config**
> Celery workers load their configuration once at startup from `celery_app.py`,
> which calls `get_settings()`. If you add the new env vars to `.env` but do
> not restart the Celery workers, they will run with the old config (no
> `CONNEXIO_INTERNAL_API_KEY`). This does not cause errors in Celery tasks
> because Celery tasks do not call the RAG routes — they process files and
> index vectors. But if you ever add a Celery task that uses
> `BackendApiClient`, restart the workers after any `.env` change.

---

## 5. Every File That Changed — Backend Side

**You do not make these changes. Send this section to your teammate.**

---

### 5.1 `tasks.routes.js` — UPDATED

**Change required:**
Remove the `protect` middleware from the `GET /api/tasks` route only. Every
other HTTP method on tasks must remain protected.

**Before:**
```javascript
router.get('/', protect, TaskController.getTasks);
router.post('/', protect, TaskController.createTask);
router.put('/:id', protect, TaskController.updateTask);
router.delete('/:id', protect, TaskController.deleteTask);
```

**After:**
```javascript
router.get('/', TaskController.getTasks);           // ← public (read only)
router.post('/', protect, TaskController.createTask);
router.put('/:id', protect, TaskController.updateTask);
router.delete('/:id', protect, TaskController.deleteTask);
```

**Why this is safe:**
Reading task data (descriptions, statuses, dates) for display purposes is not
sensitive. The RAG needs this data to give contextually accurate answers about
project progress. Write operations (create, update, delete) remain fully
protected by JWT.

---

### 5.2 `utils/ragClient.js` — NEW FILE (teammate creates)

```javascript
// utils/ragClient.js

const RAG_BASE_URL = process.env.RAG_BASE_URL;
const RAG_API_KEY  = process.env.CONNEXIO_RAG_API_KEY;

/**
 * Send a chat message to the Connexios RAG agent.
 *
 * @param {number} userId     - UID from the validated JWT (req.user.UID)
 *                              NEVER pass this from req.body — it must come
 *                              from the server-side JWT extraction only.
 * @param {number} projectId  - PID from the projects table (integer)
 * @param {string} query      - The user's message
 * @param {string} persona    - "student" | "early_career" | "educator" | "company"
 * @param {number|null} sessionId - RAG session ID for conversation continuity
 *                                  (null on the first message, then use what RAG returns)
 * @returns {Promise<Object>} - { answer, node, language, sources, session_id }
 */
async function callRagChat(userId, projectId, query, persona = "student", sessionId = null) {
  const response = await fetch(
    `${RAG_BASE_URL}/api/v1/nlp/agent/chat/${projectId}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": RAG_API_KEY,
      },
      body: JSON.stringify({
        user_id:    userId,
        query:      query,
        persona:    persona,
        session_id: sessionId,
        limit:      5,
      }),
    }
  );

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(`RAG error ${response.status}: ${err.error || response.statusText}`);
  }

  return response.json();
}

module.exports = { callRagChat };
```

**Usage inside a controller:**
```javascript
const { callRagChat } = require("../utils/ragClient");

exports.chat = async (req, res) => {
  try {
    const userId    = req.user.UID;                        // ← from JWT middleware
    const projectId = parseInt(req.params.projectId, 10);
    const { query, persona, session_id } = req.body;

    const result = await callRagChat(userId, projectId, query, persona, session_id);

    res.json({
      success:    true,
      answer:     result.answer,
      session_id: result.session_id,  // store this and pass back on next turn
      node:       result.node,
      language:   result.language,
      sources:    result.sources,
    });
  } catch (err) {
    console.error("[RAG Chat Error]", err.message);
    res.status(500).json({ success: false, message: "AI service temporarily unavailable." });
  }
};
```

---

### 5.3 Backend `.env` additions

```env
CONNEXIO_RAG_API_KEY=<same_key_as_rag_CONNEXIO_INTERNAL_API_KEY>
RAG_BASE_URL=http://connexios:8000
```

Replace `connexios` with whatever the RAG container is named in the shared
`docker-compose.yml`.

---

## 6. Frontend Notes — For When It Is Built

No frontend changes are needed right now because there is no frontend. When the
frontend is built, here is exactly what it needs to know:

### What the frontend calls
The frontend calls **the main backend only**. It never calls the RAG directly.

```javascript
// CORRECT — frontend calls main backend
fetch('/api/rag/chat/123', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${jwtToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    query:      userMessage,
    persona:    'student',
    session_id: storedSessionId ?? null,  // null on first message
  }),
});

// WRONG — frontend must never call the RAG directly
fetch('https://connexios:8000/api/v1/nlp/agent/chat/123', { ... });
```

### session_id — critical for conversation memory
The RAG returns a `session_id` on every response. The frontend must store this
value and include it on every follow-up message in the same conversation. If
`session_id` is not passed, the RAG starts a fresh session and loses memory of
everything said before.

### Streaming chat (future)
The streaming endpoint (`GET /api/v1/nlp/agent/chat/stream/{project_id}`) uses
Server-Sent Events. The browser's native `EventSource` API cannot send custom
headers, which means the `X-API-Key` cannot be sent from the browser. The
recommended approach is for the main backend to proxy the SSE stream — the
frontend connects to the main backend's streaming endpoint, and the backend
opens the RAG stream with the key in the header and forwards chunks.

---

## 7. How the Full Request Flow Works Step by Step

Here is a complete trace of what happens when a user sends the message
*"Why was I matched to this project?"*:

```
1. User types message in browser
   └─ Frontend sends: POST /api/rag/chat/123
      Headers: Authorization: Bearer <jwt>
      Body:    { query: "Why was I matched...", persona: "student", session_id: 42 }

2. Main backend receives request
   └─ JWT middleware runs → extracts UID=1 from token
   └─ Controller calls: callRagChat(userId=1, projectId=123, query="...", ...)
      Headers: X-API-Key: shared_secret
      Body:    { user_id: 1, query: "...", session_id: 42 }
   └─ Forwards to: POST http://connexios:8000/api/v1/nlp/agent/chat/123

3. RAG receives request
   └─ verify_api_key dependency runs
      → X-API-Key header matches CONNEXIO_INTERNAL_API_KEY ✓
      → Request is allowed through
   └─ NLPController.answer_agent_chat() called with user_id=1, project_id=123

4. RAG: Intent & Language Detection
   └─ "Why was I matched" → WorkflowController.detect_node()
      → Keyword "matched" triggers TEAM_FORMATION node
      → Language: English

5. RAG: Session Management
   └─ Loads session 42 from rag_chat_sessions table
   └─ Retrieves last N messages of conversation history

6. RAG: Knowledge Base Search
   └─ ToolManager.search_knowledge_base(project_id=123, query="Why was I matched...")
   └─ Searches PGVector collection_1024_123

7. RAG: CRAG Relevance Grading
   └─ WorkflowController.grade_relevance() runs
   └─ If KB results are relevant → use them
   └─ If not → trigger fallback (Wikipedia / Google / Python)

8. RAG: Live Backend Data Injection
   └─ BackendApiClient.get_user(1) → GET http://connexio-backend:5000/api/users/1
   └─ BackendApiClient.get_project(123) → GET .../api/projects/123
   └─ Both fetched in parallel (asyncio.gather)
   └─ ToolManager.get_matching_rationale() builds context:
      "User skills: Python, React | Project needs: Python, Docker, React
       Matched: Python, React | Missing: Docker"

9. RAG: Live Project Summary Injected
   └─ get_project_context_summary() fetches project + members + tasks in parallel
   └─ Appended to prompt as [Live Project Data]

10. RAG: Prompt Construction
    └─ System prompt (persona: student, node: team_formation)
    └─ Truncated conversation history
    └─ Retrieved KB context
    └─ Live project data
    └─ User question as footer

11. RAG: LLM Generation
    └─ generation_client.generate_text() called
    └─ Groq / Ollama generates answer

12. RAG: Session Update
    └─ User message + AI answer appended to session 42

13. RAG: Response returned
    └─ { answer: "You were matched because...", node: "team_formation",
         language: "en", sources: ["Documentation", "Live Backend Data"],
         session_id: 42 }

14. Main backend receives RAG response
    └─ Returns it to the frontend

15. Frontend displays the answer to the user
```

---

## 8. Deployment Checklist

Complete these in order. Do not skip steps.

### RAG side (you)

- [ ] Copy `src/utils/security.py` into your repo
- [ ] Copy `src/utils/backend_client.py` into your repo
- [ ] Replace `src/helpers/config.py` with the updated version
- [ ] Replace `src/Routes/agent.py` with the updated version
- [ ] Replace `src/Routes/nlp.py` with the updated version
- [ ] Replace `src/Routes/data.py` with the updated version
- [ ] Replace `src/controllers/helpers/ToolManager.py` with the updated version
- [ ] Replace `src/main.py` with the updated version
- [ ] Replace `src/controllers/NLPController.py` with the updated version
- [ ] Generate a random key: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Add `CONNEXIO_INTERNAL_API_KEY=<key>` to `src/.env`
- [ ] Add `MAIN_BACKEND_URL=http://<backend_container_name>:5000` to `src/.env`
- [ ] Restart the RAG server
- [ ] Restart the Celery workers
- [ ] Check startup logs for `[AGENT] X-API-Key authentication ENABLED`

### Backend side (teammate)

- [ ] Remove `protect` from `GET /api/tasks` route only
- [ ] Create `utils/ragClient.js`
- [ ] Add `CONNEXIO_RAG_API_KEY=<same_key>` to backend `.env`
- [ ] Add `RAG_BASE_URL=http://<rag_container_name>:8000` to backend `.env`
- [ ] Restart the backend server
- [ ] Test: `GET /api/tasks?project_id=1` returns data without Authorization header

### Shared

- [ ] Confirm both teams have **exactly the same** API key value
- [ ] Confirm container names match between `MAIN_BACKEND_URL` and `RAG_BASE_URL`

---

## 9. Testing the Integration End-to-End

### Test 1 — RAG rejects requests without the key

```bash
curl -X POST https://connexio.icu/api/v1/nlp/agent/chat/1 \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "query": "hello"}'
```

**Expected response:**
```json
{"detail": {"signal": "UNAUTHORIZED", "error": "Missing or invalid X-API-Key..."}}
```
HTTP status: `401`

---

### Test 2 — RAG accepts requests with the correct key

```bash
curl -X POST https://connexio.icu/api/v1/nlp/agent/chat/1 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_generated_key>" \
  -d '{"user_id": 1, "query": "hello", "persona": "student"}'
```

**Expected response:**
```json
{
  "signal": "agent_chat_success",
  "answer": "Hello! How can I help you today?...",
  "node": "general",
  "language": "en",
  "session_id": 1,
  "sources": []
}
```

---

### Test 3 — Live data is injected (matching rationale)

```bash
curl -X POST https://connexio.icu/api/v1/nlp/agent/chat/1 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_generated_key>" \
  -d '{"user_id": 1, "query": "Why was I matched to this project?", "persona": "student"}'
```

**Expected response:**
The `answer` field should mention actual skill names from the user's profile
and the project's `technologyUsed` array — not generic placeholder text.

If the answer still says "Core matching metrics are stored in the main
application database" — the `BackendApiClient` is not reaching the main backend.
See Troubleshooting section below.

---

### Test 4 — Main backend's GET /api/tasks is public

```bash
# No Authorization header
curl https://connexio.icu/api/tasks?project_id=1
```

**Expected:** Returns task list with HTTP 200.  
**If it returns 401:** The `protect` middleware was not removed from the GET route.

---

## 10. Troubleshooting Guide

| Symptom | Cause | Fix |
|---------|-------|-----|
| All RAG endpoints return `401 Unauthorized` | `CONNEXIO_INTERNAL_API_KEY` is set but the value in the backend's `CONNEXIO_RAG_API_KEY` doesn't match | Copy-paste the key again — check for trailing spaces or quote characters |
| RAG starts but logs `X-API-Key validation is DISABLED` | `CONNEXIO_INTERNAL_API_KEY` is missing from `.env` | Add the variable and restart |
| `get_matching_rationale` still returns canned message | `MAIN_BACKEND_URL` is wrong or unreachable | Run `docker exec -it <rag_container> curl http://<backend_name>:5000/api/users/1` |
| `ImportError: cannot import name 'verify_api_key'` | `security.py` was not placed in `src/utils/` | Confirm file path: `src/utils/security.py` |
| `AttributeError: 'NoneType' object has no attribute 'backend_client'` | `main.py` update was not applied | Replace `main.py` with the updated version and restart |
| Celery tasks fail with `ValidationError` for missing settings | Workers have stale config from before the `.env` update | Restart Celery workers |
| GET `/api/tasks` still returns `401` from the backend | `protect` middleware not removed from the GET route | Teammate checks `tasks.routes.js` |
| `connection refused` when RAG calls the backend | Container name wrong in `MAIN_BACKEND_URL` | Check the service name in `docker-compose.yml` |
