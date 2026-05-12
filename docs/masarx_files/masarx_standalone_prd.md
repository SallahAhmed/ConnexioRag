# Product Requirements Document (PRD) — MasarX Agent

## 1. Overview

**MasarX** is the intelligent, agentic core of the Connexio platform. It automates project management lifecycles, intelligently matches cross-disciplinary teams, and generates standardized documentation.

This PRD defines the requirements for building MasarX as a **standalone, isolated LangGraph service** before it is integrated into the main Connexio backend.

---

## 2. Objectives

1. Build a robust, scalable LangGraph multi-graph agent capable of intent routing.
2. Validate all 9 core capabilities locally using mock databases and simulated external API calls.
3. Perfect the Human-In-The-Loop (HITL) pause/resume logic for critical actions.
4. Ensure the system is easily portable to the main Connexio FastAPI/Postgres architecture.

---

## 3. Core Capabilities (The 9 Tasks)

### 🟢 Fully Autonomous Tasks (No Human Intervention)

1. **Team Match Suggestions:** Read a list of user embeddings/scores and draft personalized "Join our project" invitations.
2. **Recommender Refinement:** Update internal user rating scores based on project history (mocked logic).
3. **Motivational Streaks:** Generate and send daily motivational quotes to active team members.
4. **Sprint Digest:** Compile a weekly summary email detailing task completion rates, blockers, and upcoming deadlines.
5. **Workload Alerting:** Identify tasks overdue by >2 days and push immediate warnings to the assigned user.

### 🟡 Semi-Autonomous Tasks (Draft / Await Publish)

6. **README Generation:** Automatically draft a standardized project README based on codebase metadata and task history when a project closes. (Saves as "Draft").
7. **Milestone Documentation:** Generate documentation drafts when a sprint or milestone is completed.

### 🔴 Human-In-The-Loop (HITL) Tasks (Require Explicit Approval)

8. **Autonomous Task Creation:** Analyze a project description/sprint plan, propose a structured list of tasks and assignments. _Requires Project Owner approval to execute._
9. **Workload Rebalancing:** Detect overloaded team members, propose reassigning their tasks to members with free capacity. _Requires Project Owner approval to execute._

---

## 4. Standalone Execution Requirements

Because MasarX is being built in isolation (`F:\MasarX`), the following mock bridges must be constructed:

### 4.1 Mock Database (SQLite)

Create simple SQLAlchemy models pointing to a local `masarx_mock.db`:

- `MockUser` (id, name, skills)
- `MockProject` (id, title, description, status)
- `MockTask` (id, project_id, assignee_id, status, deadline)
- `MockTeamMember` (id, project_id, user_id, role)

### 4.2 Mock Tools (Console Output)

- `rag_tool`: Instead of connecting to PGVector, this tool will return hardcoded lists of text chunks for testing retrieval context.
- `github_tool`: Prints the generated README to the console instead of pushing to an actual repo.
- `notification_tool`: Logs `[PUSH NOTIFICATION] To: User X | Body: Y` to the terminal.

### 4.3 Checkpointer

Use `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver` instead of Postgres to allow the graph to pause and wait for HITL approval locally.

---

## 5. Development Phases

**Phase 1: Foundation & Mocks**

- Setup `MasarXState` TypedDict.
- Initialize the local SQLite mock database and populate it with seed data (1 project, 3 users, 5 tasks).
- Build the `db_tool.py` wrapper around the SQLite models.

**Phase 2: Subgraph Implementation**

- Build `NotifySubgraph` (Quotes & Digests) - Easiest entry point.
- Build `DocSubgraph` (README & Milestones) - Tests heavy LLM generation.
- Build `TeamSubgraph` (Invitations) - Tests parsing mock RAG context.
- Build `MonitorSubgraph` (Workload) - Tests math and logic.
- Build `TaskSubgraph` (Planning) - Tests complex Pydantic structured output.

**Phase 3: The Supervisor & HITL**

- Build `router_node.py` to classify incoming intents and route to the correct subgraph.
- Implement the pause/resume mechanism using the SQLite checkpointer.
- Create a simple local FastAPI script (`local_test_api.py`) to trigger the graph and simulate hitting the "Approve" webhook.

**Phase 4: Porting & Integration (Future)**

- Move the codebase to `Connexio/src/MasarX`.
- Swap `AsyncSqliteSaver` for `AsyncPostgresSaver`.
- Point `db_tool.py` to the real Connexio SQLAlchemy models.
- Connect `rag_tool.py` to PGVector.
