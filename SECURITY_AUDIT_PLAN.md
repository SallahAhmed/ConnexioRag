# Connexios RAG — Security Audit & Fix Plan

**Status:** Draft — Awaiting Investigation Answers
**Date:** 2026-06-08

---

## Part 1: Investigation Questions (Must Answer Before Executing Fixes)

### Q1: Node.js Backend — Project ID Format
**Where to check:** `github.com/Hassan19Z/Connexio-backend` — the Node.js backend repository.

The RAG expects `project_id` as an **integer** in the URL path:
- `POST /api/v1/nlp/agent/chat/{project_id}` — route definition at `src/Routes/agent.py:54`
- `GET /api/v1/nlp/agent/chat/stream/{project_id}` — route definition at `src/Routes/agent.py:83`

**Investigate in the Node.js backend:**
1. Find where the Node.js backend calls the RAG API. Search for URLs containing `/api/v1/nlp/agent/chat/` or references to `ConnexioRag` / the RAG service URL.
2. What value does it put in the `{project_id}` path segment? Is it:
   - (a) An integer from MySQL (like `42`)?
   - (b) A UUID string (like `a1b2c3d4-...`)?
   - (c) A hashed/encoded value?
3. Check the MySQL database schema — how is `PID` defined in the `projects` table? Is it `INT AUTO_INCREMENT` or a UUID?
4. Search for any hashing/encoding of `PID` before sending it to the RAG.

**Why this matters:** If the backend sends a non-integer, FastAPI returns `422` and the RAG never processes the request. If it sends the wrong integer, the RAG queries the wrong collection.

---

### Q2: Cache Invalidation Callers
**Where to check:** Node.js backend repository.

The RAG has these cache invalidation endpoints:
- `POST /api/v1/nlp/agent/cache/invalidate/{project_id}` — `src/Routes/agent.py:125`
- `POST /api/v1/nlp/agent/cache/invalidate/user/{user_id}` — `src/Routes/agent.py:143`

**Investigate in the Node.js backend:**
1. Does the backend call these endpoints after updating projects/users?
2. If yes, what triggers the call? (project update, member change, etc.)
3. If no, these endpoints can be safely removed.

---

### Q3: Global Collection Usage
**Where to check:** RAG codebase (`src/`) + Node.js backend.

The RAG currently searches a "global" vector collection (`collection_{size}_0`) for every query:
- `src/controllers/helpers/ToolManager.py:257-266` (search_knowledge_base)
- `src/controllers/helpers/ToolManager.py:328-338` (search_knowledge_base_raw)

**Investigate:**
1. In the Node.js backend, find where documents are uploaded/indexed to the RAG. Search for calls to `/api/v1/data/upload/` or `/api/v1/nlp/index/push/`.
2. Does the backend ever send `project_id=0` when indexing documents? (This would put documents in the global collection.)
3. Are there any documents that SHOULD be shared across all projects? If not, removing the global collection search is safe.

---

### Q4: Authentication Flow Verification
**Where to check:** Both repositories.

The RAG trusts `user_id` from the request body without verifying membership:
- `src/Routes/schemas/agent.py:8` — `user_id: int` from request body
- `src/Routes/agent.py:61` — `user_id=chat_request.user_id` passed directly to controller

**Investigate in the Node.js backend:**
1. When the backend forwards a user's chat request to the RAG, does it validate that the user is a member of the project FIRST?
2. Does the backend always send the correct `user_id` and `project_id` pair, or could a bug cause mismatched values?
3. The plan assumes the backend is trusted (per owner's decision). Confirm this is still the case.

---

### Q5: `?pid=` Override Origin
**Where to check:** Node.js backend + any frontend code.

The RAG has a `?pid=` query parameter override at `src/Routes/agent.py:46-52` that allows overriding the project_id from the URL path.

**Investigate:**
1. Does the Node.js backend ever send `?pid=` when calling the RAG?
2. Does the frontend directly call the RAG (bypassing the backend)?
3. If no one uses `?pid=`, it should be removed. If the backend uses it, we need to understand why.

---

## Part 2: Fix Plan (Execute After Investigation)

### Fix 1: Remove `?pid=` Override [CRITICAL]
**File:** `src/Routes/agent.py`

**Current code (lines 46-52):**
```python
def resolve_pid(project_id: int, request: Request) -> Optional[int]:
    """Resolve effective project ID with override via ?pid= or ?PID= query param."""
    for key in ("PID", "pid"):
        override = request.query_params.get(key)
        if override and override.isdigit() and int(override) > 0:
            return int(override)
    return None if project_id == 0 else project_id
```

**Action:**
- Delete the `resolve_pid()` function entirely
- In `agent_chat` (line 59): change `effective_project_id = resolve_pid(project_id, request)` → remove it, use `project_id` directly
- In `agent_chat_stream` (line 95): same change
- Remove `from typing import Optional` if no longer needed (check first)

**Depends on:** Q5 answer (confirm no one uses `?pid=`)

---

### Fix 2: Remove Global Collection Search [HIGH]
**File:** `src/controllers/helpers/ToolManager.py`

**Current code (search_knowledge_base, lines 245-266):**
```python
# Search project KB
project_collection = self._get_collection_name(project_id)
# ... search project KB ...

# Search global KB  ← REMOVE THIS BLOCK
try:
    global_results = await self.vectordb_client.hybrid_search(
        collection_name=self.get_global_collection_name(), ...)
except Exception:
    global_results = await self.vectordb_client.search_by_vector(
        collection_name=self.get_global_collection_name(), ...)
add_results(global_results, "global_")
```

**Action:**
- In `search_knowledge_base()`: delete lines 257-266 (global KB search + `add_results(global_results, "global_")`)
- In `search_knowledge_base_raw()`: delete lines 328-338 (same pattern)
- Delete `get_global_collection_name()` method (lines 197-198)
- Keep the `project_id=0` fallback in `NLPController.py:423` — when project_id is 0, it will simply find no collection and return empty, triggering CRAG tools

**Depends on:** Q3 answer (confirm no shared documents exist in global collection)

---

### Fix 3: Verify CRAG Fallback Works Without Global KB [MEDIUM]
**File:** `src/controllers/NLPController.py`

**No code change needed** — the existing logic already handles this:
- Line 422-423: `raw_docs = await self.tool_manager.search_knowledge_base_raw(project_id=..., query=query, limit=limit)`
- Line 426-433: If `raw_docs` is empty → fires 2 CRAG tools (Google, Wikipedia, ArXiv, etc.)
- Line 706-710 in `_run_crag_tools()`: Google is already in the available tools list when `serpapi_api_key` is set

**Action:** After Fix 2, test by querying with a project that has no documents. Verify Google/Wikipedia results are returned.

---

### Fix 4: SQL Injection Hardening [HIGH]
**File:** `src/stores/vectordb/providers/PGVectorProvider.py`

**Current dangerous patterns:**
```python
# Line 81 — collection_name in f-string:
count_sql = sql_text(f'SELECT COUNT(*) FROM {collection_name}')

# Line 100 — collection_name in f-string:
delete_sql = sql_text(f'DROP TABLE IF EXISTS {collection_name}')

# Line 305 — limit in f-string:
f'LIMIT {limit}'
```

**Action:**
1. Add validation function at top of file:
```python
import re
_VALID_COLLECTION = re.compile(r'^collection_\d+_\d+$')

def _validate_collection(name: str) -> str:
    if not _VALID_COLLECTION.match(name):
        raise ValueError(f"Invalid collection name: {name}")
    return name
```

2. Call `_validate_collection(collection_name)` at the entry of:
   - `create_collection()`
   - `delete_collection()`
   - `search_by_vector()`
   - `search_by_text()`
   - `hybrid_search()`
   - `insert_one()`
   - `insert_many()`
   - `get_collection_info()`
   - `is_collection_existed()`

3. Parameterize `limit` in `search_by_vector()` (line 305):
```python
# Before:
f'LIMIT {limit}'
# After:
'LIMIT :limit'
# Then add to the execute params: {"vector": vector, "limit": limit}
```

4. Same for `search_by_text()` (line 336).

---

### Fix 5: Stop Auto-Creating Phantom Projects [MEDIUM]
**File:** `src/models/ProjectModel.py`

**Current code (lines 25-40):**
```python
async def get_project_or_create_one(self, project_id: int):
    async with self.db_client() as session:
        async with session.begin():
            query = select(Project).where(Project.project_id == project_id)
            result = await session.execute(query)
            project = result.scalar_one_or_none()
            if project is None:
                project_rec = Project(project_id=project_id)
                project = await self.create_project(project=project_rec)  # ← AUTO-CREATES
                return project
            else:
                return project
```

**Action:**
- Change to return `None` when project doesn't exist:
```python
if project is None:
    return None
```

- Update all callers to handle `None`:
  - `src/Routes/data.py:38` — add `if project is None: return 404`
  - `src/Routes/nlp.py:42-44` — add `if project is None: return 404`
  - `src/Routes/nlp.py:72-74` — add `if project is None: return 404`
  - `src/Routes/data.py:265` — add `if project is None: return 404`
  - `src/Routes/data.py:349` — add `if project is None: return 404`

---

### Fix 6: Session History Project-Scoping [MEDIUM]
**File:** `src/models/SessionModel.py`

**Current code (lines 54-58):**
```python
query = select(ChatSession).where(ChatSession.user_id == user_id)
if project_id:
    query = query.where(ChatSession.project_id == project_id)
```

**Problem:** When `project_id` is `None`, the query returns the most recent session for the user regardless of which project it belongs to.

**Action:**
```python
query = select(ChatSession).where(ChatSession.user_id == user_id)
if project_id:
    query = query.where(ChatSession.project_id == project_id)
else:
    query = query.where(ChatSession.project_id.is_(None))
```

---

### Fix 7: Rate Limit Per-User [LOW]
**File:** `src/Routes/agent.py`

**Current code (line 16, 55, 84):**
```python
limiter = Limiter(key_func=get_remote_address)
# ...
@limiter.limit("30/minute")
```

**Problem:** All requests from the Node.js backend share the same IP, so all users share one rate limit bucket.

**Action:**
- Create a custom key function that combines IP + user_id:
```python
def user_rate_key(request: Request) -> str:
    """Rate limit by IP + user_id to handle proxied requests."""
    ip = get_remote_address(request)
    user_id = getattr(request, '_user_id', None)
    if user_id:
        return f"{ip}:{user_id}"
    return ip
```

- For the POST endpoint, extract `user_id` from the request body before rate limiting (this requires a custom middleware or dependency since FastAPI rate limiting happens before body parsing). **Simpler alternative:** keep per-IP limiting and document the limitation.

---

### Fix 8: Remove Dead Config [LOW]
**File:** `src/helpers/config.py`

**Action:** Delete line 40:
```python
GENERATION_MODEL_ID_LITERAL: List[str] | None = None  # ← DELETE THIS
```

---

### Fix 9: Secure or Remove Cache Invalidation Endpoints [MEDIUM]
**File:** `src/Routes/agent.py`

**Depends on:** Q2 answer.

**If backend calls these endpoints:**
- Keep them but add project_id validation (only invalidate if the project exists)
- Or move invalidation logic to be triggered internally when the backend calls other endpoints

**If no one calls them:**
- Delete `invalidate_cache()` (lines 125-140)
- Delete `invalidate_user_cache()` (lines 143-156)
- Remove `invalidate_project_cache()` and `invalidate_user_cache()` from `BackendApiClient` if no longer needed

---

### Fix 10: Project ID Hashing Investigation [BLOCKED]
**Status:** Waiting for Q1 answer.

**If the Node.js backend sends integer PIDs:** No change needed — the RAG already handles integers correctly.

**If the Node.js backend sends UUIDs/hashes:**
- Option A: Change the Node.js backend to send integer PIDs
- Option B: Change the RAG routes to accept string project_ids and look up the integer PID via `project_id_map` table
- Option B code change in `src/Routes/agent.py`:
```python
# Change route from:
@agent_router.post("/chat/{project_id}")
async def agent_chat(request: Request, project_id: int, ...):
# To:
@agent_router.post("/chat/{project_id}")
async def agent_chat(request: Request, project_id: str, ...):
    # Resolve string PID to integer
    integer_pid = await resolve_string_pid(project_id)
```

---

## Part 3: Testing Checklist

After all fixes are applied:

1. **Security test:** Send a chat request with `user_id=999, project_id=1` — verify it works only if user 999 is a member of project 1 (depends on Q4)
2. **`?pid=` test:** Send `POST /api/v1/nlp/agent/chat/1?pid=2` — verify project 2 is NOT queried
3. **Global KB test:** Query a project with no documents — verify Google/CRAG tools are used instead of global collection
4. **SQL injection test:** Try creating a collection with name `collection_1024_1; DROP TABLE projects;--` — verify it's rejected
5. **Phantom project test:** Query a non-existent project_id — verify 404 instead of auto-created row
6. **Session scoping test:** User with sessions in projects A and B — verify global chat doesn't mix history
7. **Run existing tests:** `python -m pytest tests/ -v --tb=short` — all 42 tests should still pass

---

## Part 4: Execution Order

| Phase | Fixes | Depends On |
|-------|-------|------------|
| **Phase 1: Investigation** | Answer Q1-Q5 | User / Backend dev |
| **Phase 2: Critical security** | Fix 1, Fix 2, Fix 4 | Q3, Q5 answers |
| **Phase 3: Data integrity** | Fix 5, Fix 6, Fix 3 | None |
| **Phase 4: Cleanup** | Fix 7, Fix 8, Fix 9 | Q2 answer |
| **Phase 5: Project ID** | Fix 10 | Q1 answer |
| **Phase 6: Testing** | Run full test suite | All fixes applied |
