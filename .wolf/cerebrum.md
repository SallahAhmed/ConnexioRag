# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-05-12

## User Preferences

- **[2026-05-16] No source labels visible to end users.** Tags like "Live Backend Data" must not appear in the UI. Sources metadata still sent in API response for dev use but never shown to user.

## Key Learnings

- **Jina AI embeddings via OpenAIProvider:** `EMBEDDING_BACKEND="OPENAI"` reuses `OpenAIProvider` with Jina's OpenAI-compatible API at `JINA_API_URL`. The `embed_text()` method passes `"task": "retrieval.query"` or `"retrieval.passage"` via `extra_body` when model ID contains "jina". Model: `jina-embeddings-v3` (1024 dim).

- **JinaReranker:** Calls `POST {JINA_API_URL}/v1/rerank` directly via `httpx`. Shares `JINA_API_KEY` with embeddings. No SDK needed — Jina's rerank API is OpenAI-compatible formatted as a standalone POST.

- **JAILBREAK_KEYWORDS bug (fixed):** `JAILBREAK_KEYWORDS` list was defined at line 97-103 but `if any(kw in query_lower for kw in JAILBREAK_KEYWORDS): return OUT_OF_SCOPE` was missing. Queries matching jailbreak patterns were returning GENERAL instead of OUT_OF_SCOPE. Fixed by adding the check.

- **.env secrets pattern:** All live secrets are commented with `# TODO: rotate` to prevent accidental commits while keeping the file as the single source of truth for required env vars.

- **Cohere files disabled:** `CoHereProvider.py` and `CoHereReranker.py` are kept in the codebase but not imported. The imports in `providers/__init__.py`, `LLMEnums.py`, and `LLMProviderFactory.py` remain for backward compatibility but no code path activates them.

- **Project:** connexios
- **Description:** Connexio full-stack — Node.js backend (Hostinger), Connexios RAG (HF Spaces), MasarX Agent (HF Spaces), shared Neon.tech PostgreSQL.

- **Chat system:** The Node.js backend uses MongoDB (Mongoose) for chat rooms and messages, and PostgreSQL for users/projects/tasks. `ChatRoom.metadata` is a Mongoose `Map` type — use `.get()` / `.set()` to read/write.

- **Chat room types:** `direct`, `group`, `ai_chatbot`. Group chats may have `metadata.projectId` linking them to a project.

- **@connexio trigger:** Already wired end-to-end in `socket.js` → `processAIMessage()` → `getAIResponse()` → RAG. No changes needed to make the mention work in group/direct chats.

- **RAG session management:** Sessions are keyed by `user_id + project_id` in `get_or_create_session()`. The `session_id` field in `AgentChatRequest` is accepted but effectively overwritten by the DB lookup — the RAG always resumes the latest session for that user+project pair.

- **project_id=0 convention:** `0` is used as the project_id for individual `ai_chatbot` rooms (no project context). The RAG's `agent.py` converts `project_id == 0` to `None` before calling `answer_agent_chat`. This keeps the URL path typed as `int` while supporting projectless sessions.

- **PostgreSQL column casing:** `node-postgres` returns column names in lowercase regardless of how they are defined in SQL. So `SELECT PName FROM projects` returns `row.pname` in JS, not `row.PName`.

- **Streaming SSE format (RAG):** The RAG streaming endpoint sends events in this order: (1) first event before first token is a meta event `{"node","language","sources","session_id","trace_id","event":"meta"}`, (2) each token chunk as `{"text":"..."}`, (3) final `[DONE]`. Out-of-scope short-circuit also sends `{"event":"meta"}` then `{"answer":"..."}` then `[DONE]`.

- **MasarX task schema:** MasarX's `task` table uses mixed-case columns with quoted SQL identifiers: `"TaskId"`, `"TaskName"`, `"TaskDesc"`, `"PID"`, `"UID"`. SQLAlchemy raw SQL must use quoted names or queries silently fail.

- **WebhookResult table:** `masarx_webhook_results` is the correct table for MasarX webhook outputs (not `chunks` which is RAG's table). The model has UUID primary key (not integer) due to `UUID(as_uuid=True)`.

- **rag_tool.py pool sharing:** `_get_session_maker()` was removed — rag_tool now requires `db_tool.initialize(session_maker=...)` to be called first (done in both main.py startup and Celery worker fallback path). If `session_maker` is None, `hybrid_search()` returns an error string.

- **Message.metadata field:** MongoDB `Message` model requires `metadata: { type: mongoose.Schema.Types.Mixed }` to persist AI response metadata (sources, node, language). Without this schema field, Mongoose silently drops the field on save.

- **Backend API response format:** All Node.js backend routes wrap data in `{ success: true, data: ... }`. ToolManager.get_project_context_summary must call `.get("data")` to unwrap before reading fields like `PName`, `Description`. Members and tasks follow the same pattern.

- **authMiddleware protect accepts X-API-Key:** The protect middleware now checks `X-API-Key` header against `CONNEXIO_INTERNAL_API_KEY` first. If valid, sets `req.user = { UID: 0 }` and skips JWT. This lets RAG/MasarX call backend routes without JWT.

- **BackendApiClient._headers() includes X-API-Key:** RAG outbound requests now include `X-API-Key` header alongside the service JWT. Both are sent; the backend checks X-API-Key first.

- **socket.js resolveProjectId:** AI chatbot rooms resolve project ID in this priority: (1) room metadata.projectId, (2) DB query for user's most recent project, (3) 0 (projectless). The db query joins `projects` with `project_members` on `pm.user_id`.

- **RAG chunk_size for production:** Default `chunk_size=100` is too small for document retrieval. Use `chunk_size=500+` for meaningful context per chunk. The `limit` parameter (default 5) should be at least 20 for full document coverage.

## Do-Not-Repeat

- **[2026-05-17] Do not override `language` from URL content in `_prepare_chat_context()`.**
  The old code re-detected language from downloaded URL content and overwrote the `language` variable (commit 37a1930). This caused English-asking users who pasted Arabic URLs to receive Arabic responses. `query_language` is now saved at Step 1 and used at Step 4. URL content is context data — never change the response language based on a pasted document.

- **[2026-05-17] `grade_relevance()` returns `bool`, not the string `"AMBIGUOUS"`.**
  `return "AMBIGUOUS" in grade` evaluates to `True` (bool), not the string. The decision matrix in the new CRAG block uses `grade_relevance_batch()` which returns explicit strings. Never use `grade_relevance()` where a 3-way string result is needed.

- **[2026-05-17] Do not add unconfigured tools to the CRAG decision prompt.**
  If SERPAPI/GITHUB/STACKOVERFLOW keys are missing, `_run_crag_tools()` excludes those tools from the decision prompt. Adding them causes the LLM to select a tool whose handler returns an error string that enters the RAG context as real knowledge.

- **[2026-05-17] Per-doc grading with N individual LLM calls is too slow.**
  Use `grade_relevance_batch()` which grades all docs in one LLM call. N sequential calls multiply latency (5 docs = 5x delay). Batch is same latency as single-blob grading with per-doc accuracy.

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

- **[2026-05-14] Do not use `context.stats.*` or `context.completionRate` from `getProjectContext()`.**
  `getProjectContext()` returns `{ project, tasks[], members[] }` only. Always compute stats from `context.tasks.filter(...)` inline. The `generateProjectReport()` function is the correct reference implementation.

- **[2026-05-14] Do not pass a string as `project_id` to the RAG chat URL.**
  The FastAPI route `POST /api/v1/nlp/agent/chat/{project_id}` has `project_id: int` — passing `'general'` causes a 422 validation error. Use `0` for projectless sessions instead.

- **[2026-05-16] Streaming SSE requires anti-buffering headers on HF Spaces.**
  Without `Cache-Control: no-cache`, `Connection: keep-alive`, and `X-Accel-Buffering: no`, nginx buffers the entire streaming response and delivers it all at once. These headers must be passed in the `StreamingResponse(headers={...})` constructor.

- **[2026-05-16] _SKIP_FAST_PATH must cover Arabic question words.**
  The 50-char fast path in `detect_node()` bypasses LLM classification. Arabic question starters like "ما هو", "ما هي", "كيف", "هل" were missing, allowing Arabic queries about folklore, philosophy, and personal topics to bypass OOS detection. Always keep `_SKIP_FAST_PATH` in sync with common Arabic question patterns.

- **[2026-05-23] JAILBREAK_KEYWORDS list requires an explicit check.**
  The `JAILBREAK_KEYWORDS` tuple was defined at class level but the loop to test `if any(kw in query_lower for kw in JAILBREAK_KEYWORDS): return OUT_OF_SCOPE` was never written. Static analysis won't catch this — a tuple declared and never iterated over is syntactically valid. Always verify that guard lists are actually consumed in the logic, not just declared.

- **[2026-05-16] Streaming path needs explicit model upgrade logic.**
  Unlike the non-streaming path with auto-escalation (utility→generation on bad answer), the streaming path must pre-emptively upgrade to the generation model for projectless GENERAL queries. Streaming renders tokens visibly, so poor 8B answers are more noticeable.

- **[2026-05-16] ToolManager.get_project_context_summary must unwrap `data` field from backend API responses.**
  The Node.js backend wraps all responses in `{ success: true, data: ... }`. Reading `project_data.get('PName')` directly returns `None` because `PName` is inside `project_data['data']`. Always use `project_raw.get("data") or project_raw` first.

- **[2026-05-17] CRAG tool dispatch is unified in `NLPController._run_crag_tools()`.**
  Previously duplicated 100+ lines in two branches. Now: `force_tool="GOOGLE"` for temporal, LLM picks from available-only tools otherwise. Returns `[(source_name, text)]` with error strings filtered out.

- **[2026-05-17] KB decision matrix uses `grade_relevance_batch()` and a separate `kb_context` list.**
  Matrix: all-RELEVANT → KB only; all-IRRELEVANT → 2 CRAG tools; mixed/ambiguous → KB + 1 CRAG tool; empty KB → 2 CRAG tools. `kb_context` is a separate list so KB can be discarded cleanly without string-prefix filtering.

- **[2026-05-17] Relevance grader prompts softened in both en and ar templates.**
  Changed from "strict and highly critical" to "generous — domain context is valuable even without a direct answer." AMBIGUOUS now covers partial relevance, not just near-misses.

## Decision Log

- **[2026-05-14] `ai_chatbot` rooms use `project_id=0` when calling the RAG.**
  Chosen over creating a separate `/chat/general` endpoint to avoid changing the RAG's routing structure. The RAG converts `0 → None` in `agent.py` keeping the NLPController's `Optional[int]` signature clean.

- **[2026-05-14] `ai_chatbot` rooms always call RAG; group/direct require `@connexio` mention.**
  In a 1:1 AI chatbot room the user expects every message to be answered. In group chat, the AI should only respond when explicitly addressed to avoid noise.

- **[2026-05-16] Streaming metadata (sources) is stored in MongoDB `Message.metadata` field, not PostgreSQL.**
  Frontend reads messages from MongoDB; storing metadata there means historical messages also carry source info. The `Message.metadata` is `Mixed` type (flexible JSON). Decided over a separate PostgreSQL lookup per message.

- **[2026-05-16] Cron parallelism uses `asyncio.gather()` across all project IDs.**
  Both `_run_workload_scan()` and `_run_risk_scan()` now fan-out to all projects concurrently instead of sequential `for` loop. Safe because each `invoke_masarx()` call targets an independent project.

- **[2026-05-16] X-API-Key bypass in protect middleware, not separate middleware.**
  Chose to add X-API-Key check directly in the `protect` middleware (authMiddleware.js) rather than a separate middleware or router-level skip. This ensures all protected routes automatically accept internal service calls without duplicating bypass logic per route file.

- **[2026-05-16] resolveProjectId placed in socket.js, not a shared module.**
  The project ID resolution logic is only used by socket.js's ai_chatbot handler. Placing it inline avoids premature abstraction. If ai.routes.js also needs it, extract to a shared helper later.

- **[2026-05-16] Frontend auto-creates AI chat session when projectId in URL.**
  When user clicks "AI Assistant" on a project page, ConnexioAI auto-creates a new ai_chatbot room with the project context (forceNew=true). This ensures a fresh room per project visit. The socket.js resolveProjectId then reads metadata.projectId for all subsequent messages.
