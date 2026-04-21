# Fix Database Schema Mismatch

The FastAPI application is failing because the `projects` table in the database is missing columns (`project_name` and `progress`) that are present in the SQLAlchemy model. The initial migration script was incomplete.

## Proposed Changes

### 1. Database Migration

I will create a second migration script to add the missing columns to the `projects` table.

#### [NEW] 2026_04_20_add_project_name_and_progress.py
- Add `project_name` (String) and `progress` (Integer) columns to the `projects` table.
- Update the revision ID and down-revision.

### 2. Execution

I will then run the migration inside the Docker environment.

## User Review Required

> [!IMPORTANT]
> **Database Inconsistency:** The initial migration was missing these columns. Applying this fix will align the database with the code.
> 
> You will need to rebuild and restart the container to apply this:
> ```bash
> docker compose build fastapi
> docker compose up -d fastapi
> ```

## Verification Plan

### Automated Tests
1. After the migration, the `fastapi` logs should show:
   `[AGENT] Database tables initialized or already exist.`
   And the server should start without the `UndefinedColumnError`.

### Manual Verification
- Verify in DBeaver that the `projects` table now contains the `project_name` and `progress` columns.
