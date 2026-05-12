# 🔍 MasarX_A Database Environment - Missing Components Analysis

**Analysis Date:** May 3, 2026  
**Source Project:** f:\MasarX_A  
**Reference Project:** Connexios  

---

## 📊 Executive Summary

✅ **What MasarX_A Already Has:**
- Alembic setup and basic configuration
- PostgreSQL + pgvector Docker service
- SQLAlchemy models (using live_models.py)
- Celery + RabbitMQ + Redis infrastructure
- FastAPI with entrypoint script

❌ **What MasarX_A Is Missing:**
- **Proper database schema directory structure** (not organized like Connexios)
- **SQLAlchemy base class separation** (Base is defined inside live_models.py instead of connexio_base.py)
- **Alembic database URL configuration** (not set in alembic.ini)
- **Schemas subdirectory** (individual model files, not all in one file)
- **PostgreSQL configuration in .env** (only SQLite + mock setup for development)
- **Database initialization and migration scripts** in entrypoint
- **pgvector extension creation** in first migration
- **Proper environment files structure** (docker/env/ not properly documented)
- **Connection pooling and async session management**

---

## 🗂️ What Needs to Be Built

### 1️⃣ Directory Structure - MISSING

**Current Structure:**
```
src/
├── models/
│   └── db_schemas/
│       ├── connexio_models.py      ❌ All models in one file
│       ├── live_models.py          ❌ All models in one file
│       ├── mock_models.py          ❌ Mock/test models mixed
│       └── seed_data.py
```

**Needed Structure (Like Connexios):**
```
src/
├── models/
│   ├── db_schemas/
│   │   ├── connexio/                ⭐ MISSING - Production models
│   │   │   ├── alembic.ini
│   │   │   ├── alembic/
│   │   │   │   ├── env.py
│   │   │   │   ├── script.py.mako
│   │   │   │   └── versions/
│   │   │   └── schemas/
│   │   │       ├── __init__.py
│   │   │       ├── connexio_base.py
│   │   │       ├── project.py
│   │   │       ├── task.py
│   │   │       ├── user.py
│   │   │       └── ... (other models)
│   │   ├── mock/                    ⭐ MISSING - Test models directory
│   │   │   └── mock_models.py
│   │   └── live_models.py           (can be kept or archived)
```

**Action:** Create subdirectory structure to separate production PostgreSQL migrations from mock/test data

---

### 2️⃣ SQLAlchemy Base Class - NEEDS REFACTORING

**Current State (❌ NOT IDEAL):**
```python
# File: src/models/db_schemas/live_models.py
Base = declarative_base()

class User(Base):
    ...

class Project(Base):
    ...

# All models mixed in one 500+ line file
```

**Needed State (✅ CONNEXIOS PATTERN):**
```python
# File: src/models/db_schemas/connexio/schemas/connexio_base.py
from sqlalchemy.ext.declarative import declarative_base

SQLAlchemyBase = declarative_base()
```

```python
# File: src/models/db_schemas/connexio/schemas/user.py
from .connexio_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship

class User(SQLAlchemyBase):
    __tablename__ = "user"
    # ... model definition
```

**Action:** 
1. Create `connexio_base.py` with `SQLAlchemyBase = declarative_base()`
2. Split models into individual files: `user.py`, `project.py`, `task.py`, etc.
3. Update all model files to import from `connexio_base.py`

---

### 3️⃣ Alembic Configuration - INCOMPLETE

**Current State (❌ INCOMPLETE):**
```ini
# src/alembic.ini
sqlalchemy.url = # ❌ NOT CONFIGURED
# Just has template values, no actual database URL
```

**Needed State (✅ CONFIGURED):**
```ini
# src/models/db_schemas/connexio/alembic.ini
sqlalchemy.url = postgresql+asyncpg://postgres:password@localhost:5432/masarx
```

**Action:** 
1. Create `src/models/db_schemas/connexio/alembic.ini`
2. Set `sqlalchemy.url` to PostgreSQL connection string
3. Point `script_location` to `%(here)s/alembic`

---

### 4️⃣ Alembic env.py - NEEDS UPDATE

**Current State (❌ PARTIAL):**
```python
# src/alembic/env.py
from config.config import get_settings
from models.db_schemas.live_models import Base  # ❌ Wrong path structure

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.POSTGRES_URL)
```

**Needed State (✅ CORRECT):**
```python
# src/models/db_schemas/connexio/alembic/env.py
from schemas import SQLAlchemyBase  # ✅ Relative import from schemas/

target_metadata = SQLAlchemyBase.metadata
```

**Action:**
1. Move alembic to `src/models/db_schemas/connexio/alembic/`
2. Update imports to use local `schemas` module
3. Update import to reference `SQLAlchemyBase` instead of `Base`

---

### 5️⃣ PostgreSQL .env Variables - NEEDS UPDATES

**Current State (❌ INCOMPLETE):**
```env
# src/.env - Only has SQLITE for mock
SQLITE_DB_PATH="masarx_mock.db"

# .env has POSTGRES_URL but not broken down
POSTGRES_URL="postgresql+asyncpg://postgres:123456@localhost:5432/masarx"
PGVECTOR_URL="postgresql+asyncpg://postgres:123456@localhost:5432/masarx"
```

**Needed State (✅ CONNEXIOS PATTERN):**
```env
# src/.env - Broken down like Connexios
POSTGRES_USERNAME="postgres"
POSTGRES_PASSWORD="123456"
POSTGRES_HOST="localhost"
POSTGRES_PORT=5432
POSTGRES_MAIN_DATABASE="masarx"

# Also keep for reference
POSTGRES_URL="postgresql+asyncpg://${POSTGRES_USERNAME}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_MAIN_DATABASE}"

# Vector DB Config
VECTOR_DB_BACKEND="PGVECTOR"
VECTOR_DB_PGVEC_INDEX_THRESHOLD=400
EMBEDDING_MODEL_SIZE=1024
```

**Action:** 
1. Add individual POSTGRES_* variables to `.env`
2. Add VECTOR_DB_* variables
3. Ensure docker/env/.env.postgres has matching values

---

### 6️⃣ Docker Environment Files - NEEDS STRUCTURE

**Current State (❌ NOT DOCUMENTED):**
```
docker/env/          # Exists but not documented
├── .env.app
├── .env.postgres
└── (other env files?)
```

**Needed State (✅ DOCUMENTED):**
```env
# docker/env/.env.app
APP_NAME="MasarX"
POSTGRES_HOST="postgres"          # Service name in docker-compose
POSTGRES_PORT=5432
POSTGRES_MAIN_DATABASE="masarx"
POSTGRES_USERNAME="postgres"
POSTGRES_PASSWORD="masarx_password"
# ... other variables

# docker/env/.env.postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=masarx_password
POSTGRES_DB=masarx
```

**Action:**
1. Create/update `docker/env/.env.app` with PostgreSQL configuration
2. Create/update `docker/env/.env.postgres` with database initialization
3. Ensure docker-compose.yml references these files

---

### 7️⃣ Database Initialization - MISSING

**Current State (❌ NO AUTO-MIGRATION IN DOCKER):**
- Dockerfile doesn't run alembic migrations
- Entrypoint doesn't check/create database
- PostgreSQL container starts but tables aren't created

**Needed State (✅ AUTO-MIGRATION):**

**File:** `docker/entrypoint.sh` (UPDATE)

```bash
#!/bin/bash

# Wait for PostgreSQL to be ready
until pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USERNAME; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done

# Create pgvector extension
psql -h $POSTGRES_HOST -U $POSTGRES_USERNAME -d $POSTGRES_MAIN_DATABASE << EOF
CREATE EXTENSION IF NOT EXISTS vector;
EOF

# Run alembic migrations
cd /app/models/db_schemas/connexio
alembic upgrade head

# Start application
cd /app
exec "$@"
```

**Action:**
1. Update entrypoint.sh to run alembic migrations
2. Add pgvector extension creation
3. Ensure it waits for PostgreSQL before running migrations

---

### 8️⃣ Vector Search Models - MISSING

**Current State (❌ NO VECTOR COLUMNS):**
```python
class DataChunk(Base):  # ❌ Doesn't exist in live_models.py
    # No vector embeddings
```

**Needed State (✅ WITH VECTOR SUPPORT):**
```python
# src/models/db_schemas/connexio/schemas/data_chunk.py
from sqlalchemy.dialects.postgresql import Vector

class DataChunk(SQLAlchemyBase):
    __tablename__ = "chunks"
    
    chunk_id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_text = Column(String, nullable=False)
    chunk_embedding = Column(Vector(1024), nullable=True)  # ⭐ pgvector
    project_id = Column(Integer, ForeignKey("projects.project_id"))
```

**Action:**
1. Create `data_chunk.py` with Vector column
2. Create other models: `asset.py`, `chat_session.py`, etc.
3. Update `__init__.py` to import all models

---

### 9️⃣ Migration History - NEEDS RESET

**Current State (❌ OLD MIGRATION):**
```
src/alembic/versions/
├── a3f669a46ba6_initial_schema.py  # For SQLite setup
└── (only 1 migration, targeting old structure)
```

**Needed State (✅ NEW MIGRATIONS):**
```
src/models/db_schemas/connexio/alembic/versions/
├── 2c957a9b6777_initial_commit.py      # Projects, Assets, Chunks
├── 9ffe01f2c665_add_pgvector_ext.py    # Vector extension
└── (future migrations follow)
```

**Action:**
1. Remove old migrations (they target SQLite)
2. Generate new migrations from PostgreSQL models
3. First migration should include pgvector extension creation

---

### 🔟 Config Helper - NEEDS REFACTORING

**Current State (❌ NOT USING .env PROPERLY):**
```python
# src/config/config.py
# Likely hardcoded or incomplete PostgreSQL config
```

**Needed State (✅ CONNEXIOS PATTERN):**
```python
# src/helpers/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_MAIN_DATABASE: str
    
    VECTOR_DB_BACKEND: str = "PGVECTOR"
    VECTOR_DB_PGVEC_INDEX_THRESHOLD: int = 100
    
    class Config:
        env_file = ".env"

def get_settings():
    return Settings()
```

**Action:**
1. Review/update `src/config/config.py`
2. Ensure it loads PostgreSQL variables from .env
3. Add vector database configuration

---

## 📋 Checklist: What to Build/Fix

### Phase 1: Directory Structure (30 min)
- [ ] Create `src/models/db_schemas/connexio/` directory
- [ ] Create `src/models/db_schemas/connexio/schemas/` directory
- [ ] Create `src/models/db_schemas/connexio/alembic/` directory (if not exists)
- [ ] Create `src/models/db_schemas/connexio/alembic/versions/` directory

### Phase 2: SQLAlchemy Models (1 hour)
- [ ] Create `connexio_base.py` with `SQLAlchemyBase = declarative_base()`
- [ ] Split models into individual files:
  - [ ] `user.py`
  - [ ] `project.py`
  - [ ] `task.py`
  - [ ] `data_chunk.py` (with Vector column)
  - [ ] `sprint.py`
  - [ ] `team_member.py`
  - [ ] Other models as needed
- [ ] Create `__init__.py` to import all models
- [ ] Update all models to import from `connexio_base.py`

### Phase 3: Alembic Configuration (30 min)
- [ ] Create `src/models/db_schemas/connexio/alembic.ini`
- [ ] Set `sqlalchemy.url` to PostgreSQL connection
- [ ] Move/update `alembic/env.py` to new location
- [ ] Update `env.py` imports to reference `schemas.SQLAlchemyBase`
- [ ] Copy `script.py.mako` template

### Phase 4: Environment Configuration (20 min)
- [ ] Update `src/.env` with individual POSTGRES_* variables
- [ ] Update/create `docker/env/.env.app` with PostgreSQL config
- [ ] Update/create `docker/env/.env.postgres` with database initialization
- [ ] Add VECTOR_DB_* variables

### Phase 5: Database Initialization (20 min)
- [ ] Update `docker/entrypoint.sh` to:
  - [ ] Wait for PostgreSQL
  - [ ] Create pgvector extension
  - [ ] Run alembic migrations
- [ ] Update `src/config/config.py` to load PostgreSQL config from .env

### Phase 6: Migrations (30 min)
- [ ] Delete old migrations from `src/alembic/versions/`
- [ ] Run `alembic revision --autogenerate -m "initial_commit"`
- [ ] Review generated migration in `src/models/db_schemas/connexio/alembic/versions/`
- [ ] Add `CREATE EXTENSION IF NOT EXISTS vector;` to first migration if not auto-generated

### Phase 7: Docker Updates (20 min)
- [ ] Verify `docker-compose.yml` pgvector service is configured
- [ ] Verify `Dockerfile` has `libpq-dev` installed
- [ ] Test `docker-compose up` and check migrations run automatically

### Phase 8: Testing (20 min)
- [ ] Start PostgreSQL: `docker-compose up -d postgres`
- [ ] Run migrations: `alembic upgrade head`
- [ ] Verify tables: `psql` and check `\dt`
- [ ] Verify vector extension: `SELECT * FROM pg_extension;`
- [ ] Start full stack: `docker-compose up`

---

## 📊 Summary Table: What's Where

| Component | Current Location | Needed Location | Status |
|-----------|-----------------|-----------------|--------|
| Base Class | `live_models.py` | `connexio/schemas/connexio_base.py` | ❌ Needs Move |
| Models | `live_models.py` (all in 1 file) | `connexio/schemas/*.py` (separate files) | ❌ Needs Split |
| Alembic Config | `src/alembic.ini` | `connexio/alembic.ini` | ⚠️ Needs Update |
| Alembic env.py | `src/alembic/env.py` | `connexio/alembic/env.py` | ⚠️ Needs Move |
| DB URL | `.env` (combined) | `.env` (broken down) | ⚠️ Needs Update |
| PostgreSQL Service | `docker-compose.yml` | ✅ Already Present | ✅ Ready |
| pgvector Extension | ❌ Missing | First alembic migration | ❌ Needs Add |
| Auto-Migration | ❌ Missing | `entrypoint.sh` | ❌ Needs Add |
| Vector Models | ❌ Missing | `data_chunk.py` | ❌ Needs Create |

---

## 🎯 Recommended Order

**Day 1 (1.5 hours):**
1. Create directory structure (30 min) - Phase 1
2. Split models into files (1 hour) - Phase 2

**Day 2 (1.5 hours):**
3. Configure Alembic (30 min) - Phase 3
4. Update environment files (20 min) - Phase 4
5. Update entrypoint (20 min) - Phase 5

**Day 3 (1 hour):**
6. Generate migrations (30 min) - Phase 6
7. Test everything (30 min) - Phase 7 + 8

---

## 🔗 Reference from Connexios

**Copy these exact structures from Connexios:**
- `src/models/db_schemas/connexio/schemas/connexio_base.py` → File pattern
- `src/models/db_schemas/connexio/schemas/*.py` → Model patterns
- `src/models/db_schemas/connexio/alembic.ini` → Configuration pattern
- `src/models/db_schemas/connexio/alembic/env.py` → Setup pattern
- `docker/connexio/entrypoint.sh` → Entry point pattern

**Use the guides in Connexios root:**
- `STEP_BY_STEP_EXECUTION_GUIDE.md` → Follow steps
- `COPY_PASTE_TEMPLATES.md` → Get exact code
- `QUICK_REFERENCE_WHAT_TO_COPY.md` → Find locations

---

## 💡 Key Points for Success

1. **Separate Concerns**: Keep test/mock models separate from production PostgreSQL models
2. **Base Class**: All models MUST inherit from `SQLAlchemyBase` (connexio_base.py)
3. **Individual Files**: Each model in its own file (easier to maintain and test)
4. **Vector Columns**: Use `Column(Vector(1024))` for embeddings matching your model size
5. **Migrations Auto-Run**: Entrypoint should run `alembic upgrade head` automatically
6. **Environment Files**: Keep postgres credentials in docker/env/ for security

---

**Total Time to Complete: ~3-4 hours**

---

## 📞 Questions?

Refer to:
- `SETUP_GUIDE_FOR_NEW_PROJECT.md` - Deep explanations
- `COPY_PASTE_TEMPLATES.md` - Ready-to-use code
- `QUICK_REFERENCE_WHAT_TO_COPY.md` - File locations in Connexios
