# 📋 Copy-Paste Templates for Quick Setup

**Tell your colleague:** "Use these templates as starting points for your new project."

---

## 1️⃣ .env Template

**File:** `src/.env`

```env
# --- Application Settings ---
APP_NAME="YourProjectName"
APP_VERSION="0.1"
OPEN_API_KEY="sk-your-key"

# --- Database Configuration ---
POSTGRES_USERNAME="postgres"
POSTGRES_PASSWORD="secure_password_123"
POSTGRES_HOST="localhost"
POSTGRES_PORT=5432
POSTGRES_MAIN_DATABASE="your_project_db"

# --- Vector DB Configuration ---
VECTOR_DB_BACKEND="PGVECTOR"
VECTOR_DB_DISTANCE_METHOD="cosine"
VECTOR_DB_PGVEC_INDEX_THRESHOLD=400

# --- File Processing ---
FILE_ALLOWED_TYPES=["application/pdf","text/plain"]
FILE_MAX_SIZE=50
FILE_DEFAULT_CHUNK_SIZE=1024

# --- AI/LLM Configuration ---
EMBEDDING_MODEL_ID="bge-m3"
EMBEDDING_MODEL_SIZE=1024
GENERATION_MODEL_ID="gpt-3.5-turbo"
GENERATION_DEFAULT_MAX_TOKENS=512
GENERATION_DEFAULT_TEMPERATURE=0.1
TOTAL_CONTEXT_CHAR_BUDGET=15000

# --- Language ---
PRIMARY_LANG="en"
DEFAULT_LANG="en"
```

---

## 2️⃣ requirements.txt (DB Packages Only)

**File:** `src/requirements.txt`

```txt
# --- Core API & Web Server ---
fastapi>=0.115.0
uvicorn[standard]==0.31.1
python-dotenv==1.0.1
pydantic-settings==2.12.0

# --- Database & Persistence ---
SQLAlchemy==2.0.49
asyncpg==0.30.0
alembic==1.18.4
psycopg2-binary==2.9.11

# --- Vector Search ---
pgvector==0.1.3

# Add other dependencies as needed...
```

---

## 3️⃣ SQLAlchemy Base Class

**File:** `src/models/db_schemas/schemas/connexio_base.py`

```python
from sqlalchemy.ext.declarative import declarative_base

SQLAlchemyBase = declarative_base()
```

---

## 4️⃣ Model File Templates

### Template A: Simple Model (No Vectors)

**File:** `src/models/db_schemas/schemas/project.py`

```python
from .connexio_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, DateTime, func, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid


class Project(SQLAlchemyBase):
    __tablename__ = "projects"

    # Primary Key
    project_id = Column(Integer, primary_key=True, autoincrement=True)
    project_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)

    # Metadata
    project_name = Column(String(255), nullable=True)
    project_description = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    assets = relationship("Asset", back_populates="project")
    chunks = relationship("DataChunk", back_populates="project")

    # Indexes
    __table_args__ = (
        Index('ix_project_uuid', project_uuid),
    )
```

### Template B: Model With Vector Embeddings

**File:** `src/models/db_schemas/schemas/document.py`

```python
from .connexio_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, DateTime, func, String, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, Vector, JSONB
from sqlalchemy.orm import relationship
import uuid


class Document(SQLAlchemyBase):
    __tablename__ = "documents"

    # Primary Key
    doc_id = Column(Integer, primary_key=True, autoincrement=True)
    doc_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)

    # Content
    doc_title = Column(String(255), nullable=False)
    doc_content = Column(Text, nullable=False)
    doc_metadata = Column(JSONB, nullable=True)

    # Vector Embedding (1024-dimensional)
    doc_embedding = Column(Vector(1024), nullable=True)

    # Foreign Key
    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="documents")

    # Indexes
    __table_args__ = (
        Index('ix_doc_project_id', project_id),
        Index('ix_doc_uuid', doc_uuid),
    )
```

### Template C: Relationship Model (Many-to-One)

**File:** `src/models/db_schemas/schemas/asset.py`

```python
from .connexio_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, DateTime, func, String, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid


class Asset(SQLAlchemyBase):
    __tablename__ = "assets"

    # Primary Key
    asset_id = Column(Integer, primary_key=True, autoincrement=True)
    asset_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)

    # Properties
    asset_name = Column(String(255), nullable=False)
    asset_type = Column(String(50), nullable=False)  # e.g., "pdf", "text", "image"
    asset_size = Column(Integer, nullable=False)  # in bytes
    asset_config = Column(JSONB, nullable=True)  # store any metadata

    # Foreign Key
    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="assets")
    chunks = relationship("Chunk", back_populates="asset")

    # Indexes
    __table_args__ = (
        Index('ix_asset_project_id', project_id),
        Index('ix_asset_type', asset_type),
    )
```

---

## 5️⃣ Models __init__.py

**File:** `src/models/db_schemas/schemas/__init__.py`

```python
from .connexio_base import SQLAlchemyBase
from .project import Project
from .asset import Asset
from .document import Document

__all__ = [
    "SQLAlchemyBase",
    "Project",
    "Asset",
    "Document",
]
```

---

## 6️⃣ alembic.ini Configuration

**File:** `src/models/db_schemas/alembic.ini`

```ini
# A generic, single database configuration.

[alembic]
# path to migration scripts
script_location = %(here)s/alembic

# sys.path path, will be prepended to sys.path if present
prepend_sys_path = .

# set to 'true' to run the environment during
# the 'revision' command, regardless of autogenerate
revision_environment = false

# timezone to use when rendering the date
# leave blank for localtime
# timezone =

# max length of characters to apply to the "slug" field
truncate_slug_length = 40

# set to 'true' to search source files recursively
# in each "version_locations" directory
recursive_version_locations = false

# the output encoding used when revision files
# are written from script.py.mako
output_encoding = utf-8

# database URL
sqlalchemy.url = postgresql://postgres:secure_password_123@localhost:5432/your_project_db

[post_write_hooks]
# post_write_hooks defines scripts or Python functions that are run
# on newly generated revision scripts.

# format using "black" - use the console_scripts runner, against the "black" entrypoint
# hooks = black
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 79 REVISION_SCRIPT_FILENAME

# lint using "pylint" on the generated revision script
# hooks = pylint
# pylint.type = console_scripts
# pylint.entrypoint = pylint
# pylint.options = --disable=all --enable=E9,F63,F7,F82 REVISION_SCRIPT_FILENAME

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

---

## 7️⃣ alembic/env.py

**File:** `src/models/db_schemas/alembic/env.py`

```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

# Import your models base class
from schemas import SQLAlchemyBase

from alembic import context

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = SQLAlchemyBase.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine.
    """
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
    """Run migrations in 'online' mode.
    
    In this scenario we need to create an Engine and associate a connection.
    """
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

---

## 8️⃣ docker-compose.yml (PostgreSQL Service)

**File:** `docker/docker-compose.yml`

```yaml
version: '3.8'

services:
  # PostgreSQL with pgvector extension
  pgvector:
    image: pgvector/pgvector:pg16
    container_name: pgvector
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: secure_password_123
      POSTGRES_DB: your_project_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # FastAPI Application
  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: app
    ports:
      - "8000:8000"
    depends_on:
      pgvector:
        condition: service_healthy
    environment:
      - POSTGRES_HOST=pgvector
      - POSTGRES_PORT=5432
    env_file:
      - .env
    networks:
      - backend
    restart: unless-stopped

volumes:
  postgres_data:

networks:
  backend:
    driver: bridge
```

---

## 9️⃣ Dockerfile Template

**File:** `docker/Dockerfile`

```dockerfile
FROM ghcr.io/astral-sh/uv:0.11.7-python3.13-trixie

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY src/requirements.txt .
RUN uv pip install -r requirements.txt --system

# Copy application code
COPY src/ .

# Create Alembic directory structure
RUN mkdir -p /app/models/db_schemas/

# Copy Alembic configuration (if needed from docker directory)
# COPY docker/alembic.ini /app/models/db_schemas/alembic.ini

# Entrypoint
ENTRYPOINT ["uvicorn"]
CMD ["main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 🔟 config.py Helper

**File:** `src/helpers/config.py`

```python
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Application
    APP_NAME: str = "YourApp"
    APP_VERSION: str = "0.1"

    # Database Configuration
    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_MAIN_DATABASE: str

    # Vector Database
    VECTOR_DB_BACKEND: str = "PGVECTOR"
    VECTOR_DB_DISTANCE_METHOD: str = "cosine"
    VECTOR_DB_PGVEC_INDEX_THRESHOLD: int = 100

    # Embedding
    EMBEDDING_MODEL_ID: str | None = None
    EMBEDDING_MODEL_SIZE: int | None = 1024

    # Generation
    GENERATION_MODEL_ID: str | None = None
    GENERATION_DEFAULT_MAX_TOKENS: int | None = 512
    GENERATION_DEFAULT_TEMPERATURE: float | None = 0.1

    # Language
    PRIMARY_LANG: str = "en"
    DEFAULT_LANG: str = "en"

    class Config:
        env_file = ".env"


# Global instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

---

## 🛠️ Common Alembic Commands

```bash
# Navigate to alembic directory
cd src/models/db_schemas/

# Generate initial migration from models
alembic revision --autogenerate -m "initial_commit"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 2c957a9b6777

# View current migration status
alembic current

# View migration history
alembic history

# Create empty migration (manual)
alembic revision -m "description"

# Run migrations in offline mode (for CI/CD)
alembic upgrade head --sql > migration.sql
```

---

## 🚀 First Run Checklist

```bash
# 1. Create project structure
mkdir -p src/models/db_schemas/schemas
mkdir -p src/models/db_schemas/alembic/versions
mkdir -p docker

# 2. Create .env file
cp .env.example .env
# Edit .env with your database credentials

# 3. Install dependencies
pip install -r src/requirements.txt

# 4. Copy alembic files
# Copy alembic.ini, env.py from reference project

# 5. Create initial models
# Create connexio_base.py, project.py, asset.py, document.py, __init__.py

# 6. Initialize alembic (if starting fresh)
cd src/models/db_schemas
alembic init alembic

# 7. Generate first migration
alembic revision --autogenerate -m "initial_commit"

# 8. Review migration file
cat alembic/versions/*_initial_commit.py

# 9. Apply migration
alembic upgrade head

# 10. Start application
cd ../../..
uvicorn src/main:app --reload
```

---

## 💡 Quick Tips

- **Vector Column Dimension**: Must match your embedding model (usually 1024 for bge-m3)
- **Foreign Keys**: Always name them clearly: `table_id = Column(Integer, ForeignKey("table.id"))`
- **Relationships**: Use `back_populates` to enable bidirectional access
- **Indexes**: Add to frequently queried columns for performance
- **UUIDs**: Use for all primary entities (better than sequential IDs)
- **Timestamps**: Include `created_at` and `updated_at` on all tables

---

**Ready to go! Your colleague can start copying these templates immediately.**
