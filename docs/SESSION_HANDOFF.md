# Session Handoff — Full AI-Executable Plan

## Resume Command

> "Read SESSION_HANDOFF.md and execute the full integration plan. All 3 systems are in scope."

---

## 1. Project Inventory

| System | Path | URL | Language | DB |
|--------|------|-----|----------|----|
| **RAG** | `C:\Users\salla\Connexios\` | `https://sallahahmed-connexiorag.hf.space` | Python/FastAPI | PostgreSQL (Neon) |
| **MasarX** | `F:\MasarX_A\` | `https://sallahahmed-connexioagent.hf.space` | Python/FastAPI | PostgreSQL (Neon) |
| **Backend** | `F:\connexio_back2\` | `https://connexio.icu` | Node.js/Express | MySQL |
| **Frontend** | `F:\Connexio_Frontend2\` | Not deployed | React/Vite | — |

## 2. Environment & Auth

### API Key for RAG testing:
```
CONNEXIO_INTERNAL_API_KEY = <CONNEXIO_INTERNAL_API_KEY>
```

### JWT Secret (shared across all 3 backends):
```
JWT_SECRET = <JWT_SECRET>
```

### SERVICE_USER_ID on all systems = 2 (UID with backend access)

### Groq API Key:
```
GROQ_API_KEY = <GROQ_API_KEY>
```

## 3. RAG Current State (Already Complete)

### Models
- Generation: `openai/gpt-oss-120b` via Groq (~0.6s response)
- Utility: `meta-llama/llama-4-scout-17b-16e-instruct` via Groq
- Embedding: Cohere `embed-multilingual-v3.0` (1024d)

### Model Routing Logic (in `NLPController.py:449-458`)
```
PROJECT intents (ONBOARDING, TEAM_FORMATION, PHASE_TRANSITION, BLOCKER, MILESTONE_WARNING) → GPT-OSS 120B
GENERAL intents → Llama 4 Scout 17B (auto-escalate to 120B if answer echoes/refuses/is empty)
model_tier="generation" → force 120B
model_tier="utility" → force 17B
```

### Global KB
- `collection_1024_0` — 52 files, 134 chunks, 8 categories
- Searched for ALL queries (projectless + project contexts)
- Relevance grader bypassed for projectless mode

### Intent Detection Order (in `WorkflowController.py:25-139`)
1. OOS keywords (jailbreak, personal, weather, cooking, politics, etc.)
2. Project keywords (onboarding, team, phase, blocker, milestone)
3. GENERAL keywords (greetings, identity)
4. Fast path (<50 chars → GENERAL, unless _SKIP_FAST_PATH)
5. LLM classifier fallback

### Security
- Rate limiting: 30 req/min per IP (in `utils/metrics.py`)
- Input max_length: 5000 (in `Routes/schemas/agent.py`)
- 429 retry: exponential backoff (in `stores/llm/providers/OpenAIProvider.py`)
- Cache invalidation: `POST /api/v1/nlp/agent/cache/invalidate/{pid}`
- Settings cached globally (in `utils/security.py`)

### Prompt Templates
- EN: `stores/llm/templates/locales/en/rag.py` — persona styles, no markdown, concise
- AR: `stores/llm/templates/locales/ar/rag.py` — same in Arabic
- Workflow: `locales/en/workflow.py` — 7-node classification
- Footer: "Do not repeat the question. Reply in same language."

### Key Commands
```bash
# Test
curl -X POST https://sallahahmed-connexiorag.hf.space/api/v1/nlp/agent/chat/0 \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"query": "what does Connexio do?", "user_id": 1}'

# Health
curl https://sallahahmed-connexiorag.hf.space/api/v1/health

# Deploy to HF Spaces
cd C:\Users\salla\Connexios
git push hf main
```

---

## 4. Execution Plan — 7 Phases

### Phase 1: Fix MasarX DB Connection Pools

**Problem**: MasarX creates 3 separate engines/pools to the same Neon DB:
1. `main.py:40-44` — app engine
2. `db_tool.py:36-43` — separate engine in `initialize()`
3. `rag_tool.py:34-38` — separate engine in `_get_session_maker()`

Each pool consumes a Neon connection. Free tier has ~10 connection limit.

**Solution**: Share the engine from app state through db_tool.

**File**: `F:\MasarX_A\src\main.py` (lines 64-65)
```python
# After creating engine + session_maker, store in app state
app.state.db_engine = engine
app.state.session_maker = sessionmaker(...)

# PASS session_maker to db_tool
from utils.tools.db_tool import db_tool
await db_tool.initialize(session_maker=app.state.session_maker)
```

**File**: `F:\MasarX_A\src\utils\tools\db_tool.py` (lines 22-48)
```python
class DBTool:
    def __init__(self, db_url=None):
        self.engine = None
        self.session_maker = None
    
    async def initialize(self, session_maker=None):
        if session_maker:
            self.session_maker = session_maker
            # Share with rag_tool
            from stores.vectordb.rag_tool import rag_tool
            await rag_tool.initialize(session_maker=self.session_maker)
            return
        # Fallback: create own engine (only if no shared one provided)
        if not self.engine:
            ...existing code to create engine...
```

**File**: `F:\MasarX_A\src\stores\vectordb\rag_tool.py` (lines 12-39)
```python
async def initialize(self, session_maker=None):
    if session_maker:
        self.session_maker = session_maker
        return
    # Fallback to own engine
    ...existing code...
```

### Phase 2: Fix Schema Ownership

**Problem**: MasarX writes webhook results to `chunks` table via `save_document()`. The `chunks` table is owned by RAG (Alembic migrations). If RAG runs a migration, MasarX data breaks.

**Solution**: Create a MasarX-owned `masarx_webhook_results` table.

**File**: `F:\MasarX_A\src\models\db_schemas\live_models.py` (add after PendingPlan)
```python
class WebhookResult(Base):
    __tablename__ = "masarx_webhook_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(Integer, nullable=False)
    event_type = Column(String(100), nullable=False)
    intent = Column(String(100), nullable=False)
    status = Column(String(50), default="completed")
    invocation_id = Column(String(255), nullable=True)
    result_data = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**File**: `F:\MasarX_A\src\utils\tools\db_tool.py` — replace `save_document` (lines 244-257):
```python
async def save_webhook_result(self, result_data: dict) -> WebhookResult:
    from models.db_schemas.live_models import WebhookResult
    await self.initialize()
    async with self.session_maker() as session:
        record = WebhookResult(
            project_id=self._to_int(result_data.get("project_id")),
            event_type=result_data.get("event_type", ""),
            intent=result_data.get("intent", ""),
            status=result_data.get("status", "completed"),
            invocation_id=result_data.get("invocation_id"),
            result_data=result_data.get("result"),
            error=result_data.get("error"),
        )
        session.add(record)
        await session.commit()
        return record
```

**File**: `F:\MasarX_A\src\Routes\webhook_routes.py` — update `run_workflow()` (line 129):
Change:
```python
await webhook_db_tool.save_document({...})
```
To:
```python
await webhook_db_tool.save_webhook_result({...})
```

Add `MASARX_OWNED_TABLES` update in main.py (line 51):
```python
MASARX_OWNED_TABLES = {"user", "task", "masarx_notifications", "masarx_pending_plans", "masarx_webhook_results"}
```

### Phase 3: Build REST Bridge — MasarxApiClient

**Problem**: RAG has no way to read tasks or notifications from MasarX. The data is in the shared PostgreSQL but RAG has no models or client for MasarX tables.

**Solution**: Create `MasarxApiClient` in RAG that reads MasarX tables via direct DB queries (shared PostgreSQL).

**File**: `C:\Users\salla\Connexios\src\utils\masarx_client.py` (NEW)
```python
"""
HTTP client for calling the MasarX Agent API.
Alternatively reads MasarX-owned tables directly from shared PostgreSQL.
"""
import logging
from typing import Optional, List
from sqlalchemy import text as sql_text

logger = logging.getLogger(__name__)

class MasarxClient:
    def __init__(self, db_client=None):
        self.db_client = db_client
    
    async def get_tasks(self, project_id: int, limit: int = 20) -> List[dict]:
        if not self.db_client:
            return []
        try:
            async with self.db_client() as session:
                stmt = sql_text(
                    "SELECT t.\"TaskId\", t.\"TaskName\", t.\"TaskDesc\", "
                    "t.status, t.priority, t.story_points, t.deadline, "
                    "t.\"UID\", u.name as assignee_name "
                    "FROM task t "
                    "LEFT JOIN \"user\" u ON t.\"UID\" = u.\"UID\" "
                    "WHERE t.\"PID\" = :pid "
                    "ORDER BY t.created_at DESC LIMIT :lim"
                )
                result = await session.execute(stmt, {"pid": project_id, "lim": limit})
                rows = result.fetchall()
                return [
                    {
                        "task_id": r[0],
                        "title": r[1],
                        "description": r[2],
                        "status": r[3],
                        "priority": r[4],
                        "story_points": r[5],
                        "deadline": str(r[6]) if r[6] else None,
                        "assignee_id": r[7],
                        "assignee_name": r[8],
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"MasarxClient.get_tasks error: {e}")
            return []
    
    async def get_notifications(self, user_id: int, limit: int = 10) -> List[dict]:
        if not self.db_client:
            return []
        try:
            async with self.db_client() as session:
                stmt = sql_text(
                    "SELECT id, title, body, channel, is_read, created_at "
                    "FROM masarx_notifications "
                    "WHERE user_id = :uid "
                    "ORDER BY created_at DESC LIMIT :lim"
                )
                result = await session.execute(stmt, {"uid": user_id, "lim": limit})
                rows = result.fetchall()
                return [
                    {
                        "id": str(r[0]),
                        "title": r[1],
                        "body": r[2],
                        "channel": r[3],
                        "is_read": r[4],
                        "created_at": str(r[5]) if r[5] else None,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"MasarxClient.get_notifications error: {e}")
            return []
```

**File**: `C:\Users\salla\Connexios\src\helpers\config.py` — no changes needed (already uses same Postgres)

**File**: `C:\Users\salla\Connexios\src\controllers\helpers\ToolManager.py` — add methods:
```python
async def get_masarx_tasks(self, project_id: int) -> str:
    """Fetch tasks from MasarX's task table via shared PostgreSQL."""
    if not hasattr(self, 'masarx_client') or not self.masarx_client:
        return ""
    try:
        tasks = await self.masarx_client.get_tasks(project_id)
        if not tasks:
            return "No tasks found for this project."
        lines = [f"Tasks for project {project_id}:"]
        for t in tasks[:10]:
            status_icon = "✅" if t["status"] == "DONE" else ("🔄" if t["status"] == "IN_PROGRESS" else "⏳")
            lines.append(f"  {status_icon} [{t['status']}] {t['title']} — {t.get('assignee_name', 'unassigned')}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_masarx_tasks error: {e}")
        return ""
```

**File**: `C:\Users\salla\Connexios\src\controllers\NLPController.py` — inject MasarX tasks into context:
After the live backend context injection block (around line 436-446), add:
```python
# --- MasarX tasks injection ---
if project_id and node in (WorkflowNodeEnum.BLOCKER, WorkflowNodeEnum.MILESTONE_WARNING, WorkflowNodeEnum.GENERAL):
    try:
        tasks_context = await self.tool_manager.get_masarx_tasks(project_id)
        if tasks_context:
            retrieved_context.append(f"\n[Project Tasks from MasarX]:\n{tasks_context}")
            sources.append("Tasks")
    except Exception as e:
        self.logger.warning(f"Could not fetch MasarX tasks: {e}")
```

### Phase 4: Backend Changes (Specs only — NOT executed by AI)

Full specs for backend teammate at:
`F:\Connexio_Frontend2\docs\RAG_INTEGRATION_SPECS.md`

**Summary of changes needed**:
1. `services/aiService.js`: Add `modelTier` param to `ragChat()`
2. `modules/ai/ai.routes.js`: Accept `model_tier` in POST body + GET query
3. `socket.js` or `chats.controller.js`: Stream RAG SSE as socket events
4. `bootstrap.js`: Add `GET /api/health/services` endpoint
5. Optional: Add in-memory cache for RAG responses

### Phase 5: Frontend Changes (Specs only — NOT executed by AI)

Full specs at same file.

**Summary**:
1. `ConnexioAI.jsx`: Parse RAG response JSON, show source badges
2. `ConnexioAI.jsx`: Fix markdown (headers→bold)
3. `ChatWidget.jsx`: Add AI typing indicator
4. Optional: Model tier badge on AI messages

### Phase 6: MasarX Cron Parallelism

**File**: `F:\MasarX_A\src\tasks\cron_jobs.py` (lines 38-50, 58-70)
```python
async def _run_workload_scan():
    project_ids = await _get_active_project_ids()
    if not project_ids:
        return {"status": "no_projects"}
    # Run in parallel instead of sequential
    tasks = [
        invoke_masarx(intent="monitor_workload", project_id=pid, triggered_by="celery_beat", actor="masarx_bot")
        for pid in project_ids
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {"status": "completed", "projects": len(project_ids)}
```

### Phase 7: Remove Orphan Code + Data Alignment

**File**: `F:\MasarX_A\src\Routes\webhook_routes.py` — remove lines 284-292 (orphan `search_project_domain`)

**File**: `F:\MasarX_A\src\stores\vectordb\rag_tool.py` — remove `_get_embedding_client()` method (duplicate), use shared one from db_tool. Initialize via passed session_maker only.

---

## 5. API Contracts

### RAG Chat
```
POST /api/v1/nlp/agent/chat/{project_id}
Headers: X-API-Key: <key>
Body: { query: string, user_id: int, persona?: string, model_tier?: "auto"|"generation"|"utility" }
Response: {
  signal: "agent_chat_success",
  answer: string,
  node: "general"|"onboarding"|"blocker"|"milestone_warning"|"team_formation"|"phase_transition"|"out_of_scope",
  language: "en"|"ar",
  sources: ["Documentation"|"Live Backend Data"|"Wikipedia"|"Google Search"|"GitHub"|"Tasks"],
  session_id: int
}
```

### RAG Streaming
```
GET /api/v1/nlp/agent/chat/stream/{project_id}?query=...&user_id=...&model_tier=...
Headers: X-API-Key: <key>
Response: SSE stream
  data: {"event":"meta","node":"general","language":"en","sources":[...],"session_id":1}
  data: {"text":"Hello..."}
  data: [DONE]
```

### RAG Health
```
GET /api/v1/health
Response: {
  "status": "healthy",
  "service": "ConnexiosRAG",
  "version": "0.1",
  "llm_config": {
    "generation": {"backend": "GROQ", "model": "openai/gpt-oss-120b"},
    "utility": {"backend": "GROQ", "model": "meta-llama/llama-4-scout-17b-16e-instruct"},
    "embedding": {"backend": "COHERE", "model": "embed-multilingual-v3.0"}
  }
}
```

### MasarX Webhook
```
POST /api/v1/masarx/webhook/event/{event_type}/{project_id}
Headers: Authorization: Bearer <JWT>
Body: { project_id?: string, user_id?: string, payload?: {} }
```

### Backend Proxy Routes
```
POST /api/ai/chat/:projectId  → proxies to RAG POST /chat/{pid}
GET  /api/ai/chat/stream/:projectId → proxies to RAG GET /chat/stream/{pid}
POST /api/ai/agent/:intent/:projectId → proxies to MasarX
POST /api/ai/approval/:token → proxies to MasarX
```

## 6. Key Ports & URLs

| Service | Dev URL | Deployed URL |
|---------|---------|-------------|
| RAG | `http://localhost:8080` | `https://sallahahmed-connexiorag.hf.space` |
| MasarX | `http://localhost:8000` | `https://sallahahmed-connexioagent.hf.space` |
| Backend | `http://localhost:3000` | `https://connexio.icu` |
| Frontend | `http://localhost:3001` | Not deployed |
| Neon PG | `ep-proud-shadow-ap1bijnm-pooler.c-7.us-east-1.aws.neon.tech:5432` | — |
| Upstash Redis | `dynamic-ocelot-90005.upstash.io:6379` | — |

## 7. Neon DB Connection String
```
postgresql://neondb_owner:npg_4JFZzlHNc8si@ep-proud-shadow-ap1bijnm-pooler.c-7.us-east-1.aws.neon.tech/connexio?sslmode=require&channel_binding=require
```
