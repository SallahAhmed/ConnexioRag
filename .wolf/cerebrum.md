# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-06-02

## User Preferences

- **[2026-05-16] No source labels visible to end users.** Tags like "Live Backend Data" must not appear in the UI. Sources metadata still sent in API response for dev use but never shown to user.

## Key Learnings

- **Jina AI embeddings via OpenAIProvider:** `EMBEDDING_BACKEND="OPENAI"` reuses `OpenAIProvider` with Jina's OpenAI-compatible API at `JINA_API_URL`. The `embed_text()` method passes `"task": "retrieval.query"` or `"retrieval.passage"` via `extra_body` when model ID contains "jina". Model: `jina-embeddings-v3` (1024 dim).

- **JinaReranker:** Calls `POST {JINA_API_URL}/v1/rerank` directly via `httpx`. Shares `JINA_API_KEY` with embeddings. No SDK needed — Jina's rerank API is OpenAI-compatible formatted as a standalone POST.

- **JAILBREAK_KEYWORDS bug (fixed):** `JAILBREAK_KEYWORDS` list was defined at line 97-103 but `if any(kw in query_lower for kw in JAILBREAK_KEYWORDS): return OUT_OF_SCOPE` was missing. Queries matching jailbreak patterns were returning GENERAL instead of OUT_OF_SCOPE. Fixed by adding the check.

- **.env secrets pattern:** All live secrets are commented with `# TODO: rotate` to prevent accidental commits while keeping the file as the single source of truth for required env vars.

- **Cohere files disabled:** `CoHereProvider.py` and `CoHereReranker.py` are kept in the codebase but not imported. The imports in `providers/__init__.py`, `LLMEnums.py`, and `LLMProviderFactory.py` remain for backward compatibility but no code path activates them.

- **Project:** connexios
- **Description:** Connexio full-stack — Node.js backend (Hostinger), Connexios RAG (HF Spaces), MasarX Agent (Azure VM, centralus), shared Neon.tech PostgreSQL.

- **MasarX Azure deployment:** Agent runs on Azure VM D4as_v7 (4 vCPU, 16 GB) at `connexio-agent.centralus.cloudapp.azure.com`. Docker image stored in ACR (`connexioregistry.azurecr.io`). nginx + Let's Encrypt handles HTTPS. Health endpoint: `/api/v1/masarx/health`. Deploy workflow in `F:\MasarX_A\DEPLOY.md`.

- **MasarX health route prefix:** The health endpoint is at `/api/v1/masarx/health` (NOT `/health`). The `base.py` router has `prefix="/api/v1/masarx"`. Backend `bootstrap.js` must use the full path.

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

- **[2026-06-02] Phase 3 integration testing — items found missing after implementation:**
  (1) `DirectMessages.jsx` had no `ai_chunk`/`ai_typing` socket handlers — group/direct chat AI messages appeared all at once with no streaming animation. Fixed by adding handlers + streaming bubble component.
  (2) `SkillGapWidget` was created but never imported/used in `Profile.jsx`. Fixed by adding import and rendering after `SkillsPreviewCard`.
  (3) Sidebar had no navigation links for `/ideas`, `/courses`, `/mentors`. Fixed by adding `communityItems` entries with `Lightbulb`, `BookOpen`, `UserCheck` lucide icons + translation keys in `AppContext.jsx`.
  (4) AI responses in DirectMessages had no source pills display. Fixed in `MsgContent` default renderer.

- **[2026-06-02] DirectMessages.jsx streaming pattern:** AI streaming state is `aiStreamingText` + `aiTypingRoomId` (both cleared on room switch and on `ai_typing: false`). The `onAiChunk` / `onAiTyping` handlers use `activeRoomRef.current` for safe stale-closure access.

- **[2026-06-02] socket.accountType:** Stored at socket auth time from `decoded.account_type` (the JWT already carries it — no extra DB query). Use `socket.accountType === 'pro'` to decide `model_tier` for RAG calls.

- **[2026-06-02] Supervisor Hub concept:** The `/supervisors` page is professor/TA-only and is professor-initiated — professors browse student projects and click "Offer to Supervise". Students are notified via `Notification` (type=`system`). The backend table is `mentor_applications` (naming kept as-is). Route was `/mentors` — renamed to `/supervisors` in sidebar, App.jsx, and translations only. Do NOT confuse with professor dashboard (`/admin/dashboard`): supervisors page = request management; dashboard = analytics.

- **[2026-06-02] `user_type` for supervisor role:** `'professor'` and `'ta'` are the supervisor types. Neither `'mentor'` nor `'supervisor'` is the right value — those are other roles. Professor dashboard, supervisors page, and `professorOnly` middleware all gate on `user_type IN ('professor','ta')`.

- **[2026-06-02] @mention autocomplete pattern in DirectMessages:** Detect `/@(\w*)$/` at end of text. Store matched text after `@` in `mentionQuery` state. Filter `activeRoom.participants` by that string. On click, replace the trailing `@partial` in `text` state using `text.replace(/(?:^|\s)@\w*$/, ...)` and refocus input. Clear `mentionQuery` on send, Escape, and room switch.

- **[2026-06-02] AI trigger conflict validation:** In ProjectDetail Settings tab, after validating `@` prefix, strip `@` and compare lowercase against `members.map(m => m.FullName.toLowerCase().replace(/\s+/g,''))` and `m.username.toLowerCase()`. Block save (not just warn) if a match is found — prevents AI firing every time a teammate is @mentioned.

- **[2026-06-02] SkillGapWidget visibility:** The widget must always render (remove the `if (!gaps.length) return null` guard). Show a green success message when gaps are empty. Hiding it silently when there are no gaps made it look broken to the user.

- **[2026-06-02] Project group chat member auto-sync:** After `INSERT INTO project_members`, call `ChatRoom.findOneAndUpdate({ 'metadata.projectId': String(id), type: 'group' }, { $addToSet: { participants: Number(userId) } })`. This is non-fatal (wrapped in try/catch). Without it, new members miss group chat messages until they manually join.

- **[2026-06-02] Slash command menu in DirectMessages:** Show dropdown when `text === '/'` or text starts with `/` and has no space and length ≤ 8. Each entry has `{ cmd, desc }`. Filter entries by `c.cmd.startsWith(text)`. On click, set text to the command string and focus input. Close on Escape, send, and room switch.

- **[2026-06-03] MasarX VALID_INTENTS must be kept in sync with INTENT_TO_SUBGRAPH_MAP.** `validate_idea` and `preview_team` were in `conditions.py` and working in the graph but silently returning HTTP 400 because they were missing from `VALID_INTENTS` in `webhook_routes.py`. Always update both when adding a new intent.

- **[2026-06-03] State-level errors in LangGraph nodes don't auto-surface as HTTP errors.** When a node returns `{"error": "...", "draft_status": "error"}` and routes to END cleanly, `invoke_masarx` still returns HTTP 200 — only exceptions become proper error signals. Added a post-graph check in `invoke_masarx` that converts `error + draft_status=="error"` into `signal: masarx_agent_error` so `manual_trigger` can return HTTP 500.

- **[2026-06-03] Groq rejects Pydantic schemas that contain numeric range validators (`ge`, `le`).** `ge=0, le=100` on an `int` field generates `"minimum": 0, "maximum": 100` in the JSON schema. Groq's tool-calling layer throws before the LLM even runs, causing a silent fallback. **Never use `ge`/`le` on Pydantic fields passed to `create_structured_client`.**

- **[2026-06-03] All Pydantic models for `create_structured_client` must have `ConfigDict(populate_by_name=True)`, `alias=`, and `Optional` + `default`/`default_factory` on every field.** Required fields with no defaults cause `ValidationError` when the LLM returns partial JSON — the `except` block silently swallows it and the fallback fires. The working reference pattern is `EndorsedSkillsResult` in `skill_endorsement_subgraph.py`. Follow it exactly.

- **[2026-06-03] Groq `response_format: json_object` requires the word "json" in the prompt.** `create_structured_client` passes `response_format: {"type": "json_object"}` to Groq. If the prompt/system message contains no variant of the word "json", Groq throws `invalid_request_error: 'messages' must contain the word 'json'`. This was the root cause of ALL `ideas_subgraph` failures — the system prompts said "return a structured assessment" with no "json" mention. **Fix: always include "JSON" in any prompt that will be sent with `response_format: json_object`. Alternatively, use `generate_text` with explicit JSON instructions in the prompt — avoids the constraint entirely.**

- **[2026-06-03] Small Groq models (utility, ~8B) skip fields under complex multi-field Pydantic schemas.** They return valid JSON but with empty strings and empty lists for fields beyond the first 2-3. Pydantic fills the rest with defaults — no exception thrown, no fallback, just silent empty output. Fix: use `create_generation_client()` + `GENERATION_MODEL_ID` for any structured output call that has ≥4 fields or nested lists. `endorse_skills` (2 fields, simple schema) stays on utility. `recommend_skills`, `validate_idea`, `preview_team` all moved to generation model.

- **[2026-06-03] Use `create_structured_client(PydanticModel)` for all LLM calls that need JSON.** `generate_text` + regex/`_safe_json` JSON parsing fails 20-40% of the time with Groq models. Pydantic structured output is reliable. Pattern: define a `BaseModel`, pass to `create_structured_client()`, call `.ainvoke([system, user])`, then `.model_dump()`.

- **[2026-06-03] `detect_risks` cross-scan memory pattern:** `fetch_monitor_context` fetches the most recent `risk_report` doc via `db_tool.get_documents(project_id, doc_type="risk_report")` and extracts the `## AI Risk Assessment` section. This is injected into `RISK_DETECTION_PROMPT` as `previous_analysis` + `previous_scan_date`. The LLM prompt explicitly asks to compare against the previous scan.

- **[2026-06-03] Wolfram tool in audit_subgraph is permanently mocked.** `wolfram_tool.calculate()` always returns `"Mock calculation for: ..."` in production (no real API key). Removed the entire Wolfram call path. Health score is now pure Python: `(completed/total)*100 − overdue*10 + min(in_progress,5)*2`, clamped 0–100.

- **[2026-06-03] `marketplace_ideas` vs `project_ideas` are two separate tables.** `marketplace_ideas` = commercial buy/sell idea marketplace (price, cart, orders, Stripe). `project_ideas` = Phase 3 collaborative idea marketplace (tech_stack, looking_for, team formation). The AI intents `validate_idea` and `preview_team` target `marketplace_ideas` since `IdeaDetail.jsx` (/ideas/:id) renders from that table. Do NOT confuse the two.

- **[2026-06-03] `ideas.routes.js` did not register `POST /:id/validate` or `POST /:id/preview-team`.** The controller functions `validateIdea` and `previewTeam` existed in `ideas.controller.js` but were never imported or registered. Both are now wired. Always verify routes file when NOTES.md marks a backend endpoint "✅ Fixed" — it may just mean the controller function was written.

- **[2026-06-03] Celery beat runs in-process on the Azure VM.** `start.sh` uses `celery -A celery_app worker -B --loglevel=info &`. The `-B` flag runs Beat in-process alongside the worker — no separate beat process needed. Risk/workload crons ARE firing automatically.

- **[2026-06-03] No Redis in the Azure VM Docker Compose.** The `docker-compose.yml` defines only the `masarx` service. Redis-backed circuit breaker persistence would require adding a Redis service. For now, the REDIS_URL setting (from Upstash?) may provide cloud Redis, but it is not in the compose file.

- **[2026-06-03] Gap 1.5 sprint-scoped task generation (implemented).** Sprints now emit only the next capacity-sized batch from a persisted "canonical" plan instead of regenerating the whole project every sprint. Mechanism: (1) backend `project.sprint_started` sends `sprint_id` (top-level string) + `payload:{sprint_name,sprint_goal,sprint_seq}`; (2) `task_planner` detects sprint mode, stores the first plan in PG `project_intelligence` key `canonical_phase_plan`, and on every sprint calls `_emit_sprint_batch` which reads `current_phase_index`, advances past fully-done phases (completion-driven, NOT 1-sprint-per-phase), and emits one phase's not-yet-created tasks capped at `max(4, team_size*2)`; (3) tasks sync to MySQL with `sprint_id`; (4) sprint-close retro counts `WHERE sprint_id=?`. Skip statuses `phase_in_progress`/`skipped_complete` route straight to END via a conditional edge.

- **[2026-06-03] `fireEvent`/`triggerIntent` POST the data object AS the raw webhook body, parsed by `WebhookPayload`.** Only its declared fields survive (`project_id,user_id,sprint_id,member_ids,payload,requirements`). Any extra top-level key (e.g. `sprint_name`) is silently dropped by Pydantic. To get custom data into a subgraph's `state["output"]`, nest it under `payload:{...}`. `sprint_id` must be a STRING (Pydantic v2 won't coerce int→str).

- **[2026-06-03] MasarX `project_intelligence` table (PG, MasarX-owned).** Generic cross-intent KV store `{project_id, key, value JSONB, updated_at, PK(project_id,key)}`, created idempotently in `db_tool._run_migrations()`. Access via `db_tool.get_intelligence(pid, key)` / `set_intelligence(pid, key, value)` (best-effort, never raise; value stored via `CAST(:v AS JSONB)` with `json.dumps`). Gap 1.5 keys: `canonical_phase_plan`, `current_phase_index`.

- **[2026-06-03] `db_tool.get_pending_plan(token)` takes an approval TOKEN; use `get_pending_plan_by_project(pid)` to look up by project.** Both return SQLAlchemy ORM objects (read attributes like `.plan_data`, `.approval_token` — they have NO `.get()` method). The task_planner idempotency guard had been calling `get_pending_plan(project_id)` + `.get()`, so it was dead code (see bug-188).

- **[2026-06-03] `project_intelligence` is now wired (Gap 9.1).** Producers: `detect_risks`→`last_risk_level`, `comprehensive_audit`→`last_health_score`, `task_planner`→`canonical_phase_plan`/`current_phase_index`. Read via `db_tool.get_intelligence(pid,key)`, write via `set_intelligence(pid,key,value)`.

- **[2026-06-03] AI risk level write path:** `detect_risks` derives `low|medium|high` and calls `backend_client.set_project_risk` → `PUT /api/projects/:id/ai-risk` (service-JWT, sets `projects.ai_risk_level`+`ai_risk_updated_at`). New controller `setAiRiskLevel`.

- **[2026-06-03] `Document.doc_metadata` maps to DB column `metadata`** (SQLAlchemy reserves `.metadata`). `save_document` accepts `doc_data["metadata"]`. Used by risk_report (overall_risk summary) and audit (health_score history for diffing).

- **[2026-06-03] Idea AI scores live on `marketplace_ideas` (NOT project_ideas), and `validateIdea` already persists them.** The score columns + the `UPDATE marketplace_ideas SET feasibility_score...` were already present in uncommitted backend work. Only the React badges remain.

- **[2026-06-03] Token usage (Gap 9.2)** is logged fire-and-forget from `OpenAIProvider.generate_text` via `db_tool.log_usage` → `masarx_usage`. intent/project_id are null (provider has no request context). Direct `client.chat.completions.create` calls (e.g. task_subgraph rotation) are NOT logged.

- **[2026-06-03] Audit cache (Gap 7.2) only applies to automated runs.** `triggered_by=="celery_beat"` audits skip regeneration if the last audit is <6h old; manual/webhook triggers always run fresh. Cache hit sets `_audit_cached` and routes to END.

- **[2026-06-03] Pre-merge PR review (Gap 5.1):** events `pullrequest.opened/updated` → `review_pr`, gated in `handle_event` by MySQL `projects.ai_review_on_open_prs` (default OFF, read via `backend_client.get_project`). `pullrequest.merged` always runs. Reviews post back via new `github_tool.post_pr_comment` (issues-comments endpoint; needs `pull_requests:write`). Large diffs truncated per-file (`_truncate_diff`, ~24k chars).

- **[2026-06-03] Onboarding tasks are MySQL-first (Gap 2.2).** `onboarding_task_creator` syncs to MySQL first; only mirrors to PG on success; MySQL failure → `draft_status: error` (no PG write). Same rule should apply to any source-of-truth task write.

- **[2026-06-03] Invite dedup (Gap 2.4) uses `masarx_invitations`.** `db_tool.get_recently_invited(pid, days=30)` filters candidates in `team_matching_node`; `record_invitations` writes after queuing. The owner-approval flow itself (Gap 2.1) was already implemented via the backend pending-invitations table — don't rebuild it.

- **[2026-06-03] Endorse dedup (Gap 6.1)** stores per-skill timestamps in `project_intelligence` key `endorse_ts_user_<uid>` ({skill_lower: iso}); skills endorsed <14d ago are dropped from `skills` in `performance_analysis_node` (empty list → downstream no-ops). Proficiency text→int map (Advanced=5/Intermediate=3/Beginner=1) is sent as `skill_levels` to `updateMyProfile`, which upserts `user_skills.proficiency_level` (Gap 6.3). user_skills has no unique key — upsert = UPDATE then INSERT-if-0-rows.

- **[2026-06-03] `precomputed_match_scores`** is written to `project_intelligence` by `recommender_refiner`; the weekly cron `masarx.tasks.run_match_precompute` (Mon 04:00 UTC) fans out `refine_recommender` per project. Consumer: `preview_team` (read best-effort).

- **[2026-06-03] Gap 2.3 proficiency in matching:** `GET /api/users/proficiency-map` (route placed BEFORE `/:id` in user.routes; `/skills/:type` already exists so don't use `/skills/...`) returns `{uid: {skill_lower: level}}`, optional `?user_ids=`. `backend_client.get_users_proficiency` → `team_matching_node` adds `skill_level_bonus = avg(level)/5 * 0.1` (cap 0.1).

- **[2026-06-03] ALL backend/MasarX plan work is complete.** Only React remains (`F:\MasarX_A\FRONTEND_TASKS.md`). Full per-graph/intent logic is documented in `F:\MasarX_A\MASARX_GRAPHS_AND_INTENTS.md`. Testing in `IMPLEMENTATION_TESTING.md`.

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

- **[2026-05-23] `cohere` package must stay in Requirements.txt despite being unused.**
  `CoHereProvider` is imported unconditionally at module level in `providers/__init__.py:2` and `LLMProviderFactory.py:2`. Removing `cohere` from dependencies causes `ModuleNotFoundError` at startup — the import chain is triggered before any code path that could skip it. A lazy import (inside the `if provider == COHERE` branch) would fix this, but until then, the dependency must stay.

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

- **[2026-06-01] Pydantic v2 does NOT coerce int → str (breaking change from v1).**
  In Pydantic v1, passing an integer for a `str` field was silently coerced. In v2 this raises `ValidationError: Input should be a valid string` → HTTP 422 in FastAPI. Always stringify integer IDs before sending them in webhook payloads: `user_id: String(user.UID)`, not `user_id: user.UID`.

- **[2026-06-01] MySQL query() returns { rows } — affectedRows is on result.rows, not result.**
  For UPDATE/DELETE queries, `query()` wraps the MySQL OkPacket in `{ rows: OkPacket }`. Reading `result.affectedRows` is always undefined. Must use `result.rows?.affectedRows ?? 0` to check whether rows were affected.

- **[2026-06-01] express-rate-limit v8 renamed 'max' → 'limit'.**
  v8 (installed as 8.5.2) silently ignores `max`. Must use `limit: N`. Also: `standardHeaders: true` changed to `standardHeaders: 'draft-7'`. Passing the old API causes the limiter to accept all requests with no error.

- **[2026-06-01] X-Response-Time must override res.end, not listen on 'finish'.**
  `res.on('finish', () => res.setHeader(...))` fires after headers are flushed — setHeader() is a no-op at that point. Correct pattern: save `originalEnd = res.end.bind(res)`, then `res.end = function(...args) { res.setHeader('X-Response-Time', ...); return originalEnd(...args); }`.

- **[2026-06-01] Phase 0 tables were not actually in dbconnection.js despite being checked off.**
  `contribution_evidence`, `audit_log`, `active_sessions`, `project_contracts`, `contract_signatures`, and all Phase 0 column migrations were missing from `createTables()`. Added in Phase 2 session. Always verify DB table existence with a grep before writing code that INSERTs into them.

- **[2026-06-02] Do NOT build a "browse mentors" page for students — that concept is wrong for Connexio.**
  The supervisor feature is professor-initiated: professors browse student projects and offer supervision. There is no student-facing mentor browser. The page at `/supervisors` is professor/TA only and hidden from students. Building it as a student-facing browse-and-invite page was incorrect and had to be rewritten.
  **Why:** In the academic context of Connexio, "supervisor" = a DR or TA assigned to a student capstone project. Supervision flows from professor to student, not the other way around.

- **[2026-06-02] `GET /api/users` is adminOnly — never call it from a regular user-facing page.**
  The endpoint is gated by `adminOnly` middleware (X-Admin-Key check). Using it from the frontend for browsing professors/mentors returns 403. Add a dedicated `GET /api/users/mentors` (or `/supervisors`) route with only `protect` middleware. Lesson: always check the route middleware before wiring a frontend page to it.

- **[2026-06-01] Global `validator.escape()` on req.body corrupts stored data.**
  HTML-escaping all string fields globally (e.g. `&` → `&amp;`) stores escaped HTML in MySQL and causes double-escaping when rendered. Correct approach: trim-only globally (`validator.trim`), escape at controller level for fields that accept freeform HTML. See `sanitize.js`.

- **[2026-06-01] `generateToken` must be async after adding JTI + active_sessions insert.**
  All call sites (`await generateToken(user)`) updated in auth.controller.js. Making it sync and fire-and-forget would leave the JTI unregistered before the token is returned to the client.

- **[2026-06-01] `append_message` now accepts optional `source` param.**
  Stored in the message dict alongside `role/content/node/timestamp`. Used to distinguish `chat_mention` (from socket @mention) vs page queries. The `source` param is threaded end-to-end: socket.js → agent.py → answer_agent_chat_stream → append_message.

- **[2026-06-02] Security middleware (Helmet, rateLimiter, X-Response-Time) was deployed to Hostinger but never committed to git.**
  connexio.icu already had Helmet headers and X-Response-Time live, but the local git repo had none of it. This causes a silent drift: live server has features the repo doesn't. Always commit + push BEFORE deploying to Hostinger to keep git as the source of truth.

- **[2026-06-02] `pending_verification` was added to ALLOWED_STATUS in tasks.controller.js but the MySQL tasks.status ENUM was never updated.**
  Without the ENUM update, `UPDATE tasks SET status='pending_verification'` silently stores an empty string or fails. The ENUM migration must be in dbconnection.js's createTables() alongside the ALLOWED_STATUS change in the controller.

- **[2026-06-02] KanbanBoard's `onVerify` prop was never passed from ProjectDetail.jsx.**
  The verify button in TaskCard only renders when `onVerify && canAssign` are both truthy. Even though the handler was defined in ProjectDetail, it wasn't passed as a prop. Always search for the prop usage in the parent component when a child feature appears missing.

- **Phase 3 tables:** `courses`, `course_members`, `course_projects`, `project_ideas`, `idea_members`, `mentor_applications` — all in `dbconnection.js` createTables(). Phase 3 APIs: `/api/courses`, `/api/professor`, `/api/ideas`, `/api/skills`.

- **ai_trigger column was BOOLEAN, now VARCHAR(50):** The Phase 0 migration added it as BOOLEAN but Phase 3 needs it as a keyword string (e.g. `@connexio`). A `MODIFY COLUMN` alter is in dbconnection.js to fix existing columns.

- **socket.js isAIMentioned is now async:** It queries MySQL for the project's `ai_trigger` per call. The group/direct chat handler now uses streaming RAG (same as ai_chatbot) with shortcut command detection. `parseCommand()` and `checkAIRateLimit()` are module-level helpers.

- **SHORTCUT_COMMANDS dict in NLPController.py:** Defined at module level above the class. Both `answer_agent_chat` and `answer_agent_chat_stream` check this dict before the greeting fast path. Matching commands override `query` and set `model_tier = 'generation'`.

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
