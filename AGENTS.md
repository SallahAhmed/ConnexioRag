# Connexios RAG — Agent Instructions

## Project Structure

This is the **Connexios RAG** service (`C:\Users\salla\Connexios\src`). It's one of three services sharing a Neon.tech PostgreSQL:

| Service | Path | Host |
|---------|------|------|
| **Connexios RAG (this)** | `src/` | HF Spaces: ConnexioRag |
| MasarX Agent | `F:\MasarX_A\src` | HF Spaces: ConnexioAgent |
| Node.js Backend | `github.com/Hassan19Z/Connexio-backend` | Hostinger |

**Auth model:** RAG uses `X-API-Key` header (`CONNEXIO_INTERNAL_API_KEY`). Dev bypass if key is unset (raises 500).

## Dev Commands

```bash
# From src/
uvicorn main:app --reload --port 8080                    # API server
python -m pytest tests/ -v --tb=short                    # Run all tests (42 tests)
python -m celery -A celery_app worker --loglevel=info     # Celery worker
python -m celery -A celery_app beat --loglevel=info       # Celery Beat
```

## Embedding Provider (Jina AI)

- **`EMBEDDING_BACKEND="OPENAI"`** — reuses `OpenAIProvider` with Jina's OpenAI-compatible API
- **API URL:** `JINA_API_URL` → `https://api.jina.ai/v1`
- **Model:** `jina-embeddings-v3` (1024 dim)
- **Task parameter:** `OpenAIProvider.embed_text()` passes `"task": "retrieval.query"` or `"retrieval.passage"` via `extra_body` when model ID contains "jina"
- Set `OPENAI_API_KEY` to Jina API key in `.env`
- Same key works for reranking via `JinaReranker` (httpx POST to `/v1/rerank`)

## Key Architecture Facts

- **Tiered Response:** `OUT_OF_SCOPE` → canned, no `project_id` → utility (8B), project set → generation (70B)
- **Collection naming:** `collection_{embedding_size}_{project_id}` — single source of truth in `NLPController.create_collection_name()` and `ToolManager._get_collection_name()`
- **Vector DB:** PGVector (not Qdrant). Default `VECTOR_DB_BACKEND=PGVECTOR`
- **CRAG tools:** Wikipedia, ArXiv always available. Google/SerpAPI, GitHub, StackOverflow gated by API keys
- **Streaming SSE order:** meta event → token chunks → `[DONE]`
- **No direct DB to Node.js backend** — all live data via `BackendApiClient` REST calls (5-min cache)
- **Cohere provider files retained but inactive** — `CoHereProvider.py`/`CoHereReranker.py` present, not used
- **`Requirements.txt` includes `cohere==5.21.1`** — required because `CoHereProvider` is imported unconditionally at module load time in `__init__.py` and `LLMProviderFactory.py`. Removing it crashes `celery_app.py` and `main.py` on startup (`ModuleNotFoundError: No module named 'cohere'`).

## WorkflowController Gotchas

- **JAILBREAK_KEYWORDS** (line 97-103) IS checked (fixed). All jailbreak patterns return `OUT_OF_SCOPE` immediately.
- **Fast path:** Queries <50 chars NOT in `_SKIP_FAST_PATH` → `GENERAL`. Short Arabic questions also skip fast path.
- **Fuzzy matching:** `difflib.get_close_matches()` with cutoff 0.8 against `_FUZZY_TERM_NODE` keys for typo tolerance.
- **Tech/AI exceptions** in OOS_KEYWORDS: query matching OOS passes through if it also contains tech keywords (Python, AI, code, etc.)

## .env Secrets

All live secrets in `.env` are **commented out** with `# TODO: rotate`. Before running:
```
JINA_API_KEY=        # Required for embeddings + reranking
GROQ_API_KEY=        # Required for generation
CONNEXIO_INTERNAL_API_KEY=  # Required for auth
```
All other keys (Cohere, DeepSeek, SerpAPI, GitHub) are optional/unused.

## Test Quirks

- `mock_utility_client` classifier must detect jailbreak words in the LLM prompt to return `OUT_OF_SCOPE`
- Mock `default_vector_size` = 1024 (matches jina-embeddings-v3)
- `conftest.py` patches `get_settings` in all relevant modules via autouse fixture
