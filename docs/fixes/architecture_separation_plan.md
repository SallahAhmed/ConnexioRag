# Architecture Separation Plan: Connexios & MasarX

## 1. The Context (Read First)

If you are reading this for the first time, you need to understand the current state of the ecosystem:
We have two major systems:

1. **Connexios**: A FastAPI-based Agentic RAG system. It is designed to handle fast conversational chat, document vectorization (PGVector), and short-term memory.
2. **MasarX**: A LangGraph-based Multi-Agent orchestration engine. It is designed for long-running, autonomous, complex tasks (like writing documentation, scanning for project risks, and creating task sprints with Human-In-The-Loop approval).

### 1.1 The Problem

Historically, before MasarX was built, **Connexios** was given "mocked" or simplified endpoints to handle heavy agentic tasks (like `/doc-gen` and `/task-architect`).
Now that **MasarX** exists, these endpoints in Connexios are redundant. Keeping them violates the **Single Responsibility Principle**. If we leave them, Connexios will try to do complex orchestration using simple LLM prompts, which leads to timeouts and poor quality.

### 1.2 The Vision

- **Connexios becomes "The Brain & Voice"**: It handles file chunking, semantic vector search, user memory, and streaming chat.
- **MasarX becomes "The Hands & Eyes"**: It handles deep project audits, automated documentation, team matchmaking, and heavy asynchronous workflows.

---

## 2. Action Plan: What Needs to be Removed

To achieve this separation, we must strip the execution-heavy endpoints out of Connexios. Follow these steps carefully:

### Step 1: Remove Routes (`src/Routes/agent.py`)

Open `src/Routes/agent.py` and completely delete the following endpoints and their corresponding functions:

1. **`GET /supervisor/risks/{project_id}`**
   - _Why:_ Replaced by MasarX's `AuditAgent` and `MonitorAgent` (`comprehensive_audit` and `detect_risks`).
2. **`GET /coach/path/{project_id}`**
   - _Why:_ Replaced by MasarX's mentoring and `endorse_skills` graph paths.
3. **`POST /doc-gen/{project_id}`**
   - _Why:_ Replaced by MasarX's `DocAgent` (`generate_readme` and `generate_retro`).
4. **`POST /task-architect/plan/{project_id}`**
   - _Why:_ Replaced by MasarX's `TaskAgent` (`create_tasks`), which supports crucial Human-In-The-Loop (HITL) pausing and approval.

_(Note: Keep the `/chat`, `/chat/stream`, and `/portfolio` endpoints untouched. They are the core of Connexios)._

### Step 1.5: Remove Legacy Endpoint (`src/Routes/nlp.py`)

Open `src/Routes/nlp.py` and delete the following endpoint:

1. **`POST /index/answer/{project_id}`**
   - _Why:_ This is an old, legacy version of the RAG chat. It hardcodes `user_id=1` and lacks support for `session_id` and persona tracking. It is completely redundant because `/agent/chat` does the exact same thing but better.

### Step 2: Clean up NLPController (`src/controllers/NLPController.py`)

Now that the routes are gone, the controller methods are dead code. Open `NLPController.py` and delete:

1. `get_supervisor_risks(self, project_id: Optional[int])`
2. `get_coach_path(self, user_id: int, project_id: Optional[int])`
3. `get_doc_gen(self, project_id: int, doc_type: str)`
4. `get_task_architect_plan(self, query: str, user_id: int, project_id: int)`

### Step 3: Clean up ToolManager (`src/controllers/helpers/ToolManager.py`)

Finally, remove the underlying tools that only existed to serve those deleted endpoints. Open `ToolManager.py` and look for the placeholder methods. Delete:

1. `get_project_risks(...)`
2. `get_streak_quote(...)` (This was the placeholder for the coach path)
3. `generate_project_docs(...)`
4. Any other placeholder methods related strictly to task generation or audits.

---

## 3. Final Verification

Once these steps are complete:

1. Run your FastAPI server (`uvicorn main:app`).
2. Check the Swagger UI (`/docs`). You should only see the clean, focused endpoints for Data Uploads, NLP Indexing, and Core Agent Chat.
3. From now on, any front-end request for "Generate a README" or "Audit my Project" must be routed directly to the **MasarX** API, not Connexios.
