# Connexios RAG — Agent Instructions

## Project Structure

This is the **Connexios RAG** service (`C:\Users\salla\Connexios\src`). One of three services sharing a Neon.tech PostgreSQL:

| Service | Path | Host |
|---------|------|------|
| **Connexios RAG (this)** | `src/` | HF Spaces: ConnexioRag |
| MasarX Agent | `F:\MasarX_A\src` | HF Spaces: ConnexioAgent |
| Node.js Backend | `github.com/Hassan19Z/Connexio-backend` | Hostinger |

**Auth:** All routes except `/api/v1/` and `/api/v1/health` require `X-API-Key` header matching `CONNEXIO_INTERNAL_API_KEY`. If key is unset, server raises 500 at startup.

---

## Dev Commands (from `src/`)

```bash
uvicorn main:app --reload --port 8080                    # API server
python -m pytest tests/ -v --tb=short                    # Run all tests (110 tests)
python -m celery -A celery_app worker --loglevel=info     # Celery worker
python -m celery -A celery_app beat --loglevel=info       # Celery Beat
```

---

## Architecture

### Embeddings (Jina AI via OpenAIProvider)

- `EMBEDDING_BACKEND="OPENAI"` — reuses `OpenAIProvider` pointed at Jina's OpenAI-compatible API
- **URL:** `JINA_API_URL` (`https://api.jina.ai/v1`)
- **Model:** `jina-embeddings-v3` (1024 dim)
- **Auth:** `JINA_API_KEY`
- **Task parameter:** `OpenAIProvider.embed_text()` passes `"task": "retrieval.query"` or `"retrieval.passage"` via `extra_body` when model ID contains "jina"
- **Nomic fallback:** If model ID contains "nomic-embed-text", uses `"search_query: "` / `"search_document: "` text prefixes instead

### Reranker (Jina)

- `JinaReranker` — `httpx.AsyncClient` POST to `{JINA_API_URL}/v1/rerank`
- **Model:** `jina-reranker-v2-base-multilingual` (hardcoded default)
- **Auth:** Same `JINA_API_KEY` as embeddings
- Initialized in `main.py:145-147`; falls back to `None` if key unset (reranking disabled)

### LLM Generation (Groq)

- `GroqProvider` subclasses `OpenAIProvider` — Groq is OpenAI-compatible
- `GENERATION_BACKEND` / `UTILITY_BACKEND` both `"GROQ"` by default
- **Tiered response:** `OUT_OF_SCOPE` → canned; no `project_id` → utility model (8B); project set → generation model (70B)
- Streaming SSE order: meta event → token chunks → `[DONE]`

### Vector DB

- Default: `PGVector` (not Qdrant). Set `VECTOR_DB_BACKEND=PGVECTOR`
- **Collection naming:** `collection_{embedding_size}_{project_id}` — single source of truth in `NLPController.create_collection_name()` and `ToolManager._get_collection_name()`
- Qdrant code present but unused by default

### CRAG Tools

| Tool | Gated by | Always available? |
|------|----------|-------------------|
| Wikipedia | none | Yes |
| ArXiv | none | Yes |
| Google Search | `SERPAPI_API_KEY` | No |
| GitHub | `GITHUB_TOKEN` | No |
| StackOverflow | `STACKOVERFLOW_API_KEY` | No |
| Python REPL | none | Yes |

### Backend Communication

- **No direct DB access to Node.js backend data** — all live project/user/task data via `BackendApiClient` REST calls
- 5-minute in-memory cache for project details and user profiles
- Tasks are NOT cached (volatile, 0s TTL)
- Auth to Node.js backend: short-lived service JWT signed with `JWT_SECRET` + `X-API-Key` header

---

### Standalone / Playground Mode

The Space can run with no Node.js backend and no MasarX. Set these as HF Space variables:

```
STANDALONE_MODE      = true
ENABLE_BACKEND_SYNC  = false
ENABLE_MASARX_SYNC   = false
ENABLE_CELERY        = true   # set false if Redis is unreachable
```

- `STANDALONE_MODE` serves a dependency-free chat playground at `/` (`src/static/chat.html`, ~2900 lines of inline HTML/CSS/JS, zero network requests — no CDN, no fonts, no favicon file).
- The UI calls `NLPController.answer_agent_chat_stream` **in-process** via `src/Routes/ui.py` — it never loops back through HTTP, so the browser never sees `CONNEXIO_INTERNAL_API_KEY`.
- Auth split: `verify_api_key_or_standalone` guards only `/ui/chat/stream` and `/ui/session/new`. `/` and `/ui/config` are open (they expose no secrets). Every other route still uses the strict `verify_api_key`.
- `project_id=0` resolves to `None` → GENERAL node → auto-upgrades to the 70B generation model. KB retrieval still works against pgvector in Neon; only live project/user/task context is lost.
- `ENABLE_CELERY` is read by `start.sh` and only affects background indexing + scheduled maintenance. Chat works fully with it off.
- The shared `NLPController` is warmed once in `lifespan` and cached on `app._nlp_controller`, because constructing it initialises `ToolManager`'s `SQLDatabase` (slow).
- `/ui/config` also returns `slash_commands`, built from `NLPController.SHORTCUT_COMMANDS`. That dict is the single source of truth for `/summary`, `/tasks`, `/blame`, `/docs`, `/audit` — the page only renders the autocomplete, never a hardcoded copy.

### Playground features (`src/static/chat.html`)

Assistant output is rendered as **markdown in the page**: headings, lists (nested), tables, blockquotes, hr, fenced code with a language label and a copy button, plus a from-scratch syntax highlighter for 12 language families. Every message carries copy; assistant messages also regenerate, user messages edit-and-resend, and the send button becomes stop mid-stream (`AbortController`). Slash commands autocomplete on `/`. Theme (dark/light), drawer state and all controls persist in `localStorage`. `Ctrl+B` drawer, `Ctrl+K` new session, `Ctrl+J` focus, `Ctrl+S` export, `Ctrl+D` theme. Per-message diagnostics (node, lang, session, trace, sources, TTFT, total, chars, ~tokens) sit behind a collapsed disclosure.

### Gotcha: SSE frames carry more than `text`

`answer_agent_chat_stream` streams `{"text": ...}` chunks, but the clear-history fast path yields `{"answer": ...}` in one frame. A client that only reads `frame.text` shows "the server returned an empty answer" for `clear history` / `new topic` / `نظف السجل`. The page accepts `text`, `answer`, `delta` and `token`.

### Gotcha: no shared CSS class names between layout and message markup

The layout container is `.workspace`. It was briefly named `.body`, which also matched the per-message `.bubble .body` — that turned message bodies into row flexboxes and squeezed every table and code block to roughly one character wide while every HTML assertion still passed. Any new global class must be checked against the class names the message templates emit (`turn`, `col`, `bubble`, `body`, `rich`, `actions`, `diag`, `tag`, `code`).

### Gotcha: the UTF-8 Content-Type middleware

`ensure_utf8_response` in `main.py` only rewrites **JSON** responses. An earlier version set `Content-Type: application/json` on *every* response, which relabelled `/docs` HTML and SSE as JSON — browsers downloaded the Swagger UI and the playground instead of rendering it, and `EventSource` could not consume the stream. `src/tests/test_ui_routes.py` locks this behaviour in.

### Gotcha: rate-limit exemption prefixes

`RATE_LIMIT_EXEMPT_PREFIXES` in `src/utils/metrics.py` must never contain a bare `"/"`. Every absolute path starts with `/`, so a `"/"` prefix exempts the entire API from rate limiting. Root is matched exactly via `RATE_LIMIT_EXEMPT_EXACT` instead.

## Env Vars Quick Reference

### Required (app won't start without these):
| Var | Used for |
|-----|----------|
| `POSTGRES_*` | PostgreSQL connection (Neon.tech) |
| `JINA_API_KEY` | Embeddings via OpenAIProvider + JinaReranker |
| `GROQ_API_KEY` | LLM generation (Groq) |
| `CONNEXIO_INTERNAL_API_KEY` | Auth — X-API-Key verification |

### Optional but commonly set:
| Var | Default | Notes |
|-----|---------|-------|
| `EMBEDDING_BACKEND` | `"OPENAI"` | Must be `"OPENAI"` for Jina |
| `JINA_API_URL` | `"https://api.jina.ai/v1"` | |
| `GROQ_API_URL` | `"https://api.groq.com/openai/v1"` | |
| `GENERATION_MODEL_ID` | `None` | e.g. `"llama-3.3-70b-versatile"` |
| `UTILITY_MODEL_ID` | `"llama-3.1-8b-instant"` | |
| `EMBEDDING_MODEL_ID` | `None` | e.g. `"jina-embeddings-v3"` |
| `EMBEDDING_MODEL_SIZE` | `None` | 1024 for jina-v3 |
| `VECTOR_DB_BACKEND` | `"PGVECTOR"` | |
| `MAIN_BACKEND_URL` | `"https://connexio.icu"` | Node.js backend URL |
| `SENTRY_DSN` | `None` | No-op if unset |
| `CELERY_BROKER_URL` | `None` | Celery disabled if unset |

### Model IDs — User's HF Space active values:
- `GENERATION_MODEL_ID="openai/gpt-oss-120b"` (Groq model)
- `UTILITY_MODEL_ID="meta-llama/llama-4-scout-17b-16e-instruct"` (Groq model)

---

## Key Gotchas

### Startup Crashes
- **`cohere` package must stay in `Requirements.txt`** — `CoHereProvider` is imported unconditionally at module load time in `providers/__init__.py:2` and `LLMProviderFactory.py:2`. Removing it crashes `celery_app.py` and `main.py` with `ModuleNotFoundError`.

### WorkflowController (`detect_node()`)
- **JAILBREAK_KEYWORDS IS checked** (line 97-104, fixed). All jailbreak patterns → `OUT_OF_SCOPE`
- **Jailbreak strip:** Prefixes like "ignore previous instructions and tell me" are stripped before matching
- **Conversational follow-ups:** `"you mean"`, `"you said"`, `"قصدك"` → `GENERAL` immediately
- **OOS with tech exception:** OOS keywords pass through if query also contains tech keywords (Python, AI, code, بايثون, etc.)
- **Fuzzy matching:** `difflib.get_close_matches()` cutoff 0.8 against `_FUZZY_TERM_NODE` for typos
- **Fast path:** Queries <50 chars not in `_SKIP_FAST_PATH` → `GENERAL`. Arabic questions skip fast path.

### Gemini / OpenRouter Notes
- `GENERATION_MODEL_ID_LITERAL` is defined in config.py but **never read in code** — dead config field

### File Casing
- Git has both `OpenAIProvider.py` and `OpenAiProvider.py` in history (case variants). Fixed on disk but the old entry may reappear on `git checkout` on case-sensitive systems.

### Database Schema
- Two layers: legacy Pydantic models (MongoDB-style `_id`) and SQLAlchemy ORM (`connexio/schemas/`)
- MasarX tables use quoted column names: `"TaskId"`, `"TaskName"`, `"PID"`, `"UID"` — SQLAlchemy raw SQL must use quoted identifiers

---

## .env Secrets Pattern

All live secrets in `.env` are **commented out** with `# TODO: rotate`. The `.env` file is gitignored. Real secrets go in HF Space secrets.

---

## Test Quirks

- `conftest.py` patches `get_settings` in all relevant modules via autouse fixture
- `mock_utility_client` classifier detects jailbreak words to return `OUT_OF_SCOPE`
- Mock `default_vector_size` = 1024 (matches jina-embeddings-v3)
- 109 of 110 pass
- `tests/test_agent_routes.py::TestAgentRouteStructure::test_cache_invalidate_routes` fails on `main` and is unrelated to the playground: it asserts `agent_router` owns 2 `/cache/invalidate/` routes, but `src/Routes/agent.py` defines none
- The in-page markdown renderer and syntax highlighter have no Python coverage — they are plain JS. `TestPlaygroundAsset` locks their structural invariants (escaping, URL scheme checks, no external deps); behaviour changes need a browser check
- Tests pass `reranker=None` — no Jina reranker coverage
