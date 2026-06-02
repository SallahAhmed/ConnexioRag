# OpenWolf

@.wolf/OPENWOLF.md

This project uses OpenWolf for context management. Read and follow .wolf/OPENWOLF.md every session. Check .wolf/cerebrum.md before generating code. Check .wolf/anatomy.md before reading files.

---

# CLAUDE.md — Connexio Platform Master Reference

> **Last updated:** 2026-06-02 — Phase 3 implementation complete (all 21 items). Hostinger needs `git pull` + restart. RAG needs `git pull` + restart (NLPController shortcut handlers). Phase 4 ready to start.
> **Source of truth for ecosystem details:** `F:\MasarX_A\AGENTS.md`
> **Execution plans:** `F:\MasarX_A\.opencode\plans\`
>
> ⚠️ **STANDING RULE:** Update this file at the end of every completed task or phase. Keep every status row, convention, and secret-needed note current. A stale CLAUDE.md is worse than no CLAUDE.md.

---

## 1. System Overview

**Connexio** is a collaborative platform connecting learners and builders to create real software projects in intelligent teams. All four components are active and must work together as one production system.

| Component | Local Path | Hosting | Status | Role |
|-----------|-----------|---------|--------|------|
| **Frontend** | `F:\Connexio_Frontend2` | TBD (dev: `localhost:5173`) | ✅ Active — React 19 + Vite + Tailwind | SPA: auth, projects, tasks, chat, AI chat, profiles |
| **Node.js Backend** | `F:\connexio_back2` | Hostinger (`connexio.icu:3000`) | ✅ Deployed | Core API: auth, users, projects, tasks, chat, file upload, Socket.IO |
| **Connexios RAG** | `C:\Users\salla\Connexios` | HF Spaces (`ConnexioRag`) | ✅ Deployed — DB confirmed on port 5432 | Knowledge engine: document indexing, hybrid search, intent-aware chat |
| **MasarX Agent** | `F:\MasarX_A` | Azure VM (`connexio-agent.centralus.cloudapp.azure.com`) | ✅ Fully operational | Autonomous PM: task planning (HITL), team matching, audit, HITL workflows, GitHub scaffolding |
| **Admin Panel** | `F:\connexio-adminPanel` | Standalone (Electron) | ✅ Built by teammate | System-admin tool — **NO changes from this execution plan** |

---

## 2. Architecture

```
User Browser (React SPA, localhost:5173 / connexio.icu)
        │
        │  axios + Socket.IO (JWT Bearer)
        ▼
Node.js Backend (Express, MySQL + MongoDB, Hostinger:3000)
        │
        ├── X-API-Key ──────────────────► Connexios RAG (HF Spaces)
        │   POST /api/v1/data/upload-and-process/{pid}    (file indexing, 202)
        │   POST /api/v1/projects/sync                    (project PID sync)
        │   POST /api/v1/nlp/agent/chat/{pid}             (non-streaming chat)
        │   GET  /api/v1/nlp/agent/chat/stream/{pid}      (SSE streaming)
        │
        └── Service JWT (5min HS256) ────► MasarX Agent (HF Spaces)
            POST /api/v1/masarx/webhook/event/{type}/{pid}  (fire-and-forget, 202)
            POST /api/v1/masarx/agent/{intent}/{pid}        (blocking intent)
            POST /api/v1/masarx/approval/{token}            (HITL approval)

Both Python services share PostgreSQL (Neon.tech):
  RAG owns:    projects, assets, chunks, rag_chat_sessions, collection_{size}_{pid}, project_id_map
  MasarX owns: user, task, masarx_notifications, masarx_pending_plans, masarx_webhook_results, masarx_documents
```

### Auth model
- **Frontend → Backend:** JWT Bearer (`cx-token` in localStorage, 7d expiry). JWT payload: `{ UID, email, user_type, is_admin, account_type }`.
- **Backend → RAG:** `X-API-Key` header (`CONNEXIO_INTERNAL_API_KEY`). Dev bypass if unset.
- **Backend → MasarX:** Short-lived JWT (`JWT_SECRET`, 5min, payload `{ UID, project_id, intent }`).
- **RAG/MasarX → Backend:** JWT with same `JWT_SECRET` (service actor, 5min expiry).
- **Socket.IO:** `socket.handshake.auth.token` (same user JWT).

---

## 3. Databases

### MySQL (Backend — Hostinger)
Connection pool: 20 connections. `query()` helper in `dbconnection.js` converts PG `$N` → `?`, removes `RETURNING`, `ILIKE` → `LIKE`.

**Critical conventions:**
- `query()` returns `{ rows }`, never a bare array. Always destructure: `const { rows } = await query(...)`.
- Column names are mixed-case as defined: `UID`, `PID`, `taskID`, `PName`, `TaskDesc`, `FullName`. Never lowercase variants.
- `projects.PName` — NOT `project_name`. `tasks.taskID` — NOT `taskId`.
- Schema auto-migrates on boot via idempotent `ALTER TABLE` in `createTables()`. **Do NOT use a separate migration file runner** — extend `createTables()` with try/catch alter blocks.

**Key tables:** `users`, `projects`, `project_members`, `tasks`, `task_dependencies`, `sprints`, `team_ratings`, `friends`, `friend_requests`, `blocked_users`, `groups`, `group_members`, `technical_skills`, `non_technical_skills`, `user_skills`

**New tables (added Phase 0):** `project_contracts`, `contract_signatures`, `active_sessions`

**Phase 3 tables (added):** `courses`, `course_members`, `course_projects`, `project_ideas`, `idea_members`, `mentor_applications`

**Planned tables:** `analytics_daily`, `push_subscriptions` (mobile Phase 5)

### MongoDB (Backend — Chat/Rooms)
Mongoose models: `ChatRoom`, `Message`, `CallRoom`, `CallHistory`, `ChatbotSession`, `Post`, `Comment`, `Notification`

### PostgreSQL (Neon.tech — shared by RAG + MasarX)
See AGENTS.md §3 for full schema. RAG uses Alembic for migrations. MasarX must NOT run `create_all` for `chunks` or `projects`.

---

## 4. Dev Commands

### Frontend
```bash
cd F:\Connexio_Frontend2
npm run dev        # → http://localhost:5173
npm run build      # production build
```

### Backend
```bash
cd F:\connexio_back2
npm run dev        # nodemon → http://localhost:3000
npm start          # production
```

### RAG
```bash
cd C:\Users\salla\Connexios\src
uvicorn main:app --reload --port 8080
python -m celery -A celery_app worker --queues=default,file_processing,data_indexing --loglevel=info
python -m celery -A celery_app beat --loglevel=info
python -m celery -A celery_app flower --conf=flowerconfig.py  # → http://localhost:5556
```

### MasarX
```bash
cd F:\MasarX_A\src
uvicorn main:app --reload --port 8000
python -m celery -A celery_app worker --loglevel=info
python -m celery -A celery_app beat --loglevel=info
```

---

## 5. Execution Plan — Current Status

The platform is executing a 5-phase enhancement plan (61 items). Source: `F:\MasarX_A\.opencode\plans\`.

| Phase | Name | Days | Items | Status |
|-------|------|------|-------|--------|
| **0** | Hidden Fixes + Infrastructure | Day 0 | 20 | ✅ Complete |
| **1** | Foundation | Days 1-3 | 13 | ✅ Complete |
| **2** | Core Features | Days 4-7 | 17 | ✅ Complete |
| **3** | @connexio + Platform | Days 8-12 | 21 | ✅ Complete |
| **4** | Polish | Days 13-16 | 8 | ⏳ Pending |
| **5** | Mobile (Flutter) | Days 17-23 | 4 | ⏳ Pending |

### Phase 0 Checklist
- [x] H1: `users.username` + `users.is_admin` + `users.account_type` columns — `dbconnection.js`
- [x] H33: Account type enforcement (3/month normal) + monthly counter columns — `projects.controller.js`
- [x] H34: `project_contracts` + `contract_signatures` tables — `dbconnection.js`
- [x] Stripe Pro upgrade flow — `stripeService.js` + `payments` module. **Needs: npm install stripe + .env keys**
- [x] In-app e-signature (typed name + canvas) — `eSignatureService.js` + `ContractSigning.jsx`
- [x] Contract enforcement (rating drop + 7-day restriction) — `contractService.js`
- [x] JWT payload update (`is_admin`, `account_type`) — `auth.controller.js`
- [x] H4/B16: Helmet.js + CSP — `bootstrap.js`. **Needs: npm install helmet**
- [x] H5: `express-rate-limit` on auth routes — `rateLimiter.js` + `bootstrap.js`. **Needs: npm install express-rate-limit**
- [x] H6: `app.set('trust proxy', 1)` — `app.js`
- [x] H7: Fix MasarX seed data (`technology_used`) — `seed_data.py`
- [x] H12: Graceful shutdown (`SIGTERM`) — `app.js`
- [x] B1: `pending_verification` in `ALLOWED_STATUS` — `tasks.controller.js`
- [x] `responseHandler.js` utility — `utils/responseHandler.js`
- [x] `projects.mode`, `projects.ai_trigger`, `projects.guest_token` columns — `dbconnection.js`
- [x] `tasks.verified_by`, `tasks.verified_at` columns — `dbconnection.js`
- [x] `contribution_evidence` table — `dbconnection.js`
- [x] `audit_log` table — `dbconnection.js`
- [x] A1: Co-founder matching enhancements (interest + trust bonus) — `team_subgraph.py`
- [x] A2: Workload-aware risk detection (overloaded/at-risk/stalled flags) — `monitor_subgraph.py`
- [x] Frontend: `AccountTypeBadge`, `UpgradePrompt`, `ContractSelector`, `ContractSigning` + i18n (en + ar)

---

## 6. New Features (Execution Plan)

### Account Types
Three tiers: **Normal** (free, 3 projects/month create+join), **Pro** ($20/mo via Stripe, unlimited + extended AI context + priority matching), **Org** (Phase 2, admin-managed orgs).
- Normal users hitting 3/month limit → upgrade prompt modal.
- Pro: real Stripe Checkout subscription → webhook flips `account_type` to `pro`.
- `account_type` + `projects_created_this_month` + `project_limit_reset_at` on `users` table.

### Contract / Commitment System
At project creation, owner picks: `commitment` / `nda` / `both` / `none`.
- Custom terms supported.
- Members sign via in-app signature (typed name or drawn canvas → SHA-256 hash stored).
- Provider-agnostic: `ESIGNATURE_PROVIDER=none` default (in-app); swap to Documenso (free, self-hostable) later.
- Enforcement: leaving a project with an active commitment contract → `rate` drops + 7-day re-join restriction.
- NDA template = Phase 2. Real provider integration = Phase 2.

### Professor / TA Dashboard
New page at `/admin/dashboard`, gated by `user_type IN ('professor', 'ta')`.
- Different from the system-admin Electron panel at `F:\connexio-adminPanel`.
- Shows: course list, per-project risk overview (🟢🟡🔴), student performance table, contribution evidence drill-down.
- New `professorMiddleware.js` + `professor.controller.js`.

### Idea Marketplace
Page at `/ideas` and `/ideas/:id`. Public platform-wide.
- AI skill-matching: score each idea against current user's profile.
- RAG feasibility + market validation via new MasarX `validate_idea` intent.
- Team-formation preview: who joined, skill breakdown, role gaps.
- **No one-click convert-to-project** (user creates project manually, then links).
- Tables: `project_ideas`, `idea_members`.

### Skill Gap Analysis
- Profile widget: top 5 gaps (skills used in projects but not in profile).
- Full page: `/profile/skills/analysis`.
- Learning links: roadmap.sh (free, MIT).
- Sources: declared skills + endorsed skills (MasarX) + task history + project tech stacks.

---

## 7. Features Removed / Deferred

| Feature | Decision |
|---------|----------|
| Showcase page | Removed — integrated into Profile (`/@username` routing) |
| Testimonials | Deferred — post-launch |
| Achievement/badge system | Deferred — post-launch |
| Monetization / payments | Deferred except Stripe Pro upgrade (active) |
| Hackathons | Deferred — Plan C |
| Vercel/Netlify auto-deploy | Deferred — Plan C |
| Project templates | Deferred — Plan C |
| Web push (VAPID) | Removed — mobile push only via OneSignal |
| Gantt / Kanban toggle | Deferred |
| Developer experience (hot reload, .env sync) | Deferred — Plan D low priority |
| Backend tests | Deferred — Plan B |
| Org account LMS features | Phase 2+ — only `account_type='org'` field added now |

---

## 8. Code Conventions

### Backend (Node.js)
- **Response format:** `res.json({ success: true, data: { ... } })` / `res.status(N).json({ success: false, message: '...' })`. Use `responseHandler.js` helpers.
- **Query pattern:** Always `const { rows } = await query('...', [params])`. Use `$1,$2` placeholder style for new queries — the helper converts them to `?`.
- **Column names:** Case-sensitive as defined in `dbconnection.js`. `UID`, `PID`, `taskID`, `PName`, `FullName`, `TaskDesc`.
- **Joins over N+1:** Always use JOINs, never query in loops.
- **No multi-statement SQL in `pool.execute()`** — split into separate `query()` calls.
- **New routes:** register in `bootstrap.js` under the correct prefix.
- **Migration pattern:** add idempotent `ALTER TABLE` blocks inside `createTables()` in `dbconnection.js`, wrapped in `try { ... } catch (_) {}`.
- **Timestamps:** always UTC (`new Date().toISOString()`). Frontend converts to local for display.

### Frontend (React)
- **Dark mode:** every new component must have `dark:` Tailwind variants.
- **i18n:** every user-facing string must use `const { t } = useAppContext()` with keys in `AppContext.jsx` (both `en` and `ar`).
- **Shared components:** use `src/components/shared/` library (`<Skeleton>`, `<ErrorBoundary>`, `<EmptyState>`, `<ConfirmDialog>`, `<DataTable>`, `<Avatar>`, `<Badge>`).
- **API calls:** import from `src/api/axiosInstance.js` (JWT interceptor included).
- **Provider order:** AppProvider → AuthProvider → BrowserRouter (never change this).
- **401 redirect:** `window.location.href = '/login'` (not React Router navigate).
- **Tailwind content:** `tailwind.config.js` must include all `src/**/*.{js,jsx,ts,tsx}` — extended in Phase 1.

### RAG (Python)
- All context injection goes through `NLPController._prepare_chat_context()`.
- Session key format: `{project_id}_{user_id}` (unified across @mention and AI Chat page).
- Token budget: 8000 for project-context queries.
- GITHUB_TOKEN needed for L4 (recent commits) context injection.

### MasarX (Python)
- All new intents need routing in `WorkflowController.py` and a subgraph entry.
- MasarX must NOT run `create_all` for `chunks` or `projects` (Connexios owns those).

---

## 9. Environment Variables — What You Need

### Keys you need to obtain / set up

| Variable | Where | How to get |
|----------|-------|-----------|
| `STRIPE_SECRET_KEY` | `connexio_back2/.env` | stripe.com → Dashboard → API keys (test mode is free) |
| `STRIPE_WEBHOOK_SECRET` | `connexio_back2/.env` | `stripe listen --forward-to localhost:3000/api/payments/webhook` |
| `STRIPE_PRO_PRICE_ID` | `connexio_back2/.env` | Create a $20/mo recurring price in Stripe Dashboard |
| `GITHUB_TOKEN` | `Connexios/src/.env` | github.com → Settings → Developer Settings → PAT (read:repo scope) |
| `ONESIGNAL_APP_ID` | Mobile `.env` | onesignal.com (free) — Phase 5 only |
| `ONESIGNAL_API_KEY` | Mobile `.env` | Same — Phase 5 only |
| `ESIGNATURE_PROVIDER` | `connexio_back2/.env` | Set to `none` for now (in-app signing) |

### Already set (do not need to change)
`JWT_SECRET`, `CONNEXIO_INTERNAL_API_KEY`, `GROQ_API_KEY`, `DB_HOST/USER/PASSWORD/NAME`, `MONGODB_URI`, `CLOUDINARY_*`, `VAPID_*` (removed — no longer needed).

### HF Spaces secrets to update
When deploying changes to HF Spaces:
- **ConnexioRag:** add `GITHUB_TOKEN` for L4 context injection (Phase 2).
- **ConnexioAgent:** no new secrets for Phase 0-1.

---

## 10. RAG System Detail

### Tiered Response Strategy
| Tier | Condition | Model | Cost |
|------|-----------|-------|------|
| 0 | `OUT_OF_SCOPE` | None — canned string | 0 tokens |
| 1 | `project_id is None` | `utility_client` (8B) + 12-tok system | ~80–150 tokens |
| 2 | `project_id` set | `generation_client` (70B) + full RAG prompt | ~300–800 tokens |

### Smart Context Layers (Phases 1–2)
| Layer | Data | Phase |
|-------|------|-------|
| L1 | Project profile (name, description, tech stack, phase, GitHub URL) | 1 |
| L2 | Active tasks (open/in-progress, recent completions) | 1 |
| L3 | Recent chat summary (last 5 messages) | 1 |
| L4 | Recent commits from GitHub (requires `GITHUB_TOKEN`) | 2 |
| L5 | MasarX audit snapshot (task health, risk level) | 2 |

### Shortcut Commands (Phase 3)
`/summary`, `/tasks`, `/blame`, `/docs`, `/audit` — handled in `NLPController.py` before intent detection.

### Module Map
```
src/
├── main.py                  # Startup: DB + LLM clients + VectorDB + BackendApiClient
├── celery_app.py            # 4 queues + beat schedule
├── Routes/
│   ├── base.py              # /health
│   ├── data.py              # upload/process [X-API-Key]
│   ├── projects.py          # /sync [X-API-Key]
│   ├── nlp.py               # embed/search [X-API-Key]
│   └── agent.py             # /chat/{pid}, /stream/{pid} [X-API-Key]
├── controllers/
│   ├── NLPController.py     # Core RAG orchestration (CRAG, streaming, context injection)
│   ├── WorkflowController.py # Intent + language detection, relevance grading
│   └── helpers/
│       ├── ToolManager.py   # Wikipedia, Google, GitHub, Python, KB search
│       └── TraceManager.py  # JSON trace per request
├── stores/
│   ├── llm/providers/       # OpenAIProvider, GroqProvider, CoHereProvider
│   └── vectordb/providers/  # QdrantDBProvider, PGVectorProvider
├── utils/
│   ├── security.py          # verify_api_key FastAPI dependency
│   └── backend_client.py    # REST to Node.js (5-min cache for stable data)
└── helpers/config.py        # Pydantic Settings (loads src/.env)
```

---

## 11. MasarX System Detail

### 7 Subgraphs + New Intents
| Subgraph | Intents |
|----------|---------|
| `task_subgraph.py` | `create_tasks` (HITL) |
| `team_subgraph.py` | `match_team` (enhanced Phase 0), `onboard_member`, `refine_recommender` |
| `doc_subgraph.py` | `generate_readme`, `generate_retro`, `generate_milestone_doc`, `scaffold_repo` |
| `monitor_subgraph.py` | `detect_risks` (enhanced Phase 0), `monitor_workload` |
| `pr_translator_subgraph.py` | `translate_pr`, `review_pr` |
| `skill_endorsement_subgraph.py` | `endorse_skills`, `recommend_skills` |
| `audit_subgraph.py` | `comprehensive_audit` |
| **NEW Phase 3** | `validate_idea` (idea marketplace feasibility), `preview_team` (team formation preview) |

### Event → Intent Map
| Event | Intent |
|-------|--------|
| `project.created` | `scaffold_repo` |
| `user.joined_platform` | `match_team` |
| `user.joined_project` | `onboard_member` |
| `project.sprint_started` | `create_tasks` |
| `task.completed` | `endorse_skills` |
| `sprint.closed` | `generate_retro` |
| `milestone.completed` | `generate_milestone_doc` |
| `pullrequest.merged` | `review_pr` |
| `project.closed` | `generate_readme` |

---

## 12. Risk Register

| Risk | Mitigation |
|------|-----------|
| B30 Socket.IO @mention — breaks all chat | Feature flag `AI_TRIGGER_ENABLED=false`. Test isolated before flipping. |
| B18 JWT invalidation — locks out all users | Implement last in Phase 2. Test with 2 concurrent users. |
| Stripe webhook misconfiguration | Use `stripe listen` locally + verify signature on every webhook |
| Contract enforcement race condition | Always check `project_contracts` before `project_members` delete |
| Org account scope creep | Phase 2+ only. Only `account_type='org'` field added in Phase 0. |
| Token budget overflow (L1-L5) | Log token usage; truncate L3 (chat history) first if over budget |

---

## 13. How to Keep This File Updated

After completing **every item or phase**:
1. Update the Phase 0 checklist (check off completed items).
2. Update the Phase status table (change 🔄/⏳ to ✅).
3. Update the "Last updated" line at the top.
4. If a new table was created, add it to §3.
5. If a new env var is needed, add it to §9.
6. If a feature was added/removed/deferred, update §6 or §7.

The goal: any fresh Claude session reading only this file should be able to understand the current state of the platform without reading all the plan files.
