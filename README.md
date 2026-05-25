---
title: ConnexioRag
emoji: 🦀
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# 🚀 Connexio: Advanced Agentic RAG Framework

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Deployed on HF Spaces](https://img.shields.io/badge/Deployed-HuggingFace%20Spaces-blue.svg?style=for-the-badge)](https://huggingface.co/spaces)

**Connexio** is a state-of-the-art Agentic Retrieval-Augmented Generation (RAG) system deployed on Hugging Face Spaces, serving as the AI backbone for the Connexio educational/professional project management platform. It combines intent-driven LLM orchestration (Groq — `openai/gpt-oss-120b` + `meta-llama/llama-4-scout-17b-16e-instruct`), hybrid search via PGVector (Jina AI embeddings `jina-embeddings-v3` with HNSW + GIN trigram indexes, Reciprocal Rank Fusion), Jina multilingual reranking, and multi-persona interaction for accurate, context-aware, multilingual (English & Arabic) assistance.

---

## 🌟 Main Idea

The core vision of Connexio is to bridge the gap between raw project documentation and actionable intelligence. Unlike simple chatbots, Connexio acts as an **Agentic AI**, capable of:

- **Understanding Intent**: Detecting whether a user needs onboarding help, technical troubleshooting, or team coordination.
- **Contextual Retrieval**: Utilizing hybrid search (Vector + Trigrams) to pull the most relevant information from indexed PDFs and text files.
- **Persona-Driven Responses**: Tailoring answers for students, educators, company representatives, or early-career professionals.
- **Dynamic Tool Usage**: Interacting with live databases and external knowledge sources
  (like Wikipedia and SerpApi for live web search) when local project data isn't enough.

---

## 🏗️ High-Level Architecture

Connexio is built on a modular, service-oriented architecture designed for scalability and observability, featuring an advanced agentic workflow with intent detection and corrective RAG capabilities.

```mermaid
graph TD
    User([User/Client]) <--> Nginx[Nginx Reverse Proxy]
    Nginx <--> API[FastAPI Server]

    subgraph "Logic & Orchestration"
        API <--> Controller[NLP Controller]
        Controller <--> Workflow[Intent Detection & Workflow Manager]
        Controller <--> Tools[Tool Manager]

        subgraph "Workflow Nodes[Specialized Agents]"
            ONB[ONBOARDING]
            TEAM[TEAM_FORMATION]
            PHASE[PHASE_TRANSITION]
            BLOCK[BLOCKER]
            MILE[MILESTONE_WARNING]
            GEN[GENERAL]
            OUT[OUT_OF_SCOPE]
        end
    end

    subgraph "AI Services"
        Controller <--> LLM[LLM Provider Factory]
        LLM --- Groq[Groq / GPT-OSS 120B + Llama 4 Scout 17B]
        LLM --- OpenAI[OpenAI / Compatible API]
        LLM --- Jina[Jina AI / Embeddings v3 + Reranker]
    end

    subgraph "Knowledge Sources"
        Tools --> SQL[PostgreSQL Database]
        Tools --> Vector[Vector Database (PGVector)]
        Tools --> Wiki[Wikipedia API]
        Tools --> Google[Google Search / SerpAPI]
        Tools --> Github[GitHub API]
        Tools --> ArXiv[ArXiv API]
        Tools --> StackOverflow[StackOverflow API]
        Tools --> MasarX[MasarX Agent - Shared DB]
        Tools --> Backend[Node.js Backend API]
    end

    subgraph "Asynchronous Processing"
        API --> Broker[RabbitMQ / Redis]
        Broker --> Worker[Celery Workers - file_processing, data_indexing, default]
        Worker <--> FS[Local Assets / PDF / DOCX / MD]
        Worker <--> PGVector[(PostgreSQL + pgvector)]
        Worker --- Beat[Celery Beat - 24h cleanup]
    end

    subgraph "Observability"
        API --- Prometheus[Prometheus - /metrics]
        Prometheus --- Grafana[Grafana]
        Worker --- Flower[Flower Dashboard]
        API --- Sentry[Sentry Error Tracking]
        API --- OpenTelemetry[OpenTelemetry]
    end
```

---

## 🔗 Connexio Ecosystem Integration

Connexio RAG is part of a **3-service architecture** that works together:

```
Browser / Frontend
         │
         ▼
Node.js Backend  ←─── connexio.icu (Hostinger, MySQL)
         │
         ├── X-API-Key ───────► Connexios RAG  (HF Spaces, this repo)
         │   POST /api/v1/data/upload-and-process/{pid}
         │   POST /api/v1/nlp/agent/chat/{pid}
         │   GET  /api/v1/nlp/agent/chat/stream/{pid}
         │   POST /api/v1/projects/sync
         │
         └── Service JWT ─────► MasarX Agent  (HF Spaces)
             POST /api/v1/masarx/webhook/event/{type}/{pid}
             POST /api/v1/masarx/agent/{intent}/{pid}
```

**Shared PostgreSQL Database (Neon.tech):**

- **Connexio RAG owns**: `projects`, `assets`, `chunks`, `rag_chat_sessions`, `collection_{size}_{pid}`
- **MasarX Agent owns**: `masarx_notifications`, `masarx_pending_plans`, `user`, `task`
- **MasarX reads**: `projects`, `chunks` (read-only)

**Service-to-Service Auth:**

- Backend → RAG: `X-API-Key` header (`CONNEXIO_INTERNAL_API_KEY`)
- RAG → Backend: Service JWT generated by `BackendApiClient._make_service_token()`
- Backend → MasarX: Short-lived JWT (`JWT_SECRET`, 5-min expiry)

### Backend Client

The RAG communicates with the Node.js backend via `BackendApiClient` (`src/utils/backend_client.py`):

- Fetches user profiles, project details, members, and tasks via REST
- Uses in-memory caching (5-min TTL) to avoid hammering the backend
- Authenticates with short-lived service JWTs signed with `JWT_SECRET`

---

## 🛠️ Technology Stack

Connexio leverages a curated selection of premium technologies to ensure performance and reliability:

| Category              | Technology                                                                                                                              | Role                                                                |
| :-------------------- | :-------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------ |
| **Framework**         | [FastAPI](https://fastapi.tiangolo.com/)                                                                                                | High-performance async API development.                             |
| **Reverse Proxy**     | [Nginx](https://nginx.org/)                                                                                                             | Reverse proxy and load balancer for Docker stack.                   |
| **AI Orchestration**  | [LangChain](https://www.langchain.com/)                                                                                                 | Document loading, splitting, and tool management.                   |
| **Vector DB**         | [pgvector](https://github.com/pgvector/pgvector), [Qdrant](https://qdrant.tech/)                                                        | Semantic search via PostgreSQL or standalone Qdrant (switchable).   |
| **Relational DB**     | [PostgreSQL](https://www.postgresql.org/) (Neon.tech)                                                                                   | Project metadata, session management, and chat history.             |
| **Task Queue**        | [Celery](https://docs.celeryq.dev/)                                                                                                     | Asynchronous indexing and document processing.                      |
| **Message Broker**    | [RabbitMQ](https://www.rabbitmq.com/)                                                                                                   | Handling background task distributions.                             |
| **Cache / Backend**   | [Redis](https://redis.io/)                                                                                                              | Celery result backend and in-memory caching.                        |
| **Database Drivers**  | [SQLAlchemy](https://www.sqlalchemy.org/), [asyncpg](https://github.com/MagicStack/asyncpg), [alembic](https://alembic.sqlalchemy.org/) | ORM, async PostgreSQL driver, and migration tooling.                |
| **LLM Providers**     | [Groq](https://groq.com/) (GPT-OSS 120B, Llama 4 Scout 17B), [OpenAI](https://openai.com/) (compatible), [Cohere](https://cohere.com/)                                                                          | Generation (120B), utility/classification (17B), fallback generation.        |
| **Embedding**         | [Jina AI](https://jina.ai/) `jina-embeddings-v3` via OpenAI-compatible API (1024 dims)                                                                                                                     | Production embedding model for semantic search with `retrieval.query`/`retrieval.passage` task tagging.                     |
| **Reranker**          | [Jina AI](https://jina.ai/) `jina-reranker-v2-base-multilingual`, CoHere `rerank-multilingual-v3.0`                                                                                                           | Multilingual reranking of retrieved documents.                    |
| **Document Processing**| [PyMuPDF](https://pymupdf.readthedocs.io/) (fitz), [docx2txt](https://github.com/ankushshah89/python-docx2txt)                                                                                         | PDF and DOCX text extraction and parsing.                            |
| **NLP**               | [NLTK](https://www.nltk.org/)                                                                                                           | Natural language processing utilities.                              |
| **External APIs**     | Wikipedia API, [Google Search](https://serpapi.com/) (SerpApi), [GitHub API](https://docs.github.com/en/rest), [ArXiv](https://arxiv.org/), [StackOverflow](https://stackexchange.com/)                  | External knowledge sources for Corrective RAG.                      |
| **Rate Limiting**     | [slowapi](https://github.com/laurentS/slowapi)                                                                                          | Per-IP rate limiting (30 req/min chat, 10 req/min cache).            |
| **Token Management**  | [tiktoken](https://github.com/openai/tiktoken)                                                                                          | Token counting and budget enforcement.                              |
| **Error Tracking**    | [Sentry](https://sentry.io/)                                                                                                            | Production error monitoring and tracing.                            |
| **Observability**     | [OpenTelemetry](https://opentelemetry.io/)                                                                                               | Optional auto-instrumentation for FastAPI + logging.                |
| **Monitoring**        | [Prometheus](https://prometheus.io/) & [Grafana](https://grafana.com/)                                                                  | Real-time HTTP metrics (request count, latency, rate limits).       |
| **Worker Monitoring** | [Flower](https://github.com/mher/flower)                                                                                                | Celery worker monitoring and management.                            |
| **Auth**              | [PyJWT](https://pyjwt.readthedocs.io/)                                                                                                  | Service JWT generation for backend auth.                            |
| **Async I/O**         | [aiofiles](https://github.com/Tinche/aiofiles)                                                                                          | Async file operations for uploads and processing.                   |

---

## ⚙️ Infrastructure & Orchestration

### 🧩 Service Breakdown

- **FastAPI (Web Layer)**: Serves as the gateway for all client interactions. It manages dependency injection for database sessions, AI providers, and vector stores.
- **Celery Workers (Processing Layer)**: Handles heavy-lifting tasks. When a file is uploaded, Celery manages the extraction, chunking, and indexing into the vector databases to keep the API responsive.
- **RabbitMQ (Broker)**: The high-reliability backbone for message distribution between the API and workers.
- **PGVector (Storage Layer)**: Adds hybrid search capabilities, allowing us to combine relational queries with vector similarity within a single PostgreSQL instance (Neon.tech).
- **Prometheus & Grafana (Observability Layer)**: Every RAG request and system operation is metered, providing real-time insights into latency, throughput, and error rates.

> ⚠️ **Environment variables** are set as HF Space Repository Secrets. Never commit a `.env` file.

### 🧠 Intelligent Features

Connexio implements advanced intelligent capabilities beyond basic RAG:

- **Intent-Based Model Routing**: Response quality is gated by query intent, not project context:
  - **OUT_OF_SCOPE** — instant canned refusal, zero LLM calls
  - **GENERAL intents** (professional questions, career advice, tech topics) — utility **Llama 4 Scout 17B** model
  - **Auto-Escalate** — if utility model echoes query, refuses, or gives empty answer → auto-retries with **GPT-OSS 120B**
  - **Project intents** (blocker, milestone, onboarding, team, phase) — **GPT-OSS 120B** directly (quality needed)
  - **model_tier** param allows manual override: `"generation"` or `"utility"`

- **Intent Detection & Workflow Routing**: Every query is analyzed and routed to one of seven specialized workflow nodes:
  - ONBOARDING: Guidance for new users
  - TEAM_FORMATION: Intelligent teammate matching logic
  - PHASE_TRANSITION: Validating deliverables before project advancement
  - BLOCKER: Troubleshooting and technical problem resolution
  - MILESTONE_WARNING: Proactive reporting on deadlines and late tasks
  - GENERAL: Conversational AI grounded in project context
  - OUT_OF_SCOPE: Guardrail that rejects off-topic queries. Catches trivia, history (`"who is X"` bypasses the short-query fast-path), jailbreak attempts (`"your system prompt"`, `"ignore your instructions"`), cooking, weather, sports, and Arabic equivalents. Returns a canned response with zero LLM cost.

- **Corrective RAG (CRAG)**: Activates when internal knowledge is insufficient. For project sessions, it dynamically triggers external tools. For technical queries without project context, it still activates research tools (ArXiv, StackOverflow, GitHub) to provide real-time answers:
  - **ArXiv API** for academic papers, research, and ML/AI topics
  - **StackOverflow API** for developer Q&A, coding errors, and API usage
  - **Wikipedia & Google (SerpApi)** for live web search and general definitions
  - **GitHub API** for extracting repository issues, commits, and summaries
  - **Backend REST** for live user/project/member/task data via `BackendApiClient`

- **Multi-Source Intelligence**: Combines information from:
  - SQL Database: Real-time project metrics, user skills, and task history
  - Vector Knowledge Base: Semantic search through project documentation
  - External APIs: Wikipedia, Google, GitHub, ArXiv, StackOverflow for additional context
  - Backend REST: Live user/project/member/task data via `BackendApiClient`

- **Language Support**: Automatic detection and switching between English and Arabic prompts
- **Persona Mapping**: Adjusts tone and depth based on user role (student, educator, company representative, early-career professional)
- **Adaptive Conversational Memory**: Full token-budget window for project sessions; capped at 2 turns for projectless sessions to prevent accumulation across unrelated queries
- **Rate Limiting & Security**: 30 requests/minute per IP (agent chat), 10 req/min (cache invalidation), `max_length=5000` on query input, 429 retry with exponential backoff, cache invalidation endpoints, sanitized knowledge base (no internal infra details exposed), `CONNEXIO_INTERNAL_API_KEY` required for all endpoints (no dev bypass in production)
- **Global Knowledge Base**: 52 curated files across 8 categories (134 chunks) — answers platform, agile, dev, design, career, business, soft skills, and industry trend questions
- **Session TTL**: Stale chat sessions auto-cleaned after 30 days via Celery Beat; 24-hour cleanup of old task records
- **Internal Tracing**: Every step is logged by the TraceManager for debugging and optimization; traces saved as JSON and rendered into HTML dashboards via `generate_report.py`
- **Task Idempotency**: SHA-256 dedup of Celery tasks prevents duplicate processing; stuck task detection (time limit + 60s grace) allows safe re-execution
- **Asset Management**: Full CRUD for uploaded files — list all assets per project, delete assets with cascade cleanup (vector rows, SQL chunks, physical file)
- **Upload-and-Query**: Synchronous flow — upload file → ingest → embed → search → generate answer in a single request
- **URL Content Ingestion**: Paste a URL; the system downloads the content, detects PDF/docx/text, and extracts up to 8000 characters for context
- **MasarX Integration**: Direct PostgreSQL reads of MasarX agent task tables (`"TaskId"`, `"TaskName"`, `"PID"`, `"UID"` with quoted identifiers) for cross-agent intelligence
- **Backend Caching**: 5-minute in-memory TTL for project details and user profiles (tasks are not cached — always live)
- **Text-to-SQL Tool**: Natural language → SQL query with safety validation (SELECT-only enforced, all mutating operations blocked)
- **Matching Intelligence**: 6-factor teammate matching algorithm (Skills 35%, Availability 25%, Rating 20%, Experience 12%, Goals 5%, Domain 3%) with team gap analysis
- **Error Tracking**: Sentry integration with configurable sample rate; OpenTelemetry auto-instrumentation optional via start.sh
- **Supported File Types**: PDF, TXT, DOCX, and Markdown — sliding window chunking (800 chars default, 150 overlap)
- **Celery Beat Cleanup**: Two daily maintenance tasks — stale session cleanup (30 days) and task execution record cleanup (24 hours)
- **Hidden Metrics Endpoint**: Prometheus metrics exposed at an obfuscated path (`/TrhBVe_m5gg2002_E5VVqS`) with custom 429 handler

---

## 🚀 Getting Started

### 🐳 Docker Deployment (Recommended)

The easiest way to run Connexio is using the provided Docker Compose configuration which spins up all services (API, Workers, DBs, Monitoring):

```bash
# Clone the repository
git clone https://github.com/SallahAhmed/Connexio.git
cd Connexio

# Setup your environment
cp src/.env.example src/.env
# Edit .env file with your configuration (API keys, etc.)

# Spin up the infrastructure
docker compose -f docker/docker-compose.yml up --build -d
```

### 🐍 Local Development

If you prefer running locally:

1. **Setup Python Environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r src/requirements.txt
   ```

2. **Run FastAPI**:

   ```bash
   cd src
   uvicorn main:app --reload --port 8080
   ```

3. **Run Celery Worker**:

   ```bash
   cd src
   celery -A celery_app worker --loglevel=info
   ```

> [!NOTE]
> For local development with Ollama models, uncomment the relevant sections in your `.env` file and ensure Ollama is running locally.

### 🖥️ Dev Commands (from `src/`)

```bash
uvicorn main:app --reload --port 8080                    # API server
python -m pytest tests/ -v --tb=short                    # Run all 42 tests
python -m celery -A celery_app worker --loglevel=info     # Celery worker
python -m celery -A celery_app beat --loglevel=info       # Celery Beat scheduler
python flowerconfig.py                                    # Flower dashboard on :5556
```

### 🚀 Production Entrypoint

The `start.sh` script boots Celery worker + beat and uvicorn with 4 workers, including optional OpenTelemetry auto-instrumentation:

```bash
# Set OTEL_EXPORTER_OTLP_ENDPOINT for OpenTelemetry tracing
./start.sh
```

---

> [!TIP]
> Use the **Flower Dashboard** at `http://localhost:5556` to monitor background task execution in real-time.

## 📡 API Reference

### 🔹 Agent Endpoints

| Endpoint                                     | Method | Rate Limit | Description                                                                                                                                                                                          |
| :------------------------------------------- | :----- | :--------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/api/v1/nlp/agent/chat/{project_id}`        | `POST` | 30/min     | Engage in a persona-based conversation with the AI agent using project context. Supports intent detection, workflow routing, and Corrective RAG (CRAG) for external knowledge retrieval when needed. Body: `query`, `user_id`, `persona`, `session_id`, `limit`, `model_tier`, `language`. |
| `/api/v1/nlp/agent/chat/stream/{project_id}` | `GET`  | 30/min     | Stream AI responses using Server-Sent Events (SSE) for real-time interaction. Query params: `query`, `user_id`, `persona`, `session_id`, `limit`, `model_tier`, `language`. Returns meta event → token chunks → `[DONE]`. |
| `/api/v1/nlp/agent/cache/invalidate/{project_id}` | `POST` | 10/min | Invalidate in-memory cache for a project's backend data (project, members, tasks). |
| `/api/v1/nlp/agent/cache/invalidate/user/{user_id}` | `POST` | 10/min | Invalidate cached user profile from the main backend. |

### 🔹 Base Endpoints

| Endpoint           | Method | Auth   | Description                                                     |
| :----------------- | :----- | :----- | :-------------------------------------------------------------- |
| `/api/v1/`         | `GET`  | None   | Retrieve basic application metadata including name and version. |
| `/api/v1/health`   | `GET`  | None   | Health check returning status, service name, and version.       |

### 🔹 Data Endpoints

| Endpoint                                         | Method | Description                                                                                              |
| :----------------------------------------------- | :----- | :------------------------------------------------------------------------------------------------------- |
| `/api/v1/data/upload/{project_id}`               | `POST` | Upload a file (PDF, TXT, DOCX, or MD) to the project assets directory and record it in the database.     |
| `/api/v1/data/upload-and-process/{project_id}`   | `POST` | Upload and immediately process + index a file (used by backend forwarding, fire-and-forget).             |
| `/api/v1/data/upload-and-query/{project_id}`     | `POST` | Upload file + index + answer a question about it synchronously in a single request.                      |
| `/api/v1/data/process/{project_id}`              | `POST` | Trigger the background Celery processing task to chunk and clean uploaded files.                         |
| `/api/v1/data/process-and-push/{project_id}`     | `POST` | Execute a chained Celery workflow that processes files and immediately indexes them into the vector DB.  |
| `/api/v1/data/assets/{project_id}`               | `GET`  | List all uploaded assets for a project.                                                                  |
| `/api/v1/data/assets/{asset_id}`                 | `DELETE`| Full asset deletion: PGVector rows, SQL chunks, physical file, and asset record cascade.               |

### 🔹 Project Sync Endpoints

| Endpoint                | Method | Description                                                           |
| :---------------------- | :----- | :-------------------------------------------------------------------- |
| `/api/v1/projects/sync` | `POST` | Sync project data from the Node.js backend into the RAG's PostgreSQL. |

### 🔹 NLP Endpoints

| Endpoint                                | Method | Description                                                                        |
| :-------------------------------------- | :----- | :--------------------------------------------------------------------------------- |
| `/api/v1/nlp/index/push/{project_id}`   | `POST` | Manually trigger Celery indexing of existing project chunks into the vector DB.     |
| `/api/v1/nlp/index/info/{project_id}`   | `GET`  | Retrieve vector DB collection info (record count, table metadata) for a project.   |
| `/api/v1/nlp/index/search/{project_id}` | `POST` | Perform a semantic search query against the project's indexed data.                |

### 🔹 Internal Metrics

| Endpoint                              | Method | Auth   | Description                                        |
| :------------------------------------ | :----- | :----- | :------------------------------------------------- |
| `/TrhBVe_m5gg2002_E5VVqS`            | `GET`  | None   | Prometheus metrics endpoint (obfuscated path).     |

---

## 🔍 The Brain: RAG Pipeline & Logic

Connexio doesn't just search; it understands and reasons through an advanced agentic workflow. The pipeline is divided into three critical stages:

### 1. Document Ingestion & Hybrid Indexing

When documents are uploaded (PDF, TXT, DOCX, MD):

- **Smart Chunking**: Text is split into manageable chunks using sliding window chunking (default 800 chars, 150 overlap) via `RecursiveCharacterTextSplitter` to preserve context.
- **Multimodal Embedding**: Chunks are transformed into vectors using Jina AI's `jina-embeddings-v3` (1024-dimensional) via OpenAI-compatible API, with task-specific tagging (`retrieval.query` / `retrieval.passage`).
- **Hybrid Storage**: Chunks stored in per-project PGVector tables (`collection_{size}_{pid}`) with HNSW index on vectors (ANN search) AND GIN trigram index on text (Arabic-friendly keyword search). Raw chunks also stored in PostgreSQL `chunks` table for metadata queries.

### 2. Intelligent Retrieval (Hybrid Search + RRF + Reranking)

Connexio uses **Reciprocal Rank Fusion (RRF)** to combine results from multiple sources:

- **Vector Search (ANN)**: HNSW-indexed semantic search finds documents with similar meanings.
- **Full-Text Search (Keyword)**: GIN trigram-indexed search finds exact term matches, especially useful for technical names and Arabic text.
- **RRF Algorithm**:
  $$Score = \sum_{d \in R} \frac{1}{k + rank(d)}$$
  _Where $k=60$ balances the influence of different ranking sources._
- **Relevance Grading**: Retrieved documents are batch-graded as `RELEVANT`/`AMBIGUOUS`/`IRRELEVANT` by the utility LLM (Llama 4 Scout 17B) to filter low-quality results.
- **Multilingual Reranking** (optional, requires `JINA_API_KEY`): Jina's `jina-reranker-v2-base-multilingual` re-ranks results by relevance score for improved precision.

### 3. Agentic Workflow

The `NLPController` manages the conversation flow through a sophisticated agentic loop:

- **Intent-Based Model Routing**: The pipeline selects model based on query intent:
  - **OUT_OF_SCOPE** — canned refusal, 0 LLM calls
  - **Project intents** (blocker, milestone, onboarding, team, phase) — **GPT-OSS 120B** directly
  - **GENERAL intents** — **Llama 4 Scout 17B** with **auto-escalate** to 120B if answer echoes/refuses

- **Intent Detection & Workflow Routing**: Every query is analyzed (OOS keywords first → project keywords → GENERAL → fast path → LLM) and routed to one of seven specialized workflow nodes:
  - **ONBOARDING**: Guidance for new users getting started with the project
  - **TEAM_FORMATION**: Intelligent teammate matching logic based on skills and availability
  - **PHASE_TRANSITION**: Validating deliverables before project advancement
  - **BLOCKER**: Troubleshooting and technical problem resolution
  - **MILESTONE_WARNING**: Proactive reporting on deadlines and late tasks
  - **GENERAL**: Conversational AI grounded in project context
  - **OUT_OF_SCOPE**: Guardrail that rejects off-topic queries. Short queries containing `"who is"`, `"who was"` bypass the 50-character fast-path and go to the LLM classifier. Jailbreak attempts (`"your system prompt"`, `"ignore your instructions"`, `"bypass your rules"`) are caught by keyword matching before the LLM is ever called.

- **Language Detection**: Automatically switches between English and Arabic prompts based on user input.
- **Adaptive Conversational Memory**: Full token-budget window for project sessions. Projectless sessions cap history at the last 2 turns (4 messages) to prevent token accumulation across unrelated queries.
- **Persona Mapping**: Adjusts the tone, depth, and terminology of the answer based on the user's role (student, educator, company representative, or early-career professional).
- **Corrective RAG (CRAG)**: Activates when `project_id` is set and internal knowledge is insufficient. For technical queries without project context, CRAG still activates research tools (ArXiv, StackOverflow, GitHub) to provide real-time answers:
  - **Wikipedia & Google (SerpApi)** for live web search, general definitions, and current information
  - **GitHub API** for extracting repository issues, commits, and code summaries
  - **ArXiv API** for academic papers, research, and ML/AI topics
  - **StackOverflow API** for developer Q&A, coding errors, and API usage
  - **Backend REST** for live user/project/member/task data via `BackendApiClient`
- **Internal Tracing**: Every step is logged by the `TraceManager`, allowing developers to visualize the AI's "thought process", latency, and decision-making for debugging and optimization.

---

## 🗺️ Key Files Reference

| File                                     | Role                                                 |
| :--------------------------------------- | :--------------------------------------------------- |
| `src/main.py`                            | FastAPI entry — startup, lifespan, middleware, health |
| `src/celery_app.py`                      | Celery config, beat schedule, task routing           |
| `src/flowerconfig.py`                    | Flower monitoring dashboard config                   |
| `src/helpers/config.py`                  | `Settings` Pydantic model — all env vars             |
| `src/controllers/NLPController.py`       | Chat, streaming, context prep, CRAG, model routing   |
| `src/controllers/WorkflowController.py`  | Intent detection: jailbreak/OOS/project/fuzzy/LLM    |
| `src/controllers/DataController.py`      | File upload validation and sanitization              |
| `src/controllers/ProcessController.py`   | Document loading (PDF/DOCX/TXT/MD), chunking         |
| `src/controllers/ProjectController.py`   | Project directory management on disk                 |
| `src/controllers/helpers/ToolManager.py` | Wiki, Google, GitHub, ArXiv, StackOverflow, SQL, KB, MasarX |
| `src/controllers/helpers/TraceManager.py`| Step tracer for RAG pipeline observability           |
| `src/utils/backend_client.py`            | REST client to Node.js backend (JWT auth + 5min cache)|
| `src/utils/masarx_client.py`             | Direct PostgreSQL reads of MasarX task tables        |
| `src/utils/security.py`                  | `verify_api_key()` FastAPI dependency                |
| `src/utils/metrics.py`                   | Prometheus middleware + obfuscated metrics endpoint  |
| `src/utils/idempotency_manager.py`       | Celery task dedup (SHA-256) + stuck detection        |
| `src/utils/generate_report.py`           | HTML report generator from trace JSON files          |
| `src/stores/llm/providers/`              | OpenAIProvider, GroqProvider, CoHereProvider         |
| `src/stores/vectordb/providers/`         | PGVectorProvider, QdrantDBProvider, JinaReranker     |
| `src/tasks/`                             | Celery tasks: file_processing, data_indexing, process_workflow, maintenance |
| `src/Routes/`                            | Endpoints: base, agent, data, nlp, projects          |
| `src/models/db_schemas/connexio/schemas/`| ORM: project, data_chunk, asset, chat_session, celery_task_execution, project_id_map |
| `start.sh`                               | Entrypoint: Celery worker+beat + uvicorn (+ optional OpenTelemetry) |
| `Dockerfile`                             | Production dockerfile for HF Spaces (python:3.11-slim)|
| `Requirements.txt`                       | All dependencies (63 packages)                       |

---

<!-- > [!IMPORTANT]
> **AI Readiness**: This file is optimized for consumption by Large Language Models (LLMs). If you are an AI model reading this, you now have a complete map of the project's architecture, tools, and API surface. -->

### 🤖 Jules Auto-Evaluator

This repository is equipped with an automated evaluation script that runs every 8 hours via GitHub Actions.
It simulates various user queries (students, early-career professionals) against the deployed RAG endpoint and uses the **Jules AI Agent** to grade the responses.
If the quality of the answers drops below a 9/10, Jules will automatically clone the repository, find the issue, fix the code/prompt, run tests, and open a PR!

To set this up in your own fork/environment, ensure the following secrets are added to your GitHub repository:
- `JULES_API_KEY`: Your Jules agent API key.
- `RAG_API_URL`: The URL of your deployed Connexio API (e.g., `https://connexio.icu`).
- `CONNEXIO_INTERNAL_API_KEY`: The API key matching your RAG deployment for authentication.
