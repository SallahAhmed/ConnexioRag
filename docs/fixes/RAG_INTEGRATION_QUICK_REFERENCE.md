# RAG Integration — AI Agent Quick Reference Card

## 🎯 What Was Done (May 11, 2026)

Connexios RAG has been **fully integrated** with the main Connexio backend using a microservices architecture with shared API key authentication.

---

## 🔑 Key Concepts

### X-API-Key Security Model
- **Shared secret** between RAG and Backend: `90abeeeaa98cec6d68c47bebf65400ba3eb4cdb89ca87d0958d9c3b25533b091`
- Flows **inward only** (Backend → RAG), never reverse
- Every RAG request must include this header or gets 401 Unauthorized

### Live Data Integration
- RAG no longer uses hardcoded SQL against non-existent tables
- All live data fetched via REST calls to Backend's public endpoints
- Data cached in-memory for 5 minutes (except tasks which update frequently)
- Zero direct database access — RAG communicates only through REST API

---

## 📦 What Changed

### New Files
| File | Purpose |
|------|---------|
| `src/utils/security.py` | API key validation (FastAPI dependency) |
| `src/utils/backend_client.py` | HTTP client with caching & retry logic |

### Modified Files (8 total)
| File | Change |
|------|--------|
| `src/helpers/config.py` | Added CONNEXIO_INTERNAL_API_KEY, MAIN_BACKEND_URL settings |
| `src/Routes/agent.py` | Protected with X-API-Key; backend_client injected |
| `src/Routes/nlp.py` | Protected with X-API-Key |
| `src/Routes/data.py` | Protected with X-API-Key |
| `src/main.py` | Creates BackendApiClient singleton at startup |
| `src/controllers/NLPController.py` | Accepts & passes backend_client to ToolManager |
| `src/controllers/helpers/ToolManager.py` | 3 methods rewritten + new method |
| `src/.env` | Added API key + backend URL |

---

## 🔧 ToolManager Updates

### Methods Rewritten
1. **`get_matching_rationale(user_id, project_id)`**
   - Before: SQL against non-existent tables → always failed
   - After: Fetches actual user skills + project tech via REST → LLM generates personalized explanation

2. **`get_team_gaps(project_id)`**
   - Before: SQL against non-existent tables → always failed
   - After: Fetches all team members + project requirements via REST → LLM generates gap analysis

### New Method
3. **`get_project_context_summary(project_id)`**
   - Fetches project details + team members + task list in parallel
   - Returns text summary injected into prompts as `[Live Project Data]`
   - Runs for every chat response (except OUT_OF_SCOPE node)

---

## 📡 Request Flow

```
User Query
    ↓
Main Backend (JWT validation)
    ↓
RAG (X-API-Key validation)
    ↓
NLPController (route to handler)
    ↓
ToolManager (fetch live data via BackendApiClient)
    ↓
Backend Public API (returns user/project/team/task data)
    ↓
RAG LLM (generates response with live data injected)
    ↓
Main Backend (receives response)
    ↓
Frontend (displays answer to user)
```

---

## ⚙️ Configuration

### RAG Side (✅ Complete)
```env
CONNEXIO_INTERNAL_API_KEY=90abeeeaa98cec6d68c47bebf65400ba3eb4cdb89ca87d0958d9c3b25533b091
MAIN_BACKEND_URL=http://connexio-backend:3000
```

### Backend Side (⏳ Pending)
```env
CONNEXIO_RAG_API_KEY=90abeeeaa98cec6d68c47bebf65400ba3eb4cdb89ca87d0958d9c3b25533b091
RAG_BASE_URL=http://connexios:8000
```

---

## 🧪 How to Test

### Test 1: Security Works
```bash
# Should fail without X-API-Key
curl -X POST http://connexios:8000/api/v1/nlp/agent/chat/1 \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "query": "hello"}'
# Expected: 401 Unauthorized
```

### Test 2: Live Data Works
```bash
# Should succeed with X-API-Key + return live data
curl -X POST http://connexios:8000/api/v1/nlp/agent/chat/1 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 90abeeeaa98cec6d68c47bebf65400ba3eb4cdb89ca87d0958d9c3b25533b091" \
  -d '{"user_id": 1, "query": "Why was I matched?", "persona": "student"}'
# Expected: 200 OK with personalized response mentioning actual user skills
```

---

## ⚠️ Critical Notes for AI Agent

1. **API Key has NO angle brackets** — Must be plain 64-character hex string
2. **X-API-Key flows inward only** — RAG endpoints require it; Backend public endpoints don't
3. **Backend container name matters** — Must match docker-compose.yml service name
4. **Celery workers cache config** — Restart them if .env changes
5. **Live data injection is automatic** — get_project_context_summary() runs on every query

---

## 📍 File Locations

- Full integration guide: `docs/INTEGRATION_COMPLETE_SUMMARY.md`
- Original walkthrough: `docs/fixes/INTEGRATION_WALKTHROUGH.md`
- Configuration: `src/.env`
- Security validation: `src/utils/security.py`
- Backend client: `src/utils/backend_client.py`
- ToolManager (data tools): `src/controllers/helpers/ToolManager.py`

---

## 🎯 Deployment Checklist

- [x] RAG security layer implemented ✅
- [x] Backend client with caching implemented ✅
- [x] ToolManager methods rewritten for REST calls ✅
- [x] API key generated and configured ✅
- [x] Configuration fields added ✅
- [ ] Backend team updates their config
- [ ] Backend team creates ragClient.js
- [ ] Container names verified in docker-compose
- [ ] Services restarted
- [ ] Testing completed

---

## 💡 When Future Changes Are Needed

If you need to:
- **Change API key:** Update both CONNEXIO_INTERNAL_API_KEY (RAG) and CONNEXIO_RAG_API_KEY (Backend)
- **Change backend URL:** Update MAIN_BACKEND_URL in RAG .env
- **Add new REST endpoints:** Use BackendApiClient methods in ToolManager
- **Debug backend connectivity:** Run `docker exec -it connexios curl http://connexio-backend:3000/api/users/1`

---

**Status: Integration Complete ✅ — Awaiting Backend Team Configuration**
