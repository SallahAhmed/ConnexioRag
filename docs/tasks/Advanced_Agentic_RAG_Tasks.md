# Advanced Agentic RAG Task List

## Phase 1: Retrieval Excellence (Hybrid Search & Reranking)
- `[x]` **Implement Postgres Full-Text Search (FTS)**
  - `[x]` Update `create_collection` to initialize a GIN index on the `text` column in `PGVectorProvider.py`.
  - `[x]` Add `search_by_text` method to perform FTS using `tsvector`.
  - `[x]` Implement `hybrid_search` to fetch and combine results from both vector search and FTS.
- `[x]` **Implement Cross-Encoder Reranker**
  - `[x]` Add `sentence-transformers` to `requirements.txt`.
  - `[x]` Create `RerankerInterface.py`.
  - `[x]` Create `SentenceTransformerReranker.py` implementing the BAAI cross-encoder.

## Phase 2: Agentic Reasoning & Reliability
- `[x]` Implement Query Decomposition (Thinking Phase)
- `[x]` Implement Relevance Grading (CRAG)

## Phase 3: UX & Observability
- `[ ]` Implement Streaming & Citations
- `[ ]` Implement Traceability (TraceManager)

## Phase 4: Fast & Responsive Backend
- `[ ]` Setup Celery infrastructure (Redis)
- `[ ]` Implement `celery_worker.py`
- `[ ]` Refactor FastAPI integration for async indexing
