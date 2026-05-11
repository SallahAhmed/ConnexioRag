# Connexios RAG × Connexio Backend — Integration Complete ✅

**Date:** May 11, 2026  
**Status:** Implementation Complete — Ready for Deployment  
**Integration Type:** Microservices (Service-to-Service)

---

## 📋 Quick Summary

The Connexios RAG system has been fully integrated with the main Connexio backend. The RAG now:
- ✅ Validates all inbound requests using a shared `X-API-Key` header
- ✅ Fetches live project/user/task data from the main backend via REST API
- ✅ Injects live data into prompts for grounded AI responses
- ✅ Caches stable data (5 min) while keeping volatile data fresh

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────┐
│     Browser / Mobile        │ (No direct RAG access)
└────────────┬────────────────┘
             │ JWT Token
             ▼
┌─────────────────────────────┐
│  Main Connexio Backend      │ (Node.js, port 3000)
│  - Validates JWT            │
│  - Calls RAG with X-API-Key │
│  - Returns answers to app   │
└────────────┬────────────────┘
             │ X-API-Key: shared_secret
             │ POST: user_id, query
             ▼
┌─────────────────────────────┐
│   Connexios RAG (FastAPI)   │ (port 8000)
│   - Validates X-API-Key     │
│   - Fetches live data ↓     │
│   - Generates responses     │
└────────────┬────────────────┘
             │ GET (public, no auth)
             ▼
┌─────────────────────────────┐
│  Main Backend Public API    │
│  - /api/users/{id}          │
│  - /api/projects/{id}       │
│  - /api/projects/{id}/members
│  - /api/tasks?project_id={id}
└─────────────────────────────┘
```

---

## 🔐 Security Model

### X-API-Key Header
- **What:** A 64-character hex string (generated via `secrets.token_hex(32)`)
- **Flow:** Main backend → RAG only (never reverse)
- **Current Value:** `90abeeeaa98cec6d68c47bebf65400ba3eb4cdb89ca87d0958d9c3b25533b091`
- **Configuration:**
  - RAG: `CONNEXIO_INTERNAL_API_KEY` in `src/.env`
  - Backend: `CONNEXIO_RAG_API_KEY` in backend `.env`
  - **Both must be identical**

### User Identity
- Main backend extracts `user_id` from JWT
- Main backend sends `user_id` in request body to RAG
- RAG trusts `user_id` only because X-API-Key header proves request came from main backend
- Frontend never sends `user_id` directly (main backend always proxies)

---

## 📁 Files Changed

### New Files (2)

#### `src/utils/security.py`
- **Purpose:** FastAPI dependency function `verify_api_key()`
- **Behavior:** 
  - Runs on every request to protected routes
  - Compares `X-API-Key` header to `CONNEXIO_INTERNAL_API_KEY` from `.env`
  - Returns 401 if invalid or missing
  - Dev-mode bypass if key not configured
- **Applied to:** All routes in `agent.py`, `nlp.py`, `data.py`

#### `src/utils/backend_client.py`
- **Purpose:** HTTP client to call main backend's public read endpoints
- **Features:**
  - Automatic retry (up to 2 retries with exponential backoff)
  - In-memory caching for stable data (5 minutes)
  - Timeout handling (10 seconds per request)
  - No auth headers (endpoints are public)
- **Methods:**
  - `get_user(user_id)` → Returns profile + skills + technologies
  - `get_project(project_id)` → Returns project details + tech stack
  - `get_project_members(project_id)` → Returns team member list
  - `get_project_tasks(project_id)` → Returns task list (no caching)
  - `get_rich_context(user_id, project_id)` → Fetches all four in parallel

### Updated Files (8)

#### `src/helpers/config.py`
- Added: `CONNEXIO_INTERNAL_API_KEY: str | None = None`
- Added: `MAIN_BACKEND_URL: str = "http://localhost:3000"`
- Both optional with safe defaults for local development

#### `src/Routes/agent.py`
- Added: `dependencies=[Depends(verify_api_key)]` to router definition
- Added: `backend_client=getattr(request.app, 'backend_client', None)` to controller initialization
- Result: Every endpoint now requires valid X-API-Key; BackendApiClient available to NLPController

#### `src/Routes/nlp.py`
- Added: `dependencies=[Depends(verify_api_key)]` to router definition
- Result: Index, search, and info endpoints now protected by X-API-Key

#### `src/Routes/data.py`
- Added: `dependencies=[Depends(verify_api_key)]` to router definition
- Result: Upload and processing endpoints now protected by X-API-Key

#### `src/main.py`
- Added: `from utils.backend_client import BackendApiClient`
- Added: Instantiation of `app.backend_client` in `startup_span()`
- Added: Logging to indicate whether X-API-Key validation is ENABLED or DISABLED
- Result: BackendApiClient singleton created once at startup, shared across all requests

#### `src/controllers/NLPController.py`
- Constructor now accepts: `backend_client=None`
- Passes `backend_client` to ToolManager initialization
- Result: ToolManager has access to live backend data

#### `src/controllers/helpers/ToolManager.py`
- **Three methods rewritten:**
  - `get_matching_rationale(user_id, project_id)` — Now fetches actual user skills + project tech, builds personalized explanation using LLM
  - `get_team_gaps(project_id)` — Now fetches team members + project tech requirements, generates gap analysis
  - `get_project_context_summary(project_id)` — NEW: Fetches project + members + tasks in parallel, returns text summary for prompt injection
- Constructor now accepts: `backend_client=None`
- Graceful fallback if backend_client is None (e.g., in Celery workers)

#### `src/.env`
- Added: `CONNEXIO_INTERNAL_API_KEY=90abeeeaa98cec6d68c47bebf65400ba3eb4cdb89ca87d0958d9c3b25533b091`
- Added: `MAIN_BACKEND_URL=http://connexio-backend:3000`
- **Note:** Container name must match actual service name in docker-compose.yml

---

## 🔄 Data Flow Example

**User asks:** "Why was I matched to this project?"

```
1. Browser sends JWT to main backend
   POST /api/rag/chat/123
   
2. Main backend validates JWT → extracts UID=1
   Calls RAG with X-API-Key header
   POST http://connexios:8000/api/v1/nlp/agent/chat/123
   Headers: X-API-Key: 90abeeeaa...
   Body: { user_id: 1, query: "Why was I matched...", persona: "student" }

3. RAG: verify_api_key() middleware
   ✓ X-API-Key matches CONNEXIO_INTERNAL_API_KEY
   Request allowed through

4. RAG: NLPController routes to WorkflowController
   Detects intent: TEAM_FORMATION node

5. RAG: ToolManager.get_matching_rationale(1, 123)
   Calls in parallel:
   - BackendApiClient.get_user(1)
   - BackendApiClient.get_project(123)

6. Main backend responds with:
   User: { UID: 1, FullName: "Alice", technologies: "Python,React", 
           skills: ["Frontend", "Backend"], rate: 4.5, years_of_experience: 3 }
   Project: { PID: 123, PName: "E-Commerce Portal", 
              technologyUsed: ["Python", "React", "Docker"], ... }

7. RAG: ToolManager builds LLM prompt
   "User Alice (UID:1) has skills: Python, React.
    Project requires: Python, React, Docker.
    Matched: Python, React. Missing: Docker.
    Explain why she was matched using 6-factor algorithm."

8. RAG: Generation client generates response
   "Alice was matched to this project because she has strong experience 
    with Python and React, which are core technologies..."

9. RAG returns response to main backend
   { answer: "...", session_id: 42, node: "team_formation", ... }

10. Main backend returns response to frontend
    Frontend displays answer to user
```

---

## 🚀 Deployment Checklist

### RAG Side (Completed ✅)
- [x] New files created: security.py, backend_client.py
- [x] Config updated with CONNEXIO_INTERNAL_API_KEY and MAIN_BACKEND_URL
- [x] All three routers protected by verify_api_key dependency
- [x] NLPController and ToolManager updated to use BackendApiClient
- [x] main.py instantiates BackendApiClient on startup
- [x] API key value set in .env (without angle brackets)
- [x] Startup logs show whether X-API-Key validation is enabled

### Backend Side (To Do — Teammate)
- [ ] Create `utils/ragClient.js` with `callRagChat()` function
- [ ] Update `.env` with `CONNEXIO_RAG_API_KEY=<same_key>` and `RAG_BASE_URL=http://connexios:8000`
- [ ] Remove `protect` middleware from `GET /api/tasks` route only
- [ ] Restart backend service
- [ ] Test: GET /api/tasks without Authorization header returns 200

---

## ⚙️ Configuration Reference

### RAG `.env` (`src/.env`)
```env
CONNEXIO_INTERNAL_API_KEY=90abeeeaa98cec6d68c47bebf65400ba3eb4cdb89ca87d0958d9c3b25533b091
MAIN_BACKEND_URL=http://connexio-backend:3000
```

### Backend `.env` (NodeJS / Connexio Backend)
```env
CONNEXIO_RAG_API_KEY=90abeeeaa98cec6d68c47bebf65400ba3eb4cdb89ca87d0958d9c3b25533b091
RAG_BASE_URL=http://connexios:8000
```

### Docker Compose Service Names
- RAG container: `connexios` (or verify actual name)
- Backend container: `connexio-backend` (verify in docker-compose.yml)

---

## 🧪 Testing Endpoints

### Test 1: Reject requests without X-API-Key
```bash
curl -X POST http://connexios:8000/api/v1/nlp/agent/chat/1 \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "query": "hello"}'
```
**Expected:** `401 Unauthorized`

### Test 2: Accept requests with correct X-API-Key
```bash
curl -X POST http://connexios:8000/api/v1/nlp/agent/chat/1 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 90abeeeaa98cec6d68c47bebf65400ba3eb4cdb89ca87d0958d9c3b25533b091" \
  -d '{"user_id": 1, "query": "Why was I matched?", "persona": "student"}'
```
**Expected:** `200 OK` with AI response containing live data

### Test 3: Verify live data injection
- Answer should mention actual user skills from backend
- Answer should mention actual project tech stack from backend
- Answer should include team size and project name

---

## ⚠️ Known Limitations & Potential Issues

### Issue #1: Main Backend URL Unreachable
**Symptom:** ToolManager methods return canned messages without live data  
**Cause:** `MAIN_BACKEND_URL` container name doesn't match docker-compose.yml  
**Fix:** Update `MAIN_BACKEND_URL` to match actual container service name  
**Debug:**
```bash
docker exec -it connexios curl http://connexio-backend:3000/api/users/1
# Should return JSON if connectivity is OK
```

### Issue #2: Stale Celery Worker Config
**Symptom:** Celery tasks fail or don't use new config  
**Cause:** Workers loaded config at startup before .env was updated  
**Fix:** Restart all Celery workers after any `.env` change

### Issue #3: Circular Import in security.py
**Note:** `get_settings()` is imported inside the function (not at module top) to avoid circular dependencies  
**Fix needed if:** You move `get_settings()` to a different module — update import path in `security.py`

---

## 📚 Reference Documents

- Original integration walkthrough: [INTEGRATION_WALKTHROUGH.md](./fixes/INTEGRATION_WALKTHROUGH.md)
- API architecture: [API_GUIDE.md](./API_GUIDE.md)
- App overview: [app_overview.md](./app_overview.md)

---

## 🎯 Next Steps

1. ✅ **RAG side complete** — All code changes applied, API key configured
2. ⏳ **Backend side** — Send this to your backend teammate with the integration guide
3. ⏳ **Container naming** — Verify container names in docker-compose.yml match configuration
4. ⏳ **API key sharing** — Backend team must use same API key value
5. ⏳ **Testing** — Run the three test endpoints above after deployment
6. ⏳ **Deployment** — Deploy to production following deployment checklist

---

**Status: Ready for backend integration and deployment testing** ✅
