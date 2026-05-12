# 🎬 Step-by-Step Execution Guide for Your Colleague

**Tell your colleague:** "Follow these exact steps to get PostgreSQL + pgvector + Alembic working in 20 minutes."

---

## ⏱️ Total Time: ~20 minutes

---

## 📍 Phase 1: Project Setup (5 min)

### Step 1.1: Create Project Structure

```bash
# Create directory structure
mkdir -p my_new_project/src/models/db_schemas/schemas
mkdir -p my_new_project/src/helpers
mkdir -p my_new_project/docker
mkdir -p my_new_project/src/models/db_schemas/alembic/versions

# Navigate to project
cd my_new_project
```

### Step 1.2: Create .env File

**File:** `src/.env`

```env
APP_NAME="MyNewProject"
APP_VERSION="0.1"

# Database
POSTGRES_USERNAME="postgres"
POSTGRES_PASSWORD="postgres123"
POSTGRES_HOST="localhost"
POSTGRES_PORT=5432
POSTGRES_MAIN_DATABASE="my_project_db"

# Vector DB
VECTOR_DB_BACKEND="PGVECTOR"
VECTOR_DB_PGVEC_INDEX_THRESHOLD=400
```

### Step 1.3: Create requirements.txt

**File:** `src/requirements.txt`

```txt
fastapi>=0.115.0
uvicorn[standard]==0.31.1
python-dotenv==1.0.1
pydantic-settings==2.12.0
SQLAlchemy==2.0.49
asyncpg==0.30.0
alembic==1.18.4
psycopg2-binary==2.9.11
pgvector==0.1.3
```

### Step 1.4: Install Dependencies

```bash
pip install -r src/requirements.txt
```

---

## 📍 Phase 2: SQLAlchemy Models (5 min)

### Step 2.1: Create Base Class

**File:** `src/models/db_schemas/schemas/connexio_base.py`

```python
from sqlalchemy.ext.declarative import declarative_base

SQLAlchemyBase = declarative_base()
```

### Step 2.2: Create Project Model

**File:** `src/models/db_schemas/schemas/project.py`

```python
from .connexio_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, DateTime, func, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid


class Project(SQLAlchemyBase):
    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True, autoincrement=True)
    project_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    project_name = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    documents = relationship("Document", back_populates="project")

    __table_args__ = (
        Index('ix_project_uuid', project_uuid),
    )
```

### Step 2.3: Create Document Model (With Vector)

**File:** `src/models/db_schemas/schemas/document.py`

```python
from .connexio_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, DateTime, func, String, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, Vector
from sqlalchemy.orm import relationship
import uuid


class Document(SQLAlchemyBase):
    __tablename__ = "documents"

    doc_id = Column(Integer, primary_key=True, autoincrement=True)
    doc_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    doc_title = Column(String(255), nullable=False)
    doc_content = Column(Text, nullable=False)
    
    # Vector embedding (1024 dimensions)
    doc_embedding = Column(Vector(1024), nullable=True)

    # Foreign key
    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationship
    project = relationship("Project", back_populates="documents")

    __table_args__ = (
        Index('ix_doc_project_id', project_id),
        Index('ix_doc_uuid', doc_uuid),
    )
```

### Step 2.4: Create Models __init__.py

**File:** `src/models/db_schemas/schemas/__init__.py`

```python
from .connexio_base import SQLAlchemyBase
from .project import Project
from .document import Document

__all__ = [
    "SQLAlchemyBase",
    "Project",
    "Document",
]
```

---

## 📍 Phase 3: Alembic Configuration (5 min)

### Step 3.1: Create alembic.ini

**File:** `src/models/db_schemas/alembic.ini`

```ini
[alembic]
script_location = %(here)s/alembic
prepend_sys_path = .
revision_environment = false
truncate_slug_length = 40
recursive_version_locations = false
output_encoding = utf-8
sqlalchemy.url = postgresql://postgres:postgres123@localhost:5432/my_project_db
```

⚠️ **UPDATE THIS LINE**: `sqlalchemy.url = postgresql://postgres:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT/YOUR_DB`

### Step 3.2: Create alembic/env.py

**File:** `src/models/db_schemas/alembic/env.py`

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from schemas import SQLAlchemyBase
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLAlchemyBase.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Step 3.3: Create alembic/script.py.mako

**File:** `src/models/db_schemas/alembic/script.py.mako`

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

---

## 📍 Phase 4: Docker Setup (3 min)

### Step 4.1: Create docker-compose.yml

**File:** `docker/docker-compose.yml`

```yaml
version: '3.8'

services:
  pgvector:
    image: pgvector/pgvector:pg16
    container_name: pgvector_db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres123
      POSTGRES_DB: my_project_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  postgres_data:
```

### Step 4.2: Start PostgreSQL

```bash
# Navigate to docker directory
cd docker

# Start PostgreSQL container
docker-compose up -d pgvector

# Verify it's running
docker-compose ps

# Check logs
docker-compose logs pgvector
```

**Expected output:**
```
pgvector_db     pgvector/pgvector:pg16   ...   Up (healthy)
```

---

## 📍 Phase 5: Generate & Run Migrations (2 min)

### Step 5.1: Generate Initial Migration

```bash
# Navigate to alembic directory
cd ../src/models/db_schemas

# Generate migration from models
alembic revision --autogenerate -m "initial_commit"
```

**Expected output:**
```
Generating /app/alembic/versions/2c957a9b6777_initial_commit.py ... done
```

### Step 5.2: Review Generated Migration

```bash
# Look at the generated migration file
cat alembic/versions/*_initial_commit.py
```

**Expected content:**
- `CREATE TABLE projects (...)`
- `CREATE TABLE documents (...)`
- `CREATE EXTENSION vector` (if pgvector is recognized)

### Step 5.3: Apply Migration

```bash
# Run all pending migrations
alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.migration] Context impl PostgresqlImpl.
INFO  [alembic.migration] Will assume transactional DDL is supported by the backend
INFO  [alembic.migration] Running upgrade  -> 2c957a9b6777, initial_commit
```

### Step 5.4: Verify Tables Created

```bash
# Connect to database
psql -U postgres -h localhost -d my_project_db

# List tables
\dt

# See table structure
\d documents

# See vector column
SELECT column_name, data_type FROM information_schema.columns WHERE table_name='documents';

# Exit
\q
```

**Expected output:**
```
List of relations
 Schema |    Name    | Type  | Owner
--------+------------+-------+----------
 public | documents  | table | postgres
 public | projects   | table | postgres
(2 rows)
```

---

## 📍 Phase 6: Create FastAPI App (optional, 2 min)

### Step 6.1: Create main.py

**File:** `src/main.py`

```python
from fastapi import FastAPI
from helpers.config import get_settings

app = FastAPI(title="My Project API")

settings = get_settings()


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "database": f"{settings.POSTGRES_MAIN_DATABASE}",
        "vector_db": settings.VECTOR_DB_BACKEND
    }


@app.post("/projects")
def create_project(name: str):
    return {
        "project_name": name,
        "message": "Project created successfully"
    }
```

### Step 6.2: Create helpers/config.py

**File:** `src/helpers/config.py`

```python
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

### Step 6.3: Create helpers/__init__.py

**File:** `src/helpers/__init__.py`

```python
# Helpers package
```

### Step 6.4: Start API Server

```bash
# From src directory
cd ..

# Start server
uvicorn main:app --reload

# Test health endpoint
curl http://localhost:8000/health
```

**Expected output:**
```json
{
  "status": "healthy",
  "database": "my_project_db",
  "vector_db": "PGVECTOR"
}
```

---

## 🎯 Verification Checklist

```bash
# ✅ 1. Database running
docker-compose ps
# Should show pgvector_db as "Up (healthy)"

# ✅ 2. Tables created
psql -U postgres -h localhost -d my_project_db -c "\dt"
# Should list "projects" and "documents"

# ✅ 3. Vector extension installed
psql -U postgres -h localhost -d my_project_db -c "SELECT * FROM pg_extension WHERE extname='vector';"
# Should show vector extension

# ✅ 4. API responding
curl http://localhost:8000/health
# Should return JSON with status "healthy"

# ✅ 5. Alembic tracking migrations
cd src/models/db_schemas
alembic current
# Should show current revision

alembic history
# Should show migration history
```

---

## 🚨 Troubleshooting

### ❌ Problem: "psycopg2.OperationalError: connection refused"

**Solution:**
```bash
# Check if PostgreSQL is running
docker-compose ps

# If not running, start it
docker-compose up -d pgvector

# Wait 10 seconds for health check to pass
sleep 10

# Try migration again
alembic upgrade head
```

### ❌ Problem: "ModuleNotFoundError: No module named 'schemas'"

**Solution:**
```bash
# Make sure you're in the correct directory for alembic
cd src/models/db_schemas

# Or update env.py import path to:
from schemas import SQLAlchemyBase  # Relative import
```

### ❌ Problem: "Target database is not up to date"

**Solution:**
```bash
# Check current revision
alembic current

# Upgrade to head
alembic upgrade head

# Or downgrade and try again
alembic downgrade -1
alembic upgrade head
```

### ❌ Problem: Vector extension not found

**Solution:**
```sql
-- Connect to database
psql -U postgres -h localhost -d my_project_db

-- Create extension manually
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT * FROM pg_extension WHERE extname='vector';

-- Exit
\q
```

---

## 📝 Next Steps After Setup

1. **Define more models** following the Document and Project patterns
2. **Create FastAPI routes** for CRUD operations
3. **Implement vector search** queries with pgvector
4. **Setup database session** management for connections
5. **Add data validation** with Pydantic models
6. **Implement authentication** for API endpoints

---

## 🔗 Quick Command Reference

```bash
# Generate new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# See current migration
alembic current

# Connect to database
psql -U postgres -h localhost -d my_project_db

# Start server
uvicorn main:app --reload

# Stop PostgreSQL
docker-compose down

# View PostgreSQL logs
docker-compose logs pgvector
```

---

## ✅ Success Criteria

Your setup is complete when:

- [ ] PostgreSQL container running with pgvector extension
- [ ] `projects` and `documents` tables created in database
- [ ] `alembic current` shows the initial migration applied
- [ ] FastAPI server responds to `/health` endpoint
- [ ] Vector column exists in documents table (1024 dimensions)

---

**🎉 That's it! You're ready to build your app with PostgreSQL + pgvector + Alembic!**

---

## 📞 Still Stuck?

Check these reference documents:
1. `SETUP_GUIDE_FOR_NEW_PROJECT.md` - Comprehensive guide
2. `QUICK_REFERENCE_WHAT_TO_COPY.md` - File locations in Connexios
3. `COPY_PASTE_TEMPLATES.md` - Ready-to-use code snippets
