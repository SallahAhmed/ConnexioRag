# Connexio — Full Project Description (AI Context)

## Project Overview

**Connexio** is an **Agentic RAG (Retrieval-Augmented Generation)** platform designed as an intelligent AI advisor for a project collaboration ecosystem. It bridges the gap between document-based knowledge and structured application data to support students and professionals in building software projects.

The platform uses a multi-source retrieval strategy to provide context-aware answers, project management advice, and automated documentation generation.

---

## 1. Core Personas & Workflow

The system detects the user's intent and maps it to specific **Workflow Nodes** and **Personas** to tailor the response.

### Personas

- **Student**: Starting new projects, learning fundamentals.
- **Early Career**: Focused on technical execution and professional deliverables.
- **Educator**: Monitoring progress, providing mentorship.
- **Company**: Identifying talent and project outcomes.

### Workflow Nodes (State Detection)

- `ONBOARDING`: First steps and platform navigation.
- `TEAM_FORMATION`: Matching skills and finding teammates.
- `PHASE_TRANSITION`: Moving from ideation to development or launch.
- `BLOCKER`: Troubleshooting technical or team issues.
- `MILESTONE_WARNING`: Risk management for deadlines and progress.
- `GENERAL`: Conversational fallback and general queries.

---

## 2. Technical Architecture

The app follows a microservices architecture coordinated by a FastAPI gateway.

### High-Level Flow

1. **User Query** → FastAPI Gateway.
2. **WorkflowController** detects Language (EN/AR) and Node (Intent).
3. **NLPController** manages the RAG pipeline:
   - **Query Decomposition**: Breaks complex queries into sub-tasks.
   - **ToolManager**: Orchestrates multi-source retrieval.
   - **Context Budgeting**: Strictly truncates history and context to fit LLM limits.
4. **LLM Generation**: Uses Ollama (Local) or OpenAI/Cohere (Cloud).
5. **Session Persistence**: Stores chat history and workflow state in PostgreSQL.

### Multi-Source Retrieval (ToolManager)

- **Internal Knowledge Base**: Vector search (PGVector/Qdrant) over uploaded project documents.
- **SQL Database**: Text-to-SQL queries against the **Main Application Database** (users, projects, tasks), which is logically separated from the RAG database.
- **Wikipedia**: CRAG (Corrective RAG) fallback when internal documents are irrelevant.
- **Specialized Tools**: Project risk assessment, portfolio generation, and team gap analysis.

---

## 3. Tech Stack & Infrastructure

- **Backend**: Python 3.x, FastAPI.
- **Database**:
  - **PostgreSQL + PGVector**: Main relational data and vector storage.
  - **Redis**: Result backend for Celery.
- **Task Queue**: Celery with RabbitMQ (Broker).
- **AI/LLM**:
  - **Generation**: Ollama (gemma2), OpenAI (GPT-3.5/4).
  - **Embeddings**: `nomic-embed-text` (Ollama).
- **DevOps**: Docker Compose, Nginx (Reverse Proxy), Prometheus/Grafana (Monitoring).

---

## 4. Key Implementation Details (For AI Context)

- **Context Budgeting**: The system uses a sliding window for chat history and strict character limits (e.g., 15k total budget) to avoid token overflow.
- **Asynchronous Execution**: All LLM calls and tool executions (SQL, Wiki) are non-blocking using `asyncio` and `to_thread`.
- **Retrieval Strategy**: Uses basic vector similarity scores for grounding; advanced reranking is currently disabled.
- **Manual Vector Push**: To maintain data integrity, the user has manual control over when processed document chunks are pushed to the Vector DB (via `/index/push`).
- **Configurable Logic**: Matching weights for the "6-factor algorithm" and other heuristic thresholds are configurable via the `.env` file.
- **Language Support**: Native support for English and Arabic, including persona translation and localized prompts.

---

## 5. API Map

- `/api/v1/data/`: File upload and chunking logic.
- `/api/v1/nlp/index/`: Vector database management (Push, Search, Reset).
- `/api/v1/nlp/agent/chat`: The main entry point for the agent (Supports SSE Streaming).
- `/api/v1/nlp/agent/portfolio`: Automated professional evidence generation.
