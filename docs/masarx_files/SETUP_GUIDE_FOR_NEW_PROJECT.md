# 🚀 PostgreSQL + pgvector + Alembic Setup Guide

**Reference Project:** Connexios Project Structure  
**Target:** Replicate database environment and table creation setup in a new project

---

## 📋 Overview

This guide walks through the complete setup for a FastAPI + PostgreSQL + pgvector + Alembic project. All referenced paths are from the **Connexios** project—use them as templates for your new project.

---

## 🎯 Key Components to Set Up

| Component | Location | Purpose |
|-----------|----------|---------|
| Environment Variables | `src/.env` | Database credentials & API keys |
| Python Dependencies | `src/requirements.txt` | Required packages (SQLAlchemy, alembic, pgvector, etc.) |
| SQLAlchemy Models | `src/models/db_schemas/connexio/schemas/` | Define database tables |
| Alembic Configuration | `src/models/db_schemas/connexio/alembic.ini` | Migration configuration |
| Alembic Environment | `src/models/db_schemas/connexio/alembic/env.py` | Database connection setup |
| Docker Setup | `docker/docker-compose.yml` | PostgreSQL + pgvector container |
| Dockerfile | `docker/connexio/Dockerfile` | Application container with alembic setup |

---

## 📝 STEP 1: Environment Configuration (.env)

**Reference:** `src/.env`

### What to include:

```env
# --- Application Settings ---
APP_NAME="YourProjectName"
APP_VERSION="0.1"

# --- Database Configuration (CRITICAL) ---
POSTGRES_USERNAME="postgres"
POSTGRES_PASSWORD="your_secure_password"
POSTGRES_HOST="172.17.80.1"  # Docker host IP (or localhost if local)
POSTGRES_PORT=5433           # Port mapping
POSTGRES_MAIN_DATABASE="your_db_name"

# --- Vector Database Config ---
VECTOR_DB_BACKEND="PGVECTOR"
VECTOR_DB_PGVEC_INDEX_THRESHOLD=400
```

### Key Points:
- **POSTGRES_HOST**: Use `172.17.80.1` for Docker host, or `localhost` for local PostgreSQL
- **POSTGRES_PORT**: Match the port from docker-compose (e.g., 5433 → 5432 in container)
- **VECTOR_DB_BACKEND**: Must be "PGVECTOR" for pgvector support

---

## 📦 STEP 2: Python Dependencies

**Reference:** `src/requirements.txt`

### Database & ORM Packages:

```txt
SQLAlchemy==2.0.49          # ORM framework
asyncpg==0.30.0             # Async PostgreSQL driver
alembic==1.18.4             # Database migrations
psycopg2-binary==2.9.11     # PostgreSQL client
pgvector==0.1.3             # pgvector Python support
```

### Why these versions?
- **SQLAlchemy 2.0.49**: Latest stable with SQLAlchemy 2.0 features
- **asyncpg**: High-performance async driver
- **alembic**: Latest stable migration tool
- **pgvector**: Provides Vector type for SQLAlchemy

---

## 🗄️ STEP 3: SQLAlchemy Models (Database Schemas)

**Reference Directory:** `src/models/db_schemas/connexio/schemas/`

### File Structure:

```
src/models/db_schemas/connexio/schemas/
├── __init__.py              # Import all models
├── connexio_base.py         # Base class for all models
├── project.py               # Projects table model
├── asset.py                 # Assets table model
├── data_chunk.py            # Data chunks table model
├── chat_session.py          # Chat sessions table model
├── celery_task_execution.py # Background task tracking
```

### Template: connexio_base.py

```python
from sqlalchemy.ext.declarative import declarative_base

SQLAlchemyBase = declarative_base()
```

### Template: Model File (e.g., data_chunk.py)

```python
from .connexio_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, DateTime, func, String, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, Vector
from sqlalchemy.orm import relationship
import uuid

class DataChunk(SQLAlchemyBase):
    __tablename__ = "chunks"

    chunk_id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    chunk_text = Column(String, nullable=False)
    chunk_metadata = Column(JSONB, nullable=True)
    chunk_order = Column(Integer, nullable=False)

    # Foreign keys
    chunk_project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    chunk_asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)

    # Vector embedding (pgvector)
    chunk_embedding = Column(Vector(1024), nullable=True)  # 1024-dim vector

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="chunks")
    asset = relationship("Asset", back_populates="chunks")

    # Indexes
    __table_args__ = (
        Index('ix_chunk_project_id', chunk_project_id),
        Index('ix_chunk_asset_id', chunk_asset_id),
    )
```

### Key Patterns:

| Feature | Example |
|---------|---------|
| UUID Primary Key | `Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)` |
| Vector Embedding | `Column(Vector(1024))` # pgvector column |
| JSON Data | `Column(JSONB, nullable=True)` |
| Foreign Keys | `Column(Integer, ForeignKey("table.column"))` |
| Auto Timestamp | `Column(DateTime(timezone=True), server_default=func.now())` |
| Relationships | `relationship("TableName", back_populates="...")` |
| Indexes | `__table_args__ = (Index('ix_name', column),)` |

---

## 🔄 STEP 4: Alembic Setup

### 4.1 Directory Structure

```
src/models/db_schemas/connexio/
├── alembic.ini              # ⭐ Alembic configuration
├── alembic/
│   ├── env.py               # ⭐ Database connection setup
│   ├── script.py.mako       # Migration template
│   ├── README               # Alembic README
│   └── versions/            # Migration files folder
│       ├── 2c957a9b6777_initial_commit.py
│       ├── 9ffe01f2c665_add_celery_table.py
│       └── ...
└── schemas/                 # SQLAlchemy models (from STEP 3)
```

### 4.2 alembic.ini Configuration

**Reference:** `docker/connexio/alembic.ini`

Key settings to update:

```ini
[alembic]
# Path to migration scripts (relative to alembic.ini location)
script_location = %(here)s/alembic

# Database URL - CRITICAL for migrations
sqlalchemy.url = postgresql://postgres:password@localhost:5432/your_db_name

# Optional: customize migration file naming
# file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s
```

### 4.3 alembic/env.py Setup

**Reference:** `src/models/db_schemas/connexio/alembic/env.py`

Key components:

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from schemas import SQLAlchemyBase  # ⭐ Import your models base
from alembic import context

config = context.config

# Set the target metadata from your models
target_metadata = SQLAlchemyBase.metadata

def run_migrations_offline() -> None:
    """Run migrations without creating a DB engine."""
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
    """Run migrations with a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

## 🐳 STEP 5: Docker Setup

### 5.1 docker-compose.yml

**Reference:** `docker/docker-compose.yml`

PostgreSQL + pgvector service:

```yaml
services:
  pgvector:
    image: pgvector/pgvector:pg16
    container_name: pgvector
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: 123456
      POSTGRES_DB: your_db_name
    ports:
      - "5433:5432"  # Host:Container
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:

networks:
  backend:
```

### 5.2 Dockerfile

**Reference:** `docker/connexio/Dockerfile`

```dockerfile
FROM ghcr.io/astral-sh/uv:0.11.7-python3.13-trixie

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY src/requirements.txt .
RUN uv pip install -r requirements.txt --system

COPY src/ .

# Create Alembic directory structure
RUN mkdir -p /app/models/db_schemas/

# Copy Alembic config and migration scripts
COPY docker/connexio/alembic.ini /app/models/db_schemas/connexio/alembic.ini

# Setup entrypoint
COPY docker/connexio/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 🛠️ STEP 6: Create Initial Migration

### Command to Generate Initial Migration:

```bash
# From the alembic directory
cd src/models/db_schemas/connexio

# Generate initial migration from models
alembic revision --autogenerate -m "initial_commit"

# Run migration
alembic upgrade head
```

### Expected Output:

Migration file created: `alembic/versions/2c957a9b6777_initial_commit.py`

Example content:
```python
def upgrade() -> None:
    """Create tables from models."""
    op.create_table('projects',
        sa.Column('project_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_uuid', sa.UUID(), nullable=False),
        # ... more columns
    )
    # More tables...

def downgrade() -> None:
    """Drop tables."""
    op.drop_table('projects')
    # ...
```

---

## 📋 STEP 7: Update Config Helper

**Reference:** `src/helpers/config.py`

Create settings class:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_MAIN_DATABASE: str

    # Vector DB
    VECTOR_DB_BACKEND: str  # "PGVECTOR"
    VECTOR_DB_PGVEC_INDEX_THRESHOLD: int = 100

    class Config:
        env_file = ".env"

def get_settings():
    return Settings()
```

---

## 🚀 STEP 8: Running Everything

### Local Development:

```bash
# 1. Create .env in src/
cp src/.env.example src/.env
# Edit src/.env with your credentials

# 2. Install dependencies
pip install -r src/requirements.txt

# 3. Start PostgreSQL locally or via Docker
docker-compose -f docker/docker-compose.yml up -d pgvector

# 4. Run migrations
cd src/models/db_schemas/connexio
alembic upgrade head

# 5. Start FastAPI
uvicorn src/main:app --reload
```

### Docker Compose (Production):

```bash
# Build and start all services
docker-compose -f docker/docker-compose.yml up --build

# View logs
docker-compose logs -f fastapi

# Stop services
docker-compose down
```

---

## 🔍 Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| **pgvector extension not found** | Add to migration: `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` |
| **Connection refused** | Check POSTGRES_HOST (localhost vs 172.17.80.1) and PORT mapping |
| **Alembic can't find models** | Ensure `from schemas import SQLAlchemyBase` path is correct in env.py |
| **Migration conflicts** | Check `alembic/versions/` for merge branches, use `alembic current` |
| **Vector dimension mismatch** | Ensure embedding models match Vector(dim) in schema (usually 1024) |

---

## 📚 File Reference Checklist

- [ ] `src/.env` - Environment variables configured
- [ ] `src/requirements.txt` - All dependencies added
- [ ] `src/models/db_schemas/connexio/schemas/__init__.py` - Models imported
- [ ] `src/models/db_schemas/connexio/schemas/connexio_base.py` - Base created
- [ ] `src/models/db_schemas/connexio/schemas/*.py` - All models defined
- [ ] `src/models/db_schemas/connexio/alembic.ini` - Database URL configured
- [ ] `src/models/db_schemas/connexio/alembic/env.py` - Connection setup done
- [ ] `docker/docker-compose.yml` - PostgreSQL service configured
- [ ] `docker/connexio/Dockerfile` - Alembic setup included
- [ ] Initial migration created and tested

---

## 🎯 Key Takeaways

1. **Models First**: Define all SQLAlchemy models in `schemas/` before migrations
2. **Alembic Config**: Update database URL in `alembic.ini` to match your environment
3. **pgvector Extension**: Add `CREATE EXTENSION IF NOT EXISTS vector` in first migration
4. **Vector Columns**: Use `Column(Vector(1024))` for embedding columns
5. **Migrations**: Always run `alembic upgrade head` before starting the app
6. **Docker Networking**: Use correct host IP for Docker containers

---

## 📞 Quick Commands Reference

```bash
# Generate migration from model changes
alembic revision --autogenerate -m "description"

# Apply all migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View current migration
alembic current

# View migration history
alembic history

# Create new empty migration
alembic revision -m "description"
```

---

**Last Updated:** May 3, 2026  
**Reference Project:** Connexios  
**Database:** PostgreSQL 16 + pgvector  
**ORM:** SQLAlchemy 2.0  
**Migration Tool:** Alembic 1.18
