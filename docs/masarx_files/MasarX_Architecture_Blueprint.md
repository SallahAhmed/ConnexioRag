# MasarX — Full Architectural Blueprint

**Connexio · Antigravity Module**

> Pre-implementation spec. No production code written yet.

---

## 1. Confirmed Tech Stack

| Concern            | Decision                                        |
| ------------------ | ----------------------------------------------- |
| Framework          | FastAPI + Uvicorn (fully async)                 |
| Agent framework    | LangGraph (multi-graph, async)                  |
| LLM Provider       | Groq (primary) · Ollama (fallback)              |
| Utility model      | `llama-3.1-8b-instant`                          |
| Generation model   | `llama-3.3-70b-versatile`                       |
| State persistence  | LangGraph Postgres Checkpointer                 |
| Database           | PostgreSQL (SQLAlchemy ORM)                     |
| Vector store / RAG | PGVector · bge-m3 · Hybrid RRF                  |
| Task queue         | Celery + RabbitMQ (broker) + Redis (results)    |
| Scheduled triggers | Celery Beat                                     |
| Event triggers     | FastAPI webhooks + background tasks             |
| Notifications      | FastAPI WebSockets + DB store                   |
| Email              | SMTP abstracted (SendGrid-ready)                |
| GitHub             | Personal Access Token (swappable to GitHub App) |
| Bot identity       | `masarx_bot` service account                    |

---

## 2. Final Directory Structure

```
antigravity/
└── MasarX/
    ├── __init__.py
    ├── main.py                    # Compiles the supervisor graph; exposes invoke_masarx()
    ├── graph.py                   # StateGraph + subgraph wiring; imports all nodes/edges
    ├── state.py                   # MasarXState TypedDict (the shared state contract)
    ├── config.py                  # Settings, env vars, model names, feature flags
    │
    ├── nodes/
    │   ├── __init__.py
    │   ├── router_node.py         # Supervisor: classifies intent, picks subgraph to invoke
    │   ├── task_manager.py        # Create / assign / prioritize tasks (HITL gated)
    │   ├── team_matcher.py        # Consume PGVector match scores → draft invitations
    │   ├── recommender.py         # Refine suggestions from ratings + activity history
    │   ├── streak_notifier.py     # Generate motivational quote → push notification
    │   ├── workload_monitor.py    # Detect overload → flag + suggest rebalance (HITL)
    │   ├── readme_generator.py    # Build README from project data + RAG context
    │   ├── doc_generator.py       # Draft milestone docs (saved as "Draft" status)
    │   ├── digest_sender.py       # Compile + send weekly sprint summary
    │   ├── risk_detector.py       # Detect blockers from overdue task patterns
    │   ├── onboarding.py          # Auto-generate checklist for new project members
    │   ├── retro_generator.py     # Draft post-sprint retrospective from velocity data
    │   └── hitl_node.py           # Generic plan → confirm → execute node (reused by Task + Monitor)
    │
    ├── edges/
    │   ├── __init__.py
    │   └── conditions.py          # All conditional edge functions (routing predicates)
    │
    ├── tools/
    │   ├── __init__.py
    │   ├── github_tool.py         # Push README, list commits, fetch PR metadata
    │   ├── db_tool.py             # CRUD: Task, Project, Sprint, TeamMember, Notification
    │   ├── notification_tool.py   # WebSocket push + DB store for in-app notifications
    │   ├── email_tool.py          # send_email() abstracted over SMTP / SendGrid
    │   └── rag_tool.py            # Wraps PGVector hybrid search (RRF, bge-m3)
    │
    ├── memory/
    │   ├── __init__.py
    │   ├── checkpointer.py        # Instantiates AsyncPostgresSaver from langgraph-checkpoint-postgres
    │   └── long_term_store.py     # Per-project key-value memory on top of the checkpointer
    │
    ├── prompts/
    │   ├── task_prompts.py        # Task creation / prioritization prompt templates
    │   ├── doc_prompts.py         # README + milestone doc prompt templates
    │   ├── digest_prompts.py      # Weekly sprint digest prompt template
    │   ├── quote_prompts.py       # Motivational streak quote prompt template
    │   └── team_prompts.py        # "Join our team" invitation prompt template
    │
    ├── schemas/
    │   ├── __init__.py
    │   ├── task_schema.py         # Pydantic: TaskPlan, TaskAssignment, WorkloadReport
    │   ├── team_schema.py         # Pydantic: MatchResult, InvitationDraft
    │   ├── digest_schema.py       # Pydantic: SprintDigest, BlockerSummary
    │   └── doc_schema.py          # Pydantic: ReadmeDraft, MilestoneDoc, RetroDraft
    │
    ├── triggers/
    │   ├── __init__.py
    │   ├── cron_jobs.py           # Celery Beat task definitions (daily quote, weekly digest, risk scan)
    │   └── webhook_handlers.py    # FastAPI router: /masarx/webhook/* endpoints
    │
    ├── rag/
    │   ├── __init__.py
    │   ├── retriever.py           # AsyncPGVectorRetriever with hybrid RRF search
    │   └── indexer.py             # Ingests new project docs into PGVector at milestone close
    │
    └── tests/
        ├── __init__.py
        ├── test_nodes.py
        ├── test_tools.py
        └── test_graph.py
```

---

## 3. `MasarXState` — Shared State Schema

```python
# state.py
from typing import TypedDict, Optional, Literal, Any
from datetime import datetime

DraftStatus = Literal["draft", "published", "pending_approval", "approved", "rejected"]
Intent = Literal[
    "create_tasks", "match_team", "send_quote", "send_digest",
    "generate_readme", "generate_milestone_doc", "monitor_workload",
    "detect_risks", "onboard_member", "generate_retro", "route_only"
]

class MasarXState(TypedDict):
    # ── Routing ──────────────────────────────────────────────────────────────
    intent:           Intent                  # Classified by router_node
    subgraph_target:  str                     # Which subgraph to invoke

    # ── Context IDs (lazy DB lookups; no large lists in state) ───────────────
    project_id:       str
    sprint_id:        Optional[str]
    user_id:          Optional[str]           # Triggering user (if event-driven)
    member_ids:       Optional[list[str]]     # Target members for notifications

    # ── Invocation metadata ──────────────────────────────────────────────────
    invocation_id:    str                     # Unique UUID per graph run
    triggered_by:     Literal["celery_beat", "webhook", "manual"]
    actor:            str                     # "masarx_bot" or "user:<id>"
    thread_id:        str                     # LangGraph thread = f"project:{project_id}"

    # ── HITL / Plan-Confirm-Execute ──────────────────────────────────────────
    pending_plan:     Optional[dict[str, Any]]  # Proposed plan (tasks, reassignments)
    plan_approved:    Optional[bool]
    approval_token:   Optional[str]           # Signed token sent to project owner
    approval_expires: Optional[datetime]      # Token TTL (15 min default)

    # ── RAG context ──────────────────────────────────────────────────────────
    retrieved_context: Optional[list[str]]    # Chunks from PGVector hybrid search

    # ── Output ───────────────────────────────────────────────────────────────
    output:           Optional[dict[str, Any]]  # Structured result (task list, match list…)
    draft_content:    Optional[str]           # Natural language (README, digest, quote…)
    draft_status:     DraftStatus

    # ── Persistent memory flags (survive between invocations via checkpointer) ─
    last_quote_sent_at:      Optional[datetime]
    last_digest_sent_at:     Optional[datetime]
    last_risk_scan_at:       Optional[datetime]
    last_readme_generated_at: Optional[datetime]

    # ── Error handling ───────────────────────────────────────────────────────
    error:            Optional[str]
    retry_count:      int
```

---

## 4. Graph Topology

```python
# graph.py (pseudo-code — shows wiring; not final syntax)
from langgraph.graph import StateGraph, START, END
from nodes.router_node import router_node
from edges.conditions import route_to_subgraph, should_execute_plan, has_error

# ── Subgraph imports (each is its own compiled graph) ──
from subgraphs.task_subgraph    import task_graph
from subgraphs.team_subgraph    import team_graph
from subgraphs.notify_subgraph  import notify_graph
from subgraphs.doc_subgraph     import doc_graph
from subgraphs.monitor_subgraph import monitor_graph

supervisor = StateGraph(MasarXState)

supervisor.add_node("router",  router_node)
supervisor.add_node("task",    task_graph.compile())    # subgraph as node
supervisor.add_node("team",    team_graph.compile())
supervisor.add_node("notify",  notify_graph.compile())
supervisor.add_node("docs",    doc_graph.compile())
supervisor.add_node("monitor", monitor_graph.compile())

supervisor.add_edge(START, "router")

supervisor.add_conditional_edges("router", route_to_subgraph, {
    "create_tasks":           "task",
    "match_team":             "team",
    "send_quote":             "notify",
    "send_digest":            "notify",
    "generate_readme":        "docs",
    "generate_milestone_doc": "docs",
    "generate_retro":         "docs",
    "monitor_workload":       "monitor",
    "detect_risks":           "monitor",
    "onboard_member":         "team",
})

# All subgraphs terminate back to END (or to hitl_node for gated ones)
for node in ["task", "team", "notify", "docs", "monitor"]:
    supervisor.add_edge(node, END)

masarx_graph = supervisor.compile(checkpointer=postgres_checkpointer)
```

---

## 5. Subgraph Breakdown

### 5.1 TaskSubgraph

**Trigger:** Webhook (`project.milestone_planned`, `project.sprint_started`) · Manual API call

| Node                    | Model | Role                                                         |
| ----------------------- | ----- | ------------------------------------------------------------ |
| `fetch_project_context` | —     | Pull sprint, backlog, team capacity from DB                  |
| `rag_context_node`      | —     | Query PGVector for similar past sprint tasks                 |
| `task_planner`          | 70b   | Generate structured `TaskPlan` (Pydantic) from context       |
| `hitl_node`             | —     | Serialize plan → notify project owner → await approval token |
| `task_executor`         | —     | On approval: `db_tool.create_tasks()` for each item in plan  |
| `task_notifier`         | —     | `notification_tool.push()` to assigned members               |

**HITL flow:**

```
task_planner → hitl_node → [owner approves via /masarx/webhook/approve/{token}]
                         → task_executor → task_notifier → END
                         OR [owner rejects]
                         → END (plan discarded, rejection logged)
```

**Actor label on execution:** `"Created by MasarX · Approved by {owner_name}"`

---

### 5.2 TeamSubgraph

**Trigger:** Webhook (`user.joined_platform`, `project.member_needed`, `user.joined_project`)

| Node                      | Model | Role                                                                  |
| ------------------------- | ----- | --------------------------------------------------------------------- |
| `fetch_user_profile`      | —     | Load skills, interests, activity history from DB                      |
| `pgvector_match_node`     | —     | `rag_tool.similarity_search()` → ranked list of user IDs + scores     |
| `invitation_drafter`      | 70b   | Draft personalized "Join our team" invitation per match               |
| `send_invitations`        | —     | `notification_tool.push()` + `email_tool.send()`                      |
| `onboarding_generator`    | 70b   | (on `user.joined_project`) Generate personalized onboarding checklist |
| `onboarding_task_creator` | —     | `db_tool.create_tasks()` for onboarding checklist items               |

---

### 5.3 NotifySubgraph

**Trigger:** Celery Beat (daily 9am UTC for quotes · Friday 5pm UTC for digest)

| Node                     | Model | Role                                                                  |
| ------------------------ | ----- | --------------------------------------------------------------------- |
| `check_quote_sent_today` | —     | Read `last_quote_sent_at` from state; skip if already sent            |
| `quote_generator`        | 8b    | Generate motivational streak quote (natural language, not structured) |
| `push_quote`             | —     | `notification_tool.push()` to all active project members              |
| `check_digest_sent_week` | —     | Read `last_digest_sent_at`; skip if already sent this week            |
| `digest_compiler`        | 8b    | Aggregate task completion %, blockers, upcoming deadlines from DB     |
| `digest_writer`          | 70b   | Draft human-readable digest email body                                |
| `send_digest`            | —     | `email_tool.send()` to project communication feed                     |

**Idempotency:** Both nodes check their memory flag before acting. This prevents double-sends if Celery retries a failed task.

---

### 5.4 DocSubgraph

**Trigger:** Webhook (`project.closed`, `milestone.completed`, `sprint.closed`)

| Node                   | Model | Role                                                                      |
| ---------------------- | ----- | ------------------------------------------------------------------------- |
| `fetch_project_data`   | —     | Pull project description, task history, contributor list, sprint velocity |
| `rag_context_node`     | —     | Query PGVector for indexed project documents                              |
| `github_context_node`  | —     | `github_tool.list_commits()`, `github_tool.list_prs()`                    |
| `readme_writer`        | 70b   | Fill standardized Markdown README template; status → `"draft"`            |
| `readme_publisher`     | —     | On owner publish action: `github_tool.push_readme()`                      |
| `milestone_doc_writer` | 70b   | Generate milestone documentation draft                                    |
| `retro_writer`         | 70b   | Post-sprint retrospective from velocity + blocker history                 |
| `doc_saver`            | —     | `db_tool.save_document()` with `draft_status = "draft"`                   |

**Note:** README and docs are saved as `"draft"` and pushed/published only on an explicit owner action. This satisfies the semi-autonomous requirement.

---

### 5.5 MonitorSubgraph

**Trigger:** Celery Beat (daily 8am UTC · risk scan)

| Node                  | Model | Role                                                                 |
| --------------------- | ----- | -------------------------------------------------------------------- |
| `fetch_workload_data` | —     | Pull task counts, deadlines, story points per member from DB         |
| `workload_analyzer`   | 8b    | Compute overload score (deadline density × unresolved count)         |
| `risk_scanner`        | 8b    | Flag tasks overdue > 2 days; identify blockers                       |
| `rebalance_planner`   | 70b   | Generate structured `WorkloadReport` with suggested reassignments    |
| `hitl_node`           | —     | Notify project owner with report; await approval                     |
| `rebalance_executor`  | —     | On approval: `db_tool.reassign_tasks()` + notify affected members    |
| `alert_sender`        | —     | `notification_tool.push()` risk/blocker alerts immediately (no HITL) |

**Overload definition:** `overload_score = (tasks_due_within_3_days / capacity) + (unresolved_count / avg_team_unresolved)`
If `overload_score > 1.5` → flagged.

---

## 6. Trigger Mapping

| Feature                  | Trigger Type                   | Celery Task            | Webhook Event          | HITL?           |
| ------------------------ | ------------------------------ | ---------------------- | ---------------------- | --------------- |
| Daily streak quote       | Celery Beat · 09:00 UTC        | `masarx_daily_quote`   | —                      | No              |
| Team match suggestions   | Webhook                        | —                      | `user.joined_platform` | No              |
| Autonomous task creation | Webhook                        | —                      | `sprint.started`       | **Yes**         |
| Workload rebalance       | Celery Beat · 08:00 UTC        | `masarx_workload_scan` | —                      | **Yes**         |
| README generation        | Webhook                        | —                      | `project.closed`       | No (draft)      |
| Milestone doc draft      | Webhook                        | —                      | `milestone.completed`  | No (draft)      |
| Weekly digest            | Celery Beat · Friday 17:00 UTC | `masarx_weekly_digest` | —                      | No              |
| Onboarding checklist     | Webhook                        | —                      | `user.joined_project`  | No              |
| Risk / blocker alerts    | Celery Beat · 08:00 UTC        | `masarx_risk_scan`     | —                      | No (alert only) |
| Sprint retrospective     | Webhook                        | —                      | `sprint.closed`        | No (draft)      |

---

## 7. Model Routing Strategy

```python
# config.py
UTILITY_MODEL  = "llama-3.1-8b-instant"   # Routing, quotes, digest structure, workload math
GENERATION_MODEL = "llama-3.3-70b-versatile"  # README, docs, task planning, invitations, retro

OLLAMA_FALLBACK = {
    UTILITY_MODEL:    "llama3.1:8b",
    GENERATION_MODEL: "llama3.3:70b",
}

# Per-node model assignment
NODE_MODEL_MAP = {
    "router_node":          UTILITY_MODEL,
    "task_planner":         GENERATION_MODEL,
    "quote_generator":      UTILITY_MODEL,
    "digest_compiler":      UTILITY_MODEL,
    "digest_writer":        GENERATION_MODEL,
    "workload_analyzer":    UTILITY_MODEL,
    "risk_scanner":         UTILITY_MODEL,
    "rebalance_planner":    GENERATION_MODEL,
    "readme_writer":        GENERATION_MODEL,
    "milestone_doc_writer": GENERATION_MODEL,
    "retro_writer":         GENERATION_MODEL,
    "invitation_drafter":   GENERATION_MODEL,
    "onboarding_generator": GENERATION_MODEL,
}
```

**Fallback logic:** Each node wraps its Groq call in a try/except. On `RateLimitError` or timeout, it retries once with Ollama via the `OLLAMA_FALLBACK` map. State field `retry_count` is incremented; on `retry_count > 2` the node returns an error state and the supervisor routes to END with `draft_status = "error"`.

---

## 8. HITL Flow — Plan → Confirm → Execute

```
1. [Agent] Plans action (task list or reassignment plan)
2. [hitl_node] Serializes plan to JSON → saves to DB with approval_token (UUID)
3. [notification_tool] Pushes "MasarX has a plan ready for your review" to project owner
                        WebSocket notification + DB record
4. [Graph PAUSES] — LangGraph checkpointer preserves state at hitl_node
5. [Owner] Reviews plan in Connexio UI → clicks "Approve" or "Reject"
6. [Webhook] POST /masarx/webhook/approve/{approval_token}
             FastAPI validates token signature + TTL (15 min)
7. [Graph RESUMES] — checkpointer restores state
   → plan_approved = True  → executor node runs
   → plan_approved = False → END, plan discarded, rejection logged
```

**Token security:** `approval_token` is a HMAC-signed JWT containing `{project_id, invocation_id, exp}`. Validated in `webhook_handlers.py` before resuming the graph.

---

## 9. Tool Contracts

### `github_tool.py`

```python
async def push_readme(repo: str, content: str, branch: str = "main") -> dict
async def list_commits(repo: str, since: datetime, limit: int = 50) -> list[Commit]
async def list_prs(repo: str, state: str = "all") -> list[PullRequest]
async def get_repo_structure(repo: str) -> dict  # file tree for README context
```

Auth: `Authorization: token {GITHUB_PAT}`. Designed so swapping to GitHub App only requires changing the auth header logic in one place.

### `db_tool.py`

```python
async def get_project(project_id: str) -> Project
async def get_sprint(sprint_id: str) -> Sprint
async def get_team_members(project_id: str) -> list[TeamMember]
async def get_tasks(project_id: str, filters: dict) -> list[Task]
async def create_tasks(tasks: list[TaskAssignment], actor: str) -> list[Task]
async def reassign_task(task_id: str, to_member_id: str, actor: str) -> Task
async def save_document(doc: MilestoneDoc | ReadmeDraft | RetroDraft) -> Document
async def save_notification(notification: NotificationRecord) -> None
```

### `rag_tool.py`

```python
async def hybrid_search(
    query: str,
    project_id: str,
    top_k: int = 5,
    alpha: float = 0.5  # weight between dense and sparse
) -> list[str]  # returns text chunks, not raw docs
```

Uses the existing `antigravity` PGVector store with bge-m3 embeddings and RRF re-ranking. `project_id` is used as a metadata filter to scope retrieval to the project's own documents.

### `notification_tool.py`

```python
async def push(
    user_ids: list[str],
    title: str,
    body: str,
    payload: dict,           # action data (approval token, doc ID, etc.)
    channel: str = "masarx"
) -> None
# Attempts WebSocket delivery first; falls back to DB insert for next login poll
```

### `email_tool.py`

```python
async def send(
    to: list[str],
    subject: str,
    body_html: str,
    body_text: str,
) -> None
# Abstracted: swapping SMTP → SendGrid only changes this function's internals
```

---

## 10. Checkpointer + Memory Setup

```python
# memory/checkpointer.py
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import create_async_engine

async def get_checkpointer() -> AsyncPostgresSaver:
    engine = create_async_engine(settings.DATABASE_URL)
    checkpointer = AsyncPostgresSaver(engine)
    await checkpointer.setup()  # creates checkpoint tables if not exist
    return checkpointer

# Thread ID convention: one thread per project
# thread_id = f"masarx:project:{project_id}"
# This means MasarX remembers all state (last_quote_sent, last_digest_sent, etc.)
# across every invocation for a given project.
```

---

## 11. Webhook Handler Structure

```python
# triggers/webhook_handlers.py
from fastapi import APIRouter, BackgroundTasks

router = APIRouter(prefix="/masarx/webhook")

@router.post("/event/{event_type}")
async def handle_event(event_type: str, payload: dict, bg: BackgroundTasks):
    """Receives platform events and dispatches MasarX invocations as background tasks."""
    intent = EVENT_TO_INTENT_MAP[event_type]
    bg.add_task(invoke_masarx, intent=intent, payload=payload)
    return {"status": "accepted"}

@router.post("/approve/{approval_token}")
async def handle_approval(approval_token: str, decision: ApprovalDecision):
    """Resumes a paused HITL graph after owner approval or rejection."""
    invocation = await db_tool.get_pending_plan(approval_token)
    await masarx_graph.aupdate_state(
        config={"configurable": {"thread_id": invocation.thread_id}},
        values={"plan_approved": decision.approved, "approval_token": None}
    )
    return {"status": "graph_resumed"}

EVENT_TO_INTENT_MAP = {
    "user.joined_platform":    "match_team",
    "user.joined_project":     "onboard_member",
    "project.closed":          "generate_readme",
    "milestone.completed":     "generate_milestone_doc",
    "sprint.closed":           "generate_retro",
    "project.sprint_started":  "create_tasks",
}
```

---

## 12. Celery Beat Schedule

```python
# triggers/cron_jobs.py
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    "masarx-daily-quote": {
        "task": "masarx.tasks.send_daily_quote",
        "schedule": crontab(hour=9, minute=0),   # 09:00 UTC daily
    },
    "masarx-workload-scan": {
        "task": "masarx.tasks.run_workload_scan",
        "schedule": crontab(hour=8, minute=0),   # 08:00 UTC daily
    },
    "masarx-risk-scan": {
        "task": "masarx.tasks.run_risk_scan",
        "schedule": crontab(hour=8, minute=30),  # 08:30 UTC daily
    },
    "masarx-weekly-digest": {
        "task": "masarx.tasks.send_weekly_digest",
        "schedule": crontab(hour=17, minute=0, day_of_week=5),  # Friday 17:00 UTC
    },
}
```

Each task calls `invoke_masarx(intent=..., project_id=...)` for every active project. No APScheduler is introduced.

---

## 13. Suggested Additional Features (3 new nodes, already in structure)

| Feature                     | Node                 | Trigger               | Model | HITL?            |
| --------------------------- | -------------------- | --------------------- | ----- | ---------------- |
| **Risk / Blocker Detector** | `risk_detector.py`   | Daily cron 08:30 UTC  | 8b    | No — alerts only |
| **New Member Onboarding**   | `onboarding.py`      | `user.joined_project` | 70b   | No               |
| **Sprint Retrospective**    | `retro_generator.py` | `sprint.closed`       | 70b   | No — draft only  |

---

## 14. What Happens Next (Implementation Order)

```
Phase 1 — Foundation
  → state.py · config.py · checkpointer.py · graph.py skeleton

Phase 2 — Tools
  → db_tool · rag_tool · notification_tool · email_tool · github_tool

Phase 3 — Subgraphs (order of risk)
  → NotifySubgraph (simplest, no HITL, validates stack end-to-end)
  → TeamSubgraph (tests PGVector + invitation flow)
  → DocSubgraph (tests GitHub + long-form generation)
  → MonitorSubgraph (tests HITL loop)
  → TaskSubgraph (full HITL + DB write)

Phase 4 — Triggers
  → Celery Beat tasks
  → Webhook handlers + approval endpoint

Phase 5 — Tests + Observability
  → Unit tests per node · Integration test per subgraph
  → LangSmith tracing (optional but recommended with Groq)
```
