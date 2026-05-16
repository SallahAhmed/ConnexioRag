# Connexios RAG / CRAG System — Complete Knowledge Base

## 1. System Overview

**Connexios RAG** is an Agentic Retrieval-Augmented Generation system serving as the knowledge engine for the Connexio platform. It powers intelligent, context-aware chat for project collaboration across students, developers, designers, marketers, and professionals.

### Deployment

| Component | Location | Details |
|-----------|----------|---------|
| **API Server** | Hugging Face Spaces (ConnexioRag) | FastAPI, port 7860, Docker SDK |
| **PostgreSQL** | Neon.tech | Shared with MasarX Agent |
| **Vector DB** | Neon.tech (pgvector) | Same PG instance, `collection_{size}_{pid}` tables |
| **Redis** | Upstash | Celery broker/backend |
| **Generation** | Groq API | `openai/gpt-oss-120b` (117B MoE, MMLU 90%, ~500 tok/s). Used for PROJECT intents + auto-escalation fallback. |
| **Utility** | Groq API | `meta-llama/llama-4-scout-17b-16e-instruct` (17B). Used for GENERAL intents, classification, grading. |
| **Embeddings** | Cohere API | `embed-multilingual-v3.0` (1024 dims) |

### Ecosystem Integration

```
Node.js Backend (connexio.icu)
    │
    ├── X-API-Key ──────────► Connexios RAG (HF Spaces)
    │   POST /chat/{pid}
    │   POST /upload-and-process/{pid}
    │   POST /projects/sync
    │   POST /cache/invalidate/{pid}
    │
    └── Service JWT ────────► MasarX Agent (HF Spaces)
```

---

## 2. API Endpoints

### Agent (Chat) — Protected by X-API-Key

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/nlp/agent/chat/{project_id}` | Persona-based conversation. `project_id=0` = projectless. Accepts `model_tier` param. |
| `GET` | `/api/v1/nlp/agent/chat/stream/{project_id}` | SSE streaming. Accepts `model_tier` query param. |
| `POST` | `/api/v1/nlp/agent/cache/invalidate/{project_id}` | Invalidate backend project cache |
| `POST` | `/api/v1/nlp/agent/cache/invalidate/user/{user_id}` | Invalidate backend user cache |

### Data (File Processing) — Protected by X-API-Key

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/data/upload/{project_id}` | Upload file (PDF/TXT) |
| `POST` | `/api/v1/data/process/{project_id}` | Trigger Celery chunking |
| `POST` | `/api/v1/data/process-and-push/{project_id}` | Chunk + index workflow |
| `POST` | `/api/v1/data/upload-and-process/{project_id}` | Upload + auto-index (fire-and-forget, returns 202) |

### NLP (Indexing) — Protected by X-API-Key

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/nlp/index/push/{project_id}` | Re-index project chunks |
| `GET` | `/api/v1/nlp/index/info/{project_id}` | Collection metadata |
| `POST` | `/api/v1/nlp/index/search/{project_id}` | Semantic search |

### Projects — Protected by X-API-Key

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/projects/sync` | Sync MySQL PID → PostgreSQL |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Status + health |
| `GET` | `/api/v1/` | App metadata |
| `GET` | `/api/v1/health` | Health + LLM config (generation, utility, embedding model details) |

---

## 3. Request Flow (Chat Pipeline)

```
POST /chat/{project_id}
    │
    ├── 1. Language Detection (Unicode range ؀-ۿ)
    │     → "ar" or "en"
    │
    ├── 2. Intent Classification (WorkflowNodeEnum)
    │     a. OOS keywords FIRST (off-topic, jailbreak, personal)
    │     b. Project keywords (onboarding, team, phase, blocker, milestone)
    │     c. GENERAL keywords (greetings, identity)
    │     d. <50 chars fast-path → GENERAL (unless _SKIP_FAST_PATH)
    │     e. LLM fallback (utility model with template prompt)
    │
    ├── 3. Session Management
    │     a. Get or create ChatSession in PostgreSQL (scoped by user_id)
    │     b. Update session language per-request
    │     c. Load history (capped at 4 msgs if projectless)
    │     d. Token budgeting (cl100k_base, flat 4000 token budget)
    │
    ├── 4. Knowledge Base Search (Hybrid)
    │     a. SKIP if OUT_OF_SCOPE
    │     b. Global KB (collection_1024_0) — searched ALWAYS if not OOS
    │     c. Project KB (collection_1024_{pid}) — searched if project_id set
    │     d. Merge via RRF (k=60), take top 5
    │
    ├── 5. Relevance Grading
    │     a. Bypassed for projectless mode (global KB is curated)
    │     b. Utility LLM grader for project KB results: YES/NO
    │
    ├── 6. CRAG Fallback (only when project_id IS set AND KB irrelevant)
    │     a. Platform nodes + empty KB → canned "Platform Guide" message
    │     b. Other → LLM selects: WIKIPEDIA / GOOGLE / GITHUB / PYTHON / NONE
    │     c. All external tools have 5s timeout
    │
    ├── 7. Live Backend Context (via BackendApiClient REST)
    │     Project summary + members + tasks (5-min cache, invalidatable)
    │
    ├── 8. Model Selection (intent-based + model_tier param)
    │     BLOCKER, MILESTONE_WARNING, ONBOARDING, TEAM_FORMATION,
    │     PHASE_TRANSITION → GPT-OSS 120B (quality needed)
    │     GENERAL (short/fast-path) → Llama 4 Scout 17B (cheap)
    │     model_tier="generation" → force GPT-OSS 120B
    │     model_tier="utility" → force Llama 4 Scout 17B
    │     model_tier="auto" → RAG decides based on intent node
    │
    ├── 9. MasarX Task Data Injection
    │     When node is BLOCKER/MILESTONE_WARNING/GENERAL and project_id set,
    │     queries MasarX task table via shared PostgreSQL for live task data.
    │     Sources include "Tasks" badge.
    │
    ├── 10. LLM Generation (with 429 retry: 1s, 2s, 4s backoff)
    │
    ├── 11. Auto-Escalate (utility → generation)
    │     If utility answer is empty (<20 chars), echoes query, or contains
    │     refusal phrase ("only help", "can't help", "specialize in")
    │     — auto-retry with GPT-OSS 120B
    │
    └── 12. Persist + Return
          a. Save user/assistant messages to session
          b. Write trace_{uuid}.json to disk
          c. Return {answer, node, language, sources, session_id}
```

### Streaming Variant
Same flow, but LLM output is streamed via SSE:
- First event: `{event: "meta", node, language, sources, session_id, trace_id}`
- Data events: `{text: "<chunk>"}`
- Final event: `[DONE]`

---

## 4. Workflow Nodes (Intent Classification)

### Detection Order (Priority)
1. **OOS KEYWORDS FIRST** — Off-topic, jailbreak, personal questions caught immediately
2. **PROJECT KEYWORDS** — Specific intent keywords (onboarding, team, phase, blocker, milestone)
3. **GENERAL KEYWORDS** — Greetings, identity questions
4. **FAST PATH** — Queries under 50 chars → GENERAL (unless in `_SKIP_FAST_PATH`)
5. **LLM CLASSIFIER** — Everything else → utility model with template prompt

### Node Details

| Node | Enum Value | Example Keywords | Description |
|------|-----------|-----------------|-------------|
| ONBOARDING | `onboarding` | "where do i start", "how does this", "getting started", "guide me" | Platform guidance for new users |
| TEAM_FORMATION | `team_formation` | "find teammate", "need a dev", "recruit", "join team", "looking for" | Team matching/hiring |
| PHASE_TRANSITION | `phase_transition` | "next phase", "done with", "move to", "advance" | Project phase advancement |
| BLOCKER | `blocker` | "stuck", "error", "not working", "crash", "exception", "help fix" | Technical troubleshooting |
| MILESTONE_WARNING | `milestone_warning` | "my project is behind", "we are overdue", "we missed our" | Project delay alerts (must be first-person) |
| GENERAL | `general` | "hello", "who are you", career advice, methodologies, coding, design | Catch-all for project-related + professional queries |
| OUT_OF_SCOPE | `out_of_scope` | weather, cooking, politics, sports, celebrities, jailbreak, personal ("wearing", "dreams") | Off-topic guardrail |

### OOS Keywords (Comprehensive)
```
Geography: capital of, who is the president, population of, located in, mayor of, prime minister, king of
Entertainment: tell me a joke, who won the game, celebrity, actor, movie, singer, album, lyrics
Food: recipe for, how to make, how to cook, ingredients for, bake, fry, boil
Weather: weather in, temperature in, forecast for
History: what happened on, born on, died in, year
Personal: wearing, wear, clothes, outfit, dress, my name is, i am, my age, how old, dream, sleep
Jailbreak: your system prompt, ignore your instructions, bypass your rules, jailbreak, dan mode
Arabic: عاصمة, الطقس في, من هو رئيس, قل لي نكتة, تجاهل تعليماتك, تجاوز قيودك
```

### Fast Path Bypass (`_SKIP_FAST_PATH`)
Queries matching these patterns ALWAYS go to LLM classifier:
- "who is/was/were", "who's", "من هو", "من كان"
- "system prompt", "your instructions", "ignore your", "bypass your"
- "jailbreak", "تجاهل تعليم", "تجاوز قيود"

---

## 5. Global Knowledge Base

### Overview
52 files across 8 categories, uploaded to `collection_1024_0` (134 chunks).

### Categories

| # | Category | Files | Content |
|---|----------|-------|---------|
| 1 | **Connexio Platform** (8) | `what_is_connexio`, `registration`, `team_matching`, `project_lifecycle`, `task_management`, `pricing_freemium`, `rag_agent_features`, `masarx_agent` | "What does Connexio do?", services, features |
| 2 | **Agile & PM** (7) | `agile_manifesto`, `scrum_guide`, `sprint_planning`, `wbs`, `retrospectives`, `risk_management`, `kanban` | Methodology questions |
| 3 | **Dev Skills** (8) | `python_basics`, `react_fundamentals`, `rest_api_design`, `git_workflow`, `docker_intro`, `postgresql_basics`, `html_css`, `javascript` | Technical questions |
| 4 | **Design & UX** (6) | `ui_ux_principles`, `design_thinking`, `figma_guide`, `color_theory`, `prototyping`, `user_research` | Design questions |
| 5 | **Career** (6) | `tech_career_paths`, `resume_tips`, `interview_prep`, `portfolio_building`, `networking`, `freelancing` | Career advice |
| 6 | **Business & Marketing** (6) | `market_research`, `growth_strategies`, `content_marketing`, `seo_basics`, `business_model_canvas`, `pitch_deck` | Business questions |
| 7 | **Soft Skills** (6) | `team_communication`, `conflict_resolution`, `leadership_basics`, `time_management`, `remote_work`, `code_review` | Teamwork |
| 8 | **Industry Trends** (5) | `ai_ml_intro`, `cloud_computing`, `cybersecurity_basics`, `data_analytics`, `devops_intro` | Tech trends |

### KB Sanitization
All KB files are sanitized to remove:
- Internal infrastructure details (Neon, Upstash, specific cloud providers)
- Algorithm weights/exact percentages
- Specific technology versions or internal architecture details
- API keys, tokens, or credentials

### Hybrid Search (Projectless Mode)
When `project_id=0`, searches only `collection_1024_0` (global KB). Bypasses relevance grader since global KB is curated content.

### Hybrid Search (Project Mode)
When `project_id` is set, searches both `collection_1024_{pid}` (project KB) AND `collection_1024_0` (global KB), merges via RRF.

---

## 6. CRAG (Corrective RAG) Tools

### Trigger
Only activates when `project_id` IS set AND knowledge base search is irrelevant/empty.

### Tool Selection (LLM decision)
```
Query → LLM selects one: WIKIPEDIA | GOOGLE | GITHUB | PYTHON | NONE
```

### Tool Details

| Tool | Trigger | Data Source | Requirements | Timeout |
|------|---------|-------------|-------------|---------|
| **Wikipedia** | General knowledge, definitions | Wikipedia API | None | 5s |
| **Google** | News, recent events, stats | SerpAPI | `SERPAPI_API_KEY` | 5s |
| **GitHub** | Repo search, code | GitHub REST API | `GITHUB_TOKEN` | 5s |
| **Python** | Code execution, math, logic | Sandboxed `exec()` | None (limited) | 5s |
| **NONE** | Conversational | — | — | — |

### Platform Node Special Case
If node is ONBOARDING/TEAM_FORMATION/PHASE_TRANSITION AND KB is empty:
→ Returns canned "Platform Guide" message

---

## 7. Prompt Templates

### Structure
```
stores/llm/templates/locales/
├── en/
│   ├── rag.py              # System prompt + footer prompt
│   ├── workflow.py         # Intent classification prompts
│   └── relevance_grading.py
└── ar/
    ├── rag.py              # Arabic RAG prompts
    ├── workflow.py         # Arabic classification
    └── relevance_grading.py
```

### English System Prompt (rag.py)
```
You are Connexio AI — a project collaboration advisor.
Persona: $persona | Context: $node

RESPONSE STYLE BY PERSONA:
- student: Teach like a tutor — simple examples, avoid jargon
- early_career: Mentor style — practical tips, career advice
- educator: Professor style — structured, use frameworks
- company: Consultant style — ROI, efficiency, outcomes

RESPONSE RULES:
1. No markdown headers. Speak naturally.
2. Cite sources as [Doc N].
3. Reply in EXACT SAME language as user.
4. Ask clarifying questions instead of guessing.
5. Maximum 3-5 sentences.
6. Use retrieved context first.

CRITICAL: If out of scope, MUST refuse politely.
```

### Projectless Sessions (NLPController.py)
When `model_tier=auto` and no `project_id`:
```
You are Connexio AI, a project collaboration assistant.
Persona: $persona. $persona_guide
Use the provided knowledge to answer. Be concise and helpful.
No markdown headers.
```
→ Uses utility model (Llama 4 Scout 17B), no domain gate (OOS keywords handle refusal at keyword level)

### Intent Classification Prompt (workflow.py)
Lists 7 nodes with descriptions + critical rules. LLM returns ONLY category name in CAPITALS.
Career advice, interview prep, and professional development explicitly listed as GENERAL.

### Footer Prompt
```
Retrieved Context: $context

Answer the following question using the context above.
Do not repeat the question. Reply in same language as user:

$query

Answer:
```

---

## 8. Session Management

### Data Model
```python
ChatSession:
  session_id (PK, autoincrement)
  session_uuid (UUID, unique)
  user_id (Integer)
  project_id (Integer, nullable)
  persona (Text: student/early_career/educator/company)
  language (String: en/ar)
  last_workflow_node (String)
  current_phase (String, nullable)
  chat_history (JSONB array)
  created_at (DateTime)
  updated_at (DateTime)
```

### History Truncation
- **Projectless sessions**: Capped at last 4 messages (2 turns)
- **Project sessions**: Token-budget window (4000 tokens total)
- **Clear commands**: "clear history", "forget everything", "new topic", Arabic equivalents

### Language Per-Request
Session language is updated on every request to match the detected query language.

### TTL Cleanup (Celery Beat)
Stale sessions (>30 days since `updated_at`) are deleted daily by `tasks.maintenance.clean_stale_sessions`.

---

## 9. Auth & Security

### X-API-Key
- Required on ALL endpoints (FastAPI dependency)
- Main Connexio backend adds this header when proxying
- Dev bypass: if `CONNEXIO_INTERNAL_API_KEY` is not set → validation skipped
- Settings cached in memory to avoid `.env` reload per request

### Rate Limiting
- **30 requests per minute per client IP**
- In-memory sliding window counter
- Returns `429 Too Many Requests` with clear error message
- Applied via Prometheus middleware on all routes

### Service JWT (BackendApiClient → Main Backend)
- Generated by `BackendApiClient._make_service_token()`
- Payload: `{UID: service_user_id, iat: now, exp: now+300}`
- Signed with `JWT_SECRET` (HS256), 5-minute expiry

### Python Sandbox (CRAG)
- `exec()` with limited globals: `__builtins__`, `asyncio`, `math`, `datetime`, `json`
- 5-second timeout
- No filesystem or network access from sandboxed code

### Input Validation
- `query` field: `min_length=1, max_length=5000`
- No SQL injection risk (parameterized queries)

### Backend Cache Invalidation
- `POST /api/v1/nlp/agent/cache/invalidate/{project_id}`
- `POST /api/v1/nlp/agent/cache/invalidate/user/{user_id}`
- Evicts stale project/user data from 5-min TTL cache

---

## 10. Database Schema

### RAG-Owned Tables
```sql
projects (project_id, name, description, created_at)
assets (asset_id, asset_project_id, asset_type, asset_name, asset_size)
chunks (chunk_id, chunk_text, chunk_metadata, chunk_order, chunk_project_id, chunk_asset_id)
rag_chat_sessions (session_id, user_id, project_id, persona, language, chat_history, ...)
collection_1024_0 (id, text, vector, metadata, chunk_id)  -- Global KB
collection_{size}_{pid} (id, text, vector, metadata, chunk_id)  -- Per-project KB
project_id_map (mysql_pid, postgres_pid)
```

### MasarX-Owned Tables (read-only)
```
masarx_notifications, masarx_pending_plans, user, task
```

---

## 11. Observability

### TraceManager
Every request generates `traces/trace_{uuid}.json` with:
- Language detection, session management, KB retrieval, LLM generation steps
- Each step: action name, duration, token usage, output preview

### Token Usage Logging
Per-request logging of prompt/completion/total tokens for both utility and generation models.

### Rate Limit Headers
HTTP 429 responses include `retry-after` guidance. Client should backoff.

---

## 12. Key Code References

| File | Lines | What |
|------|-------|------|
| `NLPController.py` | 155-501 | `_prepare_chat_context()` — entire pipeline |
| `NLPController.py` | 505-620 | `answer_agent_chat()` — non-streaming chat |
| `NLPController.py` | 622-718 | `answer_agent_chat_stream()` — streaming chat |
| `WorkflowController.py` | 25-139 | `detect_node()` — OOS first → project → GENERAL → fast path → LLM |
| `WorkflowController.py` | 155-194 | `grade_relevance()` — relevance grading |
| `ToolManager.py` | 198-263 | `search_knowledge_base()` — hybrid global + project KB search |
| `ToolManager.py` | 407-455 | `get_project_context_summary()` — live backend context |
| `agent.py` | 22-35 | `get_nlp_controller()` — cached controller (created once per app) |
| `agent.py` | 65-90 | `/chat/stream/{pid}` — streaming with model_tier |
| `agent.py` | 93-120 | `/cache/invalidate` routes |
| `backend_client.py` | 113-167 | `_get()` — REST with caching + retry |
| `PGVectorProvider.py` | 350-382 | `hybrid_search()` — RRF algorithm |
| `metrics.py` | 11-25 | Rate limiting (30 req/min per IP) |
| `maintenance.py` | 52-86 | `clean_stale_sessions()` — daily TTL cleanup |
| `data.py` | 233-305 | `upload_and_process()` — fire-and-forget indexing |

---

## 13. All Fixes & Improvements Applied

### Model Changes
| Change | Before | After |
|--------|--------|-------|
| Generation model | DeepSeek V4 Flash (OpenRouter, 45-60s) | GPT-OSS 120B (Groq, **<2s**) |
| Utility model | Llama 3.1 8B Instant | Llama 4 Scout 17B Instruct |
| 429 retry | None (crashed on rate limit) | Exponential backoff (1s, 2s, 4s) |
| Token budget | Inverted (short queries penalized) | Flat 4000 tokens for all |

### Intent Detection
| Fix | Before | After |
|-----|--------|-------|
| Detection order | Keywords loop → fast path → LLM | OOS first → project → GENERAL → fast path → LLM |
| OOS keywords | Limited (20 keywords) | Comprehensive (60+ keywords including personal, jailbreak) |
| Career/interview | Blocked as OOS | Explicitly GENERAL |
| Domain gate | Caused false refusals | Removed (OOS keywords handle it) |

### Knowledge Base
| Feature | Before | After |
|---------|--------|-------|
| Global KB | None | 52 files, 134 chunks, 8 categories |
| Projectless KB search | Skipped entirely | Searches `collection_1024_0` |
| Relevance grader | Rejected global KB results | Bypassed for projectless mode |
| KB sanitization | Exposed algorithm weights | Removed all internal details |

### Security
| Gap | Fix |
|-----|-----|
| No rate limiting | 30 req/min per IP |
| No input max_length | `max_length=5000` on query |
| Backend cache never invalidated | `POST /cache/invalidate/{pid}` routes |
| `.env` reloaded per request | Global settings cache in `security.py` |
| Exposed infra details in KB | Sanitized all 52 files |

### Model Selection
| Change | Before | After |
|--------|--------|-------|
| Model routing | Project-based (project_id set → 120B, else → 17B) | **Intent-based** (project intents → 120B, general → 17B) |
| Auto-escalate | None (utility failure → canned message) | **Automatic retry** with 120B if utility echoes, refuses, or gives empty answer |

### Performance
| Issue | Fix |
|-------|-----|
| New NLPController per request | Cached at app level |
| ToolManager SQLDatabase per request | Reuses cached controller |
| Mutable default arg `chat_history=[]` | Local copy in OpenAIProvider |

### Bug Fixes
| Bug | Fix |
|-----|-----|
| `final_history` undefined in fallback retry | Returned from `_prepare_chat_context` |
| `UTILITY_BACKEND` not in Settings class | `getattr` fallback to `GENERATION_BACKEND` |
| `Upload_data` PascalCase | Renamed to `upload_data` |
| `get_poject_chunks` typo | Renamed to `get_project_chunks_old` |
| `ProjectModel.get_project_or_create_one(project_id: str)` | Changed to `int` |
| Dead import `guidance` | Removed |

---

## 14. Test Categories

### A. Intent Classification
All 7 nodes tested with keywords, edge cases, short/long queries, Arabic, jailbreak attempts, and mixed-language queries.

### B. Language Detection
English, Arabic, mixed, non-Arabic non-English (French, Spanish), empty/numbers-only queries.

### C. OUT_OF_SCOPE Detection
Geography, politics, cooking, weather, sports, celebrities, jailbreak, personal questions ("wearing", "dreams"), Arabic equivalents, boundary cases.

### D. CRAG Tool Selection
Wikipedia, Google, GitHub, Python, missing API keys, ambiguous tool choice.

### E. Relevance Grading
Relevant, irrelevant (keyword false positive), ambiguous, empty context, Arabic content, long documents.

### F. Session Management
Create, get, continue sessions, history clearing, projectless capping (4 messages), token budget truncation, language/persona update.

### G. Knowledge Base Search
Hybrid search results, empty collection, non-existent collection, vector-only fallback.

### H. Streaming
SSE format, metadata event, chunk delivery, OUT_OF_SCOPE short-circuit, clear history via stream.

### I. API & Error Handling
Missing/invalid X-API-Key, empty query, invalid user_id, unknown project_id, LLM errors, rate limiting (429).

### J. Prompt Templates
System prompt substitution, footer prompt with context, Arabic rendering, missing template fallback to EN.

### K. File Upload & Processing
PDF/TXT validation, invalid type rejection, file size limits, chunking + overlap, background indexing.

### L. Integration
End-to-end chat with/without project context, file upload → process → index → search → chat, Arabic flow.

---

## 15. Deployment-Specific Notes

### HF Spaces Configuration
- Port: 7860 (HF Spaces default)
- UID: 1000 user
- All secrets as HF Space environment variables
- `POSTGRES_PORT` must be **5432** (Neon.tech pooler)
- Docker SDK runtime with Prometheus middleware

### Environment Variables (HF Secrets)
```
GENERATION_BACKEND=GROQ
GENERATION_MODEL_ID=openai/gpt-oss-120b
UTILITY_MODEL_ID=meta-llama/llama-4-scout-17b-16e-instruct
EMBEDDING_BACKEND=COHERE
EMBEDDING_MODEL_ID=embed-multilingual-v3.0
EMBEDDING_MODEL_SIZE=1024
GROQ_API_KEY=...
COHERE_API_KEY=...
CONNEXIO_INTERNAL_API_KEY=...
JWT_SECRET=...
SERVICE_USER_ID=2
MAIN_BACKEND_URL=https://connexio.icu
POSTGRES_* (Neon.tech credentials)
```

### Keepalive
- cron-job.org pings prevent HF Spaces from sleeping
- Must ping both RAG and MasarX endpoints regularly

---

## 16. Multi-System Integration Plan (Pending)

### 4 Systems Involved

| System | Path | Language | DB |
|--------|------|----------|----|
| **RAG** (this repo) | `C:\Users\salla\Connexios\` | Python/FastAPI | PostgreSQL (Neon) |
| **MasarX Agent** | `F:\MasarX_A\` | Python/FastAPI + LangGraph | PostgreSQL (Neon) |
| **Backend** | `F:\connexio_back2\` | Node.js/Express | MySQL |
| **Frontend** | `F:\Connexio_Frontend2\` | React/Vite | — |

### Issues Found (25 Total)

| ID | System | Issue | Severity |
|----|--------|-------|----------|
| C1 | RAG+MasarX | 3 separate DB pools to same Neon | 🔴 |
| C2 | MasarX | Writes webhook results to RAG-owned chunks table | 🔴 |
| C3 | RAG | No way to call MasarX endpoints | 🔴 |
| C4 | All 3 | JWT payload expectations differ | 🔴 |
| C5 | MasarX | db_tool.initialize() creates 4th engine | 🔴 |
| B1 | Backend | No direct health check for RAG/MasarX | 🟡 |
| B3 | Backend | ragChat doesn't pass model_tier | 🟡 |
| H1 | MasarX | DataChunk model may drift from RAG schema | 🟡 |
| H2 | All 3 | No cross-service health checks | 🟡 |
| H3 | MasarX | rag_tool.py creates its own embedding client | 🟡 |
| H4 | MasarX | Cron jobs run sequentially | 🟡 |
| B5 | Backend | technologies vs skills — two fields same data | 🟡 |
| F1 | Frontend | Uses Socket.IO not REST — blocks streaming | 🟡 |
| F2 | Frontend | No model_tier in UI | 🟡 |
| F3 | Frontend | No streaming — waits for full RAG response | 🟡 |
| F4 | Frontend | ReactMarkdown overrides "no markdown" rule | 🟡 |
| F5 | Frontend | Always uses project_id=0 (utility model) | 🟡 |
| F7 | Frontend | No typing indicator in ChatWidget | 🟢 |

### Execution Phases

| Phase | What | Who | Status |
|-------|------|-----|--------|
| **1** | Fix DB pools — share 1 engine | AI | Ready |
| **2** | Fix schema — own table for webhook results | AI | Ready |
| **3** | Build MasarxApiClient — RAG reads tasks | AI | Ready |
| **4** | Backend changes (model_tier, streaming, health) | Teammate | Specs written |
| **5** | Frontend changes (sources, markdown, typing) | Teammate | Specs written |
| **6** | MasarX cron parallelism | AI | Ready |
| **7** | Remove orphan code + data alignment | AI | Ready |

### Handoff File
Full AI-executable plan with exact code: `docs/SESSION_HANDOFF.md`
Backend + Frontend specs with line-by-line changes: `F:\Connexio_Frontend2\docs\RAG_INTEGRATION_SPECS.md`

---

## 17. Key Files Reference (Complete)

| File | Purpose |
|------|---------|
| `controllers/NLPController.py` | Main pipeline: prepare context → generate → fallback |
| `controllers/WorkflowController.py` | Intent detection: OOS first → keywords → fast path → LLM |
| `controllers/helpers/ToolManager.py` | KB search, CRAG tools, project context, MasarX tasks |
| `Routes/agent.py` | Chat + streaming + cache invalidation endpoints |
| `Routes/schemas/agent.py` | Pydantic schemas with model_tier + max_length |
| `stores/llm/templates/locales/en/rag.py` | System prompt + footer prompt |
| `stores/llm/providers/OpenAIProvider.py` | 429 retry with exponential backoff |
| `utils/metrics.py` | Rate limiting (30 req/min) + Prometheus |
| `utils/security.py` | X-API-Key validation with cached settings |
| `utils/backend_client.py` | REST client to Node.js backend with JWT auth |
| `docs/CONNEXIOS_RAG_KNOWLEDGE_BASE.md` | This file — full system documentation |
| `docs/SESSION_HANDOFF.md` | AI-executable multi-system integration plan |
| `F:\Connexio_Frontend2\docs\RAG_INTEGRATION_SPECS.md` | Backend + frontend code specs |

---

## 18. Test Commands

```bash
# Projectless chat (auto mode — RAG decides model)
curl -X POST https://sallahahmed-connexiorag.hf.space/api/v1/nlp/agent/chat/0 \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"query": "what does Connexio do?", "user_id": 1}'

# Force generation model
curl -X POST .../chat/0 \
  -d '{"query": "explain agile", "user_id": 1, "model_tier": "generation"}'

# Streaming with model_tier
curl -X GET "...chat/stream/0?query=hello&user_id=1&model_tier=generation" -H "X-API-Key: $KEY"

# Upload KB file to global KB
curl -X POST .../data/upload-and-process/0 -H "X-API-Key: $KEY" -F "file=@doc.txt"

# Invalidate backend cache
curl -X POST .../agent/cache/invalidate/11 -H "X-API-Key: $KEY"

# Health with LLM config
curl https://sallahahmed-connexiorag.hf.space/api/v1/health

# Direct KB search
curl -X POST .../nlp/index/search/0 \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"text": "what does Connexio do?", "limit": 3}'
```
