# RAG Enhancement Implementation Plan

This plan outlines the steps, organized into structured phases, to upgrade the `mini-rag-app` from a basic RAG system to a production-grade **Advanced Agentic RAG** system.

## User Review Required

> [!IMPORTANT]
> **Execution Strategy**: The plan is now divided into 4 distinct phases (including Celery Async Processing). We will execute and verify each phase independently before moving to the next.

## Phase 1: Retrieval Excellence (Hybrid Search & Reranking)

*Goal: Ensure the agent fetches both exact keyword matches and semantic concepts, and ranks them accurately using a specialized AI model.*

#### 1. Implement Postgres Full-Text Search (FTS)
- **File**: `PGVectorProvider.py`
- Update `create_collection` to initialize a GIN index on the `text` column.
- Add `search_by_text` method to perform FTS using `tsvector`.
- Implement `hybrid_search` to fetch results from both vector search and FTS.

#### 2. Implement Cross-Encoder Reranker
- **Requirement**: Install `sentence-transformers` via `requirements.txt`.
- **Files**: Create `RerankerInterface.py` and `SentenceTransformerReranker.py` in `src/stores/vectordb/`.
- **Logic**: Use the `BAAI/bge-reranker-base` model to take the combined results from `hybrid_search` and re-score them for maximum accuracy.

---

## Phase 2: Agentic Reasoning & Reliability (CRAG & Decomposition)

*Goal: Make the agent "think" before it acts. It will break down complex questions and grade its own retrieved data in English, ensuring high reliability.*

#### 1. Query Decomposition (Thinking Phase)
- **File**: `NLPController.py`
- Add an English "Query Planner" LLM step at the start of the chat loop.
- The planner will break complex queries into simpler sub-tasks to query exact tools (e.g., "Find docs on X" AND "Get stats for Y from SQL").

#### 2. Relevance Grading (CRAG - Corrective RAG)
- **Files**: `relevance_grading.py` (New), `NLPController.py`
- Create English grading templates (Relevant, Ambiguous, Irrelevant).
- Insert a "Relevance Check" step after retrieval. If the reranked documents are graded `Irrelevant` to the decomposed queries, the agent will trigger a fallback search (Wiki/Dataset) instead of hallucinating.

---

## Phase 3: UX & Observability (Streaming, Citations, & Traces)

*Goal: Make the application feel fast and transparent to the end-user and the developer.*

#### 1. Streaming & Citations
- **Files**: `OpenAIProvider.py`, `NLPController.py`, `agent.py`
- Implement `stream_text` using OpenAI's `stream=True`.
- Refactor `answer_agent_chat` to yield server-sent events (SSE).
- Update the final generation prompt to force inline citations (e.g., "According to [Doc 1]...") and ensure the final text matches the user's detected language (e.g., Arabic).

#### 2. Traceability (Observability)
- **File**: `TraceManager.py` (New)
- Create a manager to log the full timeline of the request (Original Query -> Decomposed Queries -> Retrieved Sources -> Relevance Grades -> Final Prompt -> Output). This makes debugging the Agentic flow seamless.

---

## Phase 4: Fast & Responsive Backend (Celery & Redis)

*Goal: Offload heavy data processing tasks (like indexing PDFs and generating embeddings) to background workers so the FastAPI server remains fast and never times out.*

#### 1. Infrastructure Setup
- **File**: `docker-compose.yml` (or similar environment config)
- Add a `redis` container as the Celery Message Broker.
- Add `celery` and `redis` to `requirements.txt`.

#### 2. Celery Worker Initialization
- **File**: `celery_worker.py` (New)
- Initialize the Celery application bound to the Redis broker.
- Migrate the heavy data ingestion logic from `NLPController.py` and `ProcessController.py` into a new `@celery_app.task` function (e.g., `background_index_file`).

#### 3. FastAPI Integration integration
- **File**: `data.py` (FastAPI router)
- Refactor endpoints that trigger vector insertions to use `task.delay()` instead of `await`, immediately returning a `task_id` to the user so the frontend knows processing has started without waiting for completion.

---

## Verification Plan

### Automated Tests
- Test Hybrid Search: Ensure results from `tsvector` and `vector` are both present before routing to the reranker.
- Test Streaming: Use a script to consume the SSE stream and verify chunk arrival.

### Manual Verification
- Verify that complex queries (e.g., "Compare X with Y") now trigger multiple searches.
- Confirm that citations `[Doc X]` are present in the final answer and match the retrieved data.
- Confirm that passing an Arabic query performs internal tasks (Decomposition, Grading) in English, but the final streamed response is correctly formatted in Arabic.
- Verify Celery Indexing: Test an upload and confirm an immediate response with a task ID, while observing the Celery worker logs complete the vector insertions in the background.
