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

**Connexio** is a state-of-the-art Retrieval-Augmented Generation (RAG) system designed to serve as an intelligent backbone for educational and professional project management. It combines cutting-edge AI orchestration, hybrid search capabilities, and multi-persona interaction to provide accurate, context-aware, and multilingual (English & Arabic) assistance.

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
        LLM --- Groq[Groq / Llama 3]
        LLM --- OpenAI[OpenAI / GPT-4]
        LLM --- Cohere[Cohere / Embeddings]
    end

    subgraph "Knowledge Sources"
        Tools --> SQL[PostgreSQL Database]
        Tools --> Vector[Vector Database (Qdrant/PGVector)]
        Tools --> Wiki[Wikipedia API]
        Tools --> Google[Google Search]
        Tools --> Github[GitHub API]
        Tools --> Python[Python Interpreter]
    end

    subgraph "Asynchronous Processing"
        API --> Broker[RabbitMQ]
        Broker --> Worker[Celery Workers]
        Worker <--> FS[Local Assets / PDF]
        Worker <--> Qdrant[(Qdrant Vector DB)]
        Worker <--> PGVector[(PostgreSQL + pgvector)]
    end

    subgraph "Observability"
        API --- Prometheus[Prometheus]
        Prometheus --- Grafana[Grafana]
        Worker --- Flower[Flower Dashboard]
    end
```

---

## 🛠️ Technology Stack

Connexio leverages a curated selection of premium technologies to ensure performance and reliability:

| Category              | Technology                                                                                                                              | Role                                                                |
| :-------------------- | :-------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------ |
| **Framework**         | [FastAPI](https://fastapi.tiangolo.com/)                                                                                                | High-performance async API development.                             |
| **AI Orchestration**  | [LangChain](https://www.langchain.com/)                                                                                                 | Document loading, splitting, and tool management.                   |
| **Vector DB**         | [Qdrant](https://qdrant.tech/) & [pgvector](https://github.com/pgvector/pgvector)                                                       | Semantic search and long-term memory.                               |
| **Relational DB**     | [PostgreSQL](https://www.postgresql.org/)                                                                                               | Project metadata, session management, and chat history.             |
| **Task Queue**        | [Celery](https://docs.celeryq.dev/)                                                                                                     | Asynchronous indexing and document processing.                      |
| **Message Broker**    | [RabbitMQ](https://www.rabbitmq.com/)                                                                                                   | Handling background task distributions.                             |
| **Database Drivers**  | [SQLAlchemy](https://www.sqlalchemy.org/), [asyncpg](https://github.com/MagicStack/asyncpg), [alembic](https://alembic.sqlalchemy.org/) | ORM, async PostgreSQL driver, and migration tooling.                |
| **LLM Providers**     | Groq (Llama 3.3 70B, Llama 3.1 8B), OpenAI, Cohere                                                                                      | Multimodal intelligence, tool selection, and intent classification. |
| **External APIs**     | Wikipedia API, [Google Search](https://serpapi.com/) (SerpApi), [GitHub API](https://docs.github.com/en/rest)                           | External knowledge sources for Corrective RAG.                      |
| **Monitoring**        | Prometheus & Grafana                                                                                                                    | Real-time performance metrics and dashboards.                       |
| **Worker Monitoring** | [Flower](https://github.com/mher/flower)                                                                                                | Celery worker monitoring and management.                            |

---

## ⚙️ Infrastructure & Orchestration

### 🧩 Service Breakdown

- **FastAPI (Web Layer)**: Serves as the gateway for all client interactions. It manages dependency injection for database sessions, AI providers, and vector stores.
- **Celery Workers (Processing Layer)**: Handles heavy-lifting tasks. When a file is uploaded, Celery manages the extraction, chunking, and indexing into the vector databases to keep the API responsive.
- **RabbitMQ (Broker)**: The high-reliability backbone for message distribution between the API and workers.
- **Qdrant & PGVector (Storage Layer)**:
  - **Qdrant** provides extremely fast semantic search for high-dimensional vectors.
  - **PGVector** adds hybrid search capabilities, allowing us to combine relational queries with vector similarity within a single PostgreSQL instance.
- **Prometheus & Grafana (Observability Layer)**: Every RAG request and system operation is metered, providing real-time insights into latency, throughput, and error rates.

### 🔐 Environment Configuration

Connexio is highly configurable via environment variables. Key sections in your `.env` file include:

```ini
# --- Application Settings ---
APP_NAME="Connexio"
APP_VERSION="0.1"
FILE_ALLOWED_TYPES=["application/pdf","text/plain"]
FILE_MAX_SIZE=10
FILE_DEFAULT_CHUNK_SIZE=1024
PRIMARY_LANG="en"
DEFAULT_LANG="en"
INPUT_DEFAULT_MAX_CHARACTERS=500

# --- Database Configuration ---
POSTGRES_USERNAME="your_postgres_username"
POSTGRES_PASSWORD="your_postgres_password"
POSTGRES_HOST="your_postgres_host"
POSTGRES_PORT=your_postgres_port
POSTGRES_MAIN_DATABASE="your_postgres_database"

# --- LLM & AI Configuration ---
# ========================= LLM Config =========================
# GENERATION_BACKEND="OPENAI"
# OPENAI_API_KEY="your_openrouter_api_key"
# OPENAI_GENERATION_API_URL="https://openrouter.ai/api/v1"
GENERATION_BACKEND="GROQ" # Options: GROQ, OPENAI, COHERE
EMBEDDING_BACKEND="OPENAI" # Options: OPENAI, COHERE
OPENAI_API_KEY="your_openai_api_key"
OPENAI_GENERATION_API_URL="http://your_ollama_ip:11434/v1" # Use http://host.docker.internal:11434/v1 in Docker
OPENAI_EMBEDDING_API_URL="http://your_ollama_ip:11434/v1"
COHERE_API_KEY="your_cohere_api_key"
GROQ_API_KEY="your_groq_api_key"
GROQ_API_URL="https://api.groq.com/openai/v1"
SERPAPI_API_KEY="your_serpapi_api_key"
GITHUB_TOKEN="your_github_token"

# ========================= Model IDs =========================
GENERATION_MODEL_ID_LITERAL=["qwen:4b","gemma4:e2b","llama-3.3-70b-versatile","openai/gpt-oss-120b","inclusionai/ling-2.6-1t:free", "qwen/qwen-3-coder-480b:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free","openrouter/free"]
GENERATION_MODEL_ID="your_generation_model_id"
UTILITY_MODEL_ID="your_utility_model_id"
EMBEDDING_MODEL_ID="bge-m3"
EMBEDDING_MODEL_SIZE=1024

# ========================= Generation Defaults =========================
INPUT_DEFAULT_MAX_CHARACTERS=500
GENERATION_DEFAULT_MAX_TOKENS=1024
GENERATION_DEFAULT_TEMPERATURE=0.1
TOTAL_CONTEXT_CHAR_BUDGET=12000

# --- Vector DB Configuration ---
# ========================= Vector DB Config =========================
VECTOR_DB_BACKEND_LITERAL=["QDRANT", "PGVECTOR"]
VECTOR_DB_BACKEND="PGVECTOR" # Options: QDRANT, PGVECTOR
VECTOR_DB_PATH="qdrant_db"
VECTOR_DB_DISTANCE_METHOD="cosine"
VECTOR_DB_PGVEC_INDEX_THRESHOLD=400

# --- Celery & Task Queue Configuration ---
# ========================= Celery Task Queue Config =========================
CELERY_BROKER_URL="amqp://your_user:your_pass@your_host:5672/your_vhost"
CELERY_RESULT_BACKEND="redis://:your_pass@your_host:6379/0"

CELERY_TASK_SERIALIZER="json"
CELERY_TASK_TIME_LIMIT=600
CELERY_TASK_ACKS_LATE=false
CELERY_WORKER_CONCURRENCY=2
CELERY_FLOWER_PASSWORD="your_flower_password"

# --- Deprecated or Commented Out ---
# MONGODB_URL="mongodb://admin:admin@localhost:27007"
# MONGODB_DATABASE="Anything"
# REDIS_HOST="localhost"
# REDIS_PORT=6379
# REDIS_DB=0
```

### 🧠 Intelligent Features

Connexio implements advanced intelligent capabilities beyond basic RAG:

- **Intent Detection & Workflow Routing**: Every query is analyzed and routed to one of seven specialized workflow nodes:
  - ONBOARDING: Guidance for new users
  - TEAM_FORMATION: Intelligent teammate matching logic
  - PHASE_TRANSITION: Validating deliverables before project advancement
  - BLOCKER: Troubleshooting and technical problem resolution
  - MILESTONE_WARNING: Proactive reporting on deadlines and late tasks
  - GENERAL: Conversational AI grounded in project context
  - OUT_OF_SCOPE: Guardrail that rejects off-topic queries (trivia, history, etc.)

- **Corrective RAG (CRAG)**: When internal knowledge is insufficient, the system dynamically extracts context and triggers external tools:
  - Wikipedia & Google (SerpApi) for live web search and general definitions
  - GitHub API for extracting repository issues, commits, and summaries
  - Python Interpreter for executing logic, math, and data processing

- **Multi-Source Intelligence**: Combines information from:
  - SQL Database: Real-time project metrics, user skills, and task history
  - Vector Knowledge Base: Semantic search through project documentation
  - External APIs: Wikipedia, Google, GitHub for additional context

- **Language Support**: Automatic detection and switching between English and Arabic prompts
- **Persona Mapping**: Adjusts tone and depth based on user role (student, educator, company representative, early-career professional)
- **Deep Conversational Memory**: Retains conversation history (configurable, currently 12,000 characters) for context continuity
- **Internal Tracing**: Every step is logged by the TraceManager for debugging and optimization

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

---

> [!TIP]
> Use the **Flower Dashboard** at `http://localhost:5556` to monitor background task execution in real-time.

## 📡 API Reference

### 🔹 Agent Endpoints

| Endpoint                                     | Method | Description                                                                                                                                                                                          |
| :------------------------------------------- | :----- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/api/v1/nlp/agent/chat/{project_id}`        | `POST` | Engage in a persona-based conversation with the AI agent using project context. Supports intent detection, workflow routing, and Corrective RAG (CRAG) for external knowledge retrieval when needed. |
| `/api/v1/nlp/agent/chat/stream/{project_id}` | `GET`  | Stream AI responses using Server-Sent Events (SSE) for real-time interaction. Includes metadata about detected intent, language, sources used, and session information in the initial stream event.  |

### 🔹 Base Endpoints

| Endpoint   | Method | Description                                                     |
| :--------- | :----- | :-------------------------------------------------------------- |
| `/api/v1/` | `GET`  | Retrieve basic application metadata including name and version. |

### 🔹 Data Endpoints

| Endpoint                                     | Method | Description                                                                                            |
| :------------------------------------------- | :----- | :----------------------------------------------------------------------------------------------------- |
| `/api/v1/data/upload/{project_id}`           | `POST` | Upload a file (PDF or TXT) to the project assets directory and record it in the database.              |
| `/api/v1/data/process/{project_id}`          | `POST` | Trigger the background processing task to chunk and clean uploaded files.                              |
| `/api/v1/data/process-and-push/{project_id}` | `POST` | Execute a chained workflow that processes files and immediately indexes them into the vector database. |

### 🔹 Nlp Endpoints

| Endpoint                                | Method | Description                                                                        |
| :-------------------------------------- | :----- | :--------------------------------------------------------------------------------- |
| `/api/v1/nlp/index/push/{project_id}`   | `POST` | Manually trigger the indexing of existing project chunks into the vector database. |
| `/api/v1/nlp/index/info/{project_id}`   | `GET`  | Retrieve information about the vector database collection for a specific project.  |
| `/api/v1/nlp/index/search/{project_id}` | `POST` | Perform a semantic search query against the project's indexed data.                |

---

## 🔍 The Brain: RAG Pipeline & Logic

Connexio doesn't just search; it understands and reasons through an advanced agentic workflow. The pipeline is divided into three critical stages:

### 1. Document Ingestion & Hybrid Indexing

When documents are uploaded:

- **Smart Chunking**: Text is split into manageable chunks using `RecursiveCharacterTextSplitter` with configurable overlap to preserve context.
- **Multimodal Embedding**: Chunks are transformed into vectors using the configured embedding model (currently 1024-dimensional with bge-m3).
- **Hybrid Storage**: Chunks are stored in the vector database (Qdrant or PGVector) for semantic search and in PostgreSQL for metadata. This enables both semantic and keyword-based search capabilities.

### 2. Intelligent Retrieval (Hybrid Search + RRF)

Connexio uses **Reciprocal Rank Fusion (RRF)** to combine results from multiple sources:

- **Vector Search**: Finds documents with similar meanings.
- **Full-Text Search**: Finds exact term matches, especially useful for technical names.
- **RRF Algorithm**:
  $$Score = \sum_{d \in R} \frac{1}{k + rank(d)}$$
  _Where $k=60$ balances the influence of different ranking sources._

### 3. Agentic Workflow

The `NLPController` manages the conversation flow through a sophisticated agentic loop:

- **Intent Detection & Workflow Routing**: Every query is analyzed and routed to one of seven specialized workflow nodes:
  - **ONBOARDING**: Guidance for new users getting started with the project
  - **TEAM_FORMATION**: Intelligent teammate matching logic based on skills and availability
  - **PHASE_TRANSITION**: Validating deliverables before project advancement
  - **BLOCKER**: Troubleshooting and technical problem resolution
  - **MILESTONE_WARNING**: Proactive reporting on deadlines and late tasks
  - **GENERAL**: Conversational AI grounded in project context
  - **OUT_OF_SCOPE**: Guardrail that automatically rejects off-topic queries (trivia, history, etc.) to maintain focus on professional/project topics

- **Language Detection**: Automatically switches between English and Arabic prompts based on user input.
- **Deep Conversational Memory**: Retains conversation history (currently limited to 12,000 characters) for context continuity, enabling deep, continuous, multi-turn technical discussions.
- **Persona Mapping**: Adjusts the tone, depth, and terminology of the answer based on the user's role (student, educator, company representative, or early-career professional).
- **Corrective RAG (CRAG)**: When the internal knowledge base is insufficient or irrelevant, the system dynamically extracts context and triggers external tools:
  - **Wikipedia & Google (SerpApi)** for live web search, general definitions, and current information
  - **GitHub API** for extracting repository issues, commits, and code summaries
  - **Python Interpreter** for executing logic, mathematical calculations, and data processing tasks
- **Internal Tracing**: Every step is logged by the `TraceManager`, allowing developers to visualize the AI's "thought process", latency, and decision-making for debugging and optimization.

---

<!-- > [!IMPORTANT]
> **AI Readiness**: This file is optimized for consumption by Large Language Models (LLMs). If you are an AI model reading this, you now have a complete map of the project's architecture, tools, and API surface. -->
