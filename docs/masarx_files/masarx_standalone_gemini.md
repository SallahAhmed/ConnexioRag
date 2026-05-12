# MasarX — Standalone Agent Workspace Context

> **Purpose:** This file provides the foundational knowledge for any AI agent (like Antigravity) working in the `F:\MasarX` workspace. It establishes the architectural boundaries and the strategy for building the agent in isolation before integration.

---

## 1. PROJECT IDENTITY

**Project Name:** MasarX
**Parent System:** Connexio (Antigravity Module)
**Role:** A multi-functional, asynchronous AI agent built with LangGraph to automate project management, team building, and documentation.

## 2. DEVELOPMENT STRATEGY: "STANDALONE FIRST"

This repository (`F:\MasarX`) is an isolated sandbox. We are building the agent **entirely decoupled** from the main Connexio backend.

**Rules for Standalone Development:**

1. **Mock Dependencies:** The main Connexio DB (Project, Task, User) and the PGVector store do not exist here. We will use a local **SQLite database** (using SQLAlchemy) with mock models to simulate the real DB.
2. **Mock Tools:** `github_tool`, `email_tool`, and `notification_tool` should simply print to the console or return static JSON responses during this phase.
3. **Checkpointer:** Use the `AsyncSqliteSaver` (LangGraph SQLite checkpointer) instead of Postgres for local rapid testing.
4. **Integration Later:** Once the agent successfully runs its subgraphs and HITL (Human-in-the-loop) flows locally, we will port the code over to `Connexio/src/MasarX` and swap the mock DB connections with the real Postgres/PGVector connections.

## 3. ARCHITECTURE & TECH STACK

- **Core Framework:** LangGraph (Multi-graph, Supervisor routing)
- **Execution:** Fully Async (`async def`, `asyncio`)
- **LLM Providers:** Groq (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`)
- **State Management:** TypedDict (`MasarXState`) scoped per-project.
- **Data Modeling:** Pydantic (for structured LLM outputs) and SQLAlchemy (for mock local DB).

## 4. AGENT BEHAVIORAL RULES

1. **Focus on Subgraphs:** Build one subgraph at a time (e.g., `NotifySubgraph`, `TaskSubgraph`). Do not try to build the entire supervisor graph at once.
2. **HITL Flow Testing:** When implementing Human-in-the-loop, simulate the webhook pause/resume mechanism using simple Python input prompts or local FastAPI test endpoints.
3. **No Django:** Assume FastAPI/Asyncio patterns. Do not write synchronous ORM code.
4. **Resilience:** Wrap LLM calls with try/except fallbacks.

## 5. REPOSITORY STRUCTURE (Isolated)

```
F:\MasarX\
├── core/               # config, state, supervisor graph
├── subgraphs/          # task, team, doc, notify, monitor subgraphs
├── mock_db/            # SQLite models (Project, Task, User) simulating Connexio
├── tools/              # Mocked tools (db, github, email, rag)
└── tests/              # Local async tests invoking the graph directly
```
