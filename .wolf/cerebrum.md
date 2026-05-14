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

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

- **[2026-05-14] Do not use `context.stats.*` or `context.completionRate` from `getProjectContext()`.**
  `getProjectContext()` returns `{ project, tasks[], members[] }` only. Always compute stats from `context.tasks.filter(...)` inline. The `generateProjectReport()` function is the correct reference implementation.

- **[2026-05-14] Do not pass a string as `project_id` to the RAG chat URL.**
  The FastAPI route `POST /api/v1/nlp/agent/chat/{project_id}` has `project_id: int` — passing `'general'` causes a 422 validation error. Use `0` for projectless sessions instead.

## Decision Log

- **[2026-05-14] `ai_chatbot` rooms use `project_id=0` when calling the RAG.**
  Chosen over creating a separate `/chat/general` endpoint to avoid changing the RAG's routing structure. The RAG converts `0 → None` in `agent.py` keeping the NLPController's `Optional[int]` signature clean.

- **[2026-05-14] `ai_chatbot` rooms always call RAG; group/direct require `@connexio` mention.**
  In a 1:1 AI chatbot room the user expects every message to be answered. In group chat, the AI should only respond when explicitly addressed to avoid noise.
