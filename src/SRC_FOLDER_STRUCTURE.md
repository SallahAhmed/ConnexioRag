# Src Folder Structure Documentation

This document provides a comprehensive overview of the `src` folder structure, explaining the purpose and contents of each directory and key files.

---

## Core Entry Point

### **main.py**
The FastAPI application initialization file. Configures:
- Database connections (PostgreSQL via SQLAlchemy, MongoDB optional)
- Initializes LLM and Vector DB providers
- Sets up async engines
- Includes middleware for metrics and health checks
- Defines startup events for database initialization

---

## 📁 **assets/**

**Purpose**: Local file storage and vector database storage

### Subdirectories:
- **files/**: Stores uploaded document files for the RAG system (PDFs, text, images, etc.)
- **vector_db/**: Local vector database storage (contains indexed vectors for embeddings)
- **response.json**: Cached response templates

---

## 📁 **models/**

**Purpose**: Database schemas and ORM models for data persistence

### Key Files:
- **BaseDataModel.py**: Base class that wraps database client and app settings for all data models
- **AssetModel.py**: Manages assets (documents/files) CRUD operations in the database
- **ProjectModel.py**: Manages projects (containers for documents and RAG sessions)
- **SessionModel.py**: Manages conversation sessions
- **ChunkModel.py**: Manages text chunks created from documents

### Subdirectories:
- **db_schemas/**: Contains SQLAlchemy ORM schema definitions
  - **connexio/**: Main database schemas (Asset, Project, Session, Chunk tables)
  - **asset.py**: Asset table schema
  - **project.py**: Project table schema
  - **data_chunk.py**: Data chunk table schema
- **enums/**: Database-related enumerations (DataBaseEnum, etc.)

---

## 📁 **controllers/**

**Purpose**: Business logic layer that orchestrates operations

### Key Files:
- **BaseController.py**: Base controller with common utilities
  - File path management
  - Random ID generation
  - Vector DB path handling
- **DataController.py**: Handles data/file operations (uploading, processing files)
- **ProjectController.py**: Manages project operations
- **ProcessController.py**: Manages document processing pipeline
- **WorkflowController.py**: Orchestrates multi-step workflows
- **NLPController.py**: Handles NLP tasks (embeddings, chunking, vectorization)

### Subdirectories:
- **helpers/**: Controller-specific helper functions

---

## 📁 **stores/**

**Purpose**: Abstraction layer for external services (LLM providers, vector databases)

### **llm/** Subdirectory:
LLM provider abstraction and management
- **LLMProviderFactory.py**: Factory pattern - creates LLM provider instances
  - Supports: OpenAI, Cohere, Groq, Ollama
- **LLMInterface.py**: Abstract interface for LLM providers
- **LLMEnums.py**: Enumerations for LLM providers
- **providers/**: Concrete implementations
  - OpenAIProvider
  - CoHereProvider
  - GroqProvider
  - OllamaProvider
- **templates/**: LLM prompt templates and template parser

### **vectordb/** Subdirectory:
Vector database abstraction and management
- **VectorDBProviderFactory.py**: Factory for vector DB providers
  - Supports: Pinecone, Milvus, ChromaDB, etc.
- **VectorDBInterface.py**: Abstract interface for vector DB providers
- **VectorDBEnums.py**: Enumerations for vector DB providers
- **RerankerInterface.py**: For re-ranking search results
- **providers/**: Concrete vector DB implementations

---

## 📁 **Routes/**

**Purpose**: API endpoints (FastAPI routers)

### Key Files:
- **base.py**: Base routes
  - Health checks
  - Welcome endpoint
  - API version info
- **data.py**: Data/document operations endpoints
  - File upload
  - Document retrieval
  - Asset management
- **nlp.py**: NLP operations endpoints
  - Embeddings generation
  - Text chunking
  - Vectorization
- **agent.py**: Agent/workflow execution endpoints
  - Agent initialization
  - Task execution
  - Workflow management

### Subdirectories:
- **schemas/**: Request/response Pydantic schemas for validation

---

## 📁 **tasks/**

**Purpose**: Celery async tasks (background job processing)

### Key Files:
- **data_indexing.py**: Indexes documents into vector DB asynchronously
  - Chunks documents
  - Generates embeddings
  - Stores vectors in vector DB
- **file_processing.py**: Processes uploaded files
  - File parsing
  - Text extraction
  - Content cleaning
  - Initial chunking
- **process_workflow.py**: Executes multi-step workflows asynchronously
  - Pipeline orchestration
  - Task sequencing
  - Error handling
- **maintenance.py**: Cleanup and maintenance tasks
  - Cache clearing
  - Database optimization
  - Old data cleanup

---

## 📁 **utils/**

**Purpose**: Utility and helper functions

### Key Files:
- **metrics.py**: Application metrics and monitoring setup
  - Performance tracking
  - System health monitoring
- **generate_report.py**: Report generation utilities
  - Summary generation
  - Data export
- **idempotency_manager.py**: Ensures tasks run exactly once
  - Prevents duplicate processing
  - Transaction safety

---

## 📁 **helpers/**

**Purpose**: Helper/configuration utilities

### Key Files:
- **config.py**: Loads and manages environment variables
  - Settings class with validation
  - App configuration
  - Environment variable management

---

## 📁 **traces/**

**Purpose**: Debugging and monitoring

### Contents:
- JSON trace files for request tracing and debugging workflows
- Used for performance analysis and troubleshooting

---

## 📁 **tests/**

**Purpose**: Unit and integration tests (currently empty)

---

## 📁 **celerybeat/**

**Purpose**: Scheduled task definitions (currently empty)

---

## Other Key Files

### Configuration & Setup:
- **celery_app.py**: Celery worker configuration and initialization
- **flowerconfig.py**: Flower (Celery monitoring) configuration
- **requirements.txt**: Python dependencies list

### Data & Logs:
- **.env**: Environment variables configuration
- **.env.example**: Example environment variables
- **celerybeat-schedule**: Celery Beat scheduler persistence file
- **celery.log**: Celery worker logs
- **trace.json**: Trace data file
- **rag_report.html**: RAG system report (HTML format)

---

## Architecture Overview

### Data Flow:
```
API Request → Routes → Controllers → Models/Stores → Database
                              ↓
                    Background Tasks (Celery)
                              ↓
                      LLM/VectorDB via Stores
```

### Layer Responsibilities:

**1. Routes Layer**
- Receives HTTP requests
- Validates input schemas
- Calls appropriate controllers

**2. Controllers Layer**
- Business logic implementation
- Coordinates models and stores
- Orchestrates workflows

**3. Models Layer**
- Database schema definitions
- CRUD operations
- Data validation

**4. Stores Layer**
- Provider abstraction (LLM, VectorDB)
- Factory pattern for creating provider instances
- External service integration

**5. Tasks Layer**
- Asynchronous background processing
- Celery task definitions
- Scheduled operations

**6. Utils/Helpers Layer**
- Configuration management
- Common utilities
- Monitoring and metrics

---

## Design Patterns Used

1. **Factory Pattern**: LLMProviderFactory, VectorDBProviderFactory
2. **Strategy Pattern**: Different LLM and VectorDB providers
3. **Base Class Pattern**: BaseDataModel, BaseController for code reuse
4. **Dependency Injection**: Settings injected through FastAPI Depends
5. **Async/Await**: Throughout for non-blocking operations

---

## Key Features

- **Multi-Provider Support**: Switch between different LLM and VectorDB providers
- **Modular Architecture**: Clear separation of concerns
- **Async Operations**: Non-blocking I/O for better performance
- **Background Processing**: Celery tasks for heavy operations
- **Monitoring**: Metrics and trace collection built-in
- **Extensible**: Easy to add new providers or controllers

---

## Configuration

Environment variables are managed in `.env` and loaded via `helpers/config.py`. Key settings include:
- Database credentials (PostgreSQL, MongoDB)
- LLM API keys and URLs
- Vector DB configuration
- Celery broker configuration
- Application settings (timeouts, max tokens, etc.)
