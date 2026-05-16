# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-05-12

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

## Key Learnings

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

## Do-Not-Repeat

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

- **[2026-05-16] Streaming path needs explicit model upgrade logic.**
  Unlike the non-streaming path with auto-escalation (utility→generation on bad answer), the streaming path must pre-emptively upgrade to the generation model for projectless GENERAL queries. Streaming renders tokens visibly, so poor 8B answers are more noticeable.

## Decision Log

- **[2026-05-14] `ai_chatbot` rooms use `project_id=0` when calling the RAG.**
  Chosen over creating a separate `/chat/general` endpoint to avoid changing the RAG's routing structure. The RAG converts `0 → None` in `agent.py` keeping the NLPController's `Optional[int]` signature clean.

- **[2026-05-14] `ai_chatbot` rooms always call RAG; group/direct require `@connexio` mention.**
  In a 1:1 AI chatbot room the user expects every message to be answered. In group chat, the AI should only respond when explicitly addressed to avoid noise.

- **[2026-05-16] Streaming metadata (sources) is stored in MongoDB `Message.metadata` field, not PostgreSQL.**
  Frontend reads messages from MongoDB; storing metadata there means historical messages also carry source info. The `Message.metadata` is `Mixed` type (flexible JSON). Decided over a separate PostgreSQL lookup per message.

- **[2026-05-16] Cron parallelism uses `asyncio.gather()` across all project IDs.**
  Both `_run_workload_scan()` and `_run_risk_scan()` now fan-out to all projects concurrently instead of sequential `for` loop. Safe because each `invoke_masarx()` call targets an independent project.
