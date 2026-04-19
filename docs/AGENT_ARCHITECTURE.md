# Agent Development & Architecture History

This document aggregates the implementation plans and overhauls performed during the evolution of the Multi-Source RAG Agent.

---

## 🏗️ Phase 1: Context Management & Strict Budgeting

### Goal
Resolve persistent "context length exceeded" errors caused by large SQL schemas, conversational history, and retrieved knowledge base context pushing past local model limits (e.g., 2k-4k tokens).

### Implementation Summary
- **Infrastructure**: Introduced `TOTAL_CONTEXT_CHAR_BUDGET` (default 15,000) in `.env`.
- **Sliding History Window**: Implemented `_get_truncated_history` in `NLPController` to work backward from the newest message until the budget is filled.
- **Resource Budgeting**:
    - **Retrieved Context**: Limited to 50% of the total budget.
    - **History**: Limited to 30% of the total budget.
    - **Individual Messages**: Capped at 2,000 characters to prevent a single massive message from blowing the budget.
- **Strict Tool Truncation**:
    - **SQL Schema**: Truncated to 5,000 characters.
    - **SQL Results**: Capped at 1,500 characters.
    - **Knowledge Base**: Capped at 3,000 characters.
    - **Wikipedia**: Capped at 2,000 characters.

---

## ⚡ Phase 2: Performance & Stability Overhaul

### Goal
Resolve server "hangs" (appearing as "downloading" in Postman) caused by synchronous LLM calls blocking the FastAPI event loop, and fix database schema mismatches in specialized tools.

### Key Improvements
1. **Asynchronous LLM Client**:
    - Migrated `OpenAIProvider` from `OpenAI` to **`AsyncOpenAI`**.
    - Updated `NLPController` and `WorkflowController` to `await` all generation results.
    - *Benefit*: The server remains responsive and can handle other requests while the LLM is "thinking."

2. **Non-blocking Tool Execution**:
    - Offloaded synchronous `SQLDatabase` and `WikipediaQueryRun` calls to background threads using `asyncio.to_thread`.
    - *Benefit*: Slow tool lookups no longer freeze the entire application.

3. **Database & Tool Alignment**:
    - **Schema Match**: Aligned RAG database table names (e.g., `projects` plural instead of legacy `project` singular).
    - **Schema Expansion**: Added `project_name` and `progress` to the `projects` table to support Supervisor/Risk Assessment tools.
    - **Defensive Error Handling**: Added graceful fallbacks to all tools (Team Gaps, Portfolios, Doc Gen). If a core application table (like `task` history) is missing, the agent explains the situation instead of returning a 500 error.

### Verification Commands
To apply the necessary schema changes manually to the container:
```powershell
docker exec -it pgvector psql -U postgres -d connexio -c "ALTER TABLE projects ADD COLUMN project_name VARCHAR(255); ALTER TABLE projects ADD COLUMN progress INTEGER DEFAULT 0;"
```

---

## 🧪 Testing Guide

### Core RAG Flow
1. **Push**: Use `/api/v1/nlp/index/push` to index document chunks.
2. **Search**: Use `/api/v1/nlp/index/search` for basic grounding checks.
3. **Agent Chat**: Use `/api/v1/nlp/agent/chat` for the full persona-aware, multi-source routing experience.

### Specialized Tools
- **Risk Assessment**: Ask "Who is at risk in this project?" or "Which projects are behind schedule?"
- **Team Formation**: Ask "What technology are we missing?" or "Find me a developer for project 2."
- **Document Gen**: Ask "Generate a README for project 1."
- **Matching Rationale**: Ask "Why was I matched to project 2?"
