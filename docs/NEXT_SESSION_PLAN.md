# Next Session — Execution Plan

## What to tell me next session

> "Continue the plan from where we left off. Execute the MasarX integration phases."

## Execution Order

### Phase 1: Database Stabilization (I do — 1h)
Fix the 3 separate DB connection pools to Neon. Share engine between MasarX `db_tool` and app state.

**Files**: `F:\MasarX_A\src\utils\tools\db_tool.py`, `F:\MasarX_A\src\main.py`

### Phase 2: Schema Ownership (I do — 2h)
Create `masarx_webhook_results` table, stop MasarX writing to RAG's `chunks` table.

**Files**: `F:\MasarX_A\src\models\db_schemas\live_models.py`, `F:\MasarX_A\src\utils\tools\db_tool.py`, `F:\MasarX_A\src\Routes\webhook_routes.py`

### Phase 3: REST Bridge (I do — 3h)
Create `MasarxApiClient` in RAG so RAG can read tasks and notifications from MasarX's DB.

**Files**: RAG new `src/utils/masarx_client.py`, RAG `helpers/config.py`, RAG `controllers/helpers/ToolManager.py`

### Phases 4-10: Backend + Frontend
I will write comprehensive specs (already started), NOT execute them. Your teammates implement:

- **Backend teammate**: model_tier passthrough, streaming socket events, health endpoint, caching
- **Frontend teammate**: source badges, markdown fix, typing indicator

## What your teammates need

File `F:\Connexio_Frontend2\docs\RAG_INTEGRATION_SPECS.md` contains all specs.
Share it with them — everything is documented with why, what, and how.

## After all phases complete

I run the full test suite to verify everything works end-to-end.
