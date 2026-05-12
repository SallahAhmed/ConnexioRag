# Connexio Project Stabilization Summary

This document summarizes the key changes made to stabilize and optimize the Connexio RAG platform during the development session on April 23, 2026.

## 1. Core Infrastructure & Connectivity Fixes
- **Docker Networking:** Resolved connectivity issues between the Windows/WSL host and Docker containers by standardizing on the network gateway IP (`172.17.80.1`) for PostgreSQL, RabbitMQ, and Redis.
- **Celery Visibility:** Resolved the "hidden logs" issue by moving the Celery Worker and Flower execution from Docker to the local terminal. This allows for real-time `tqdm` progress bars and clear traceback visibility.
- **LLM Client Fix:** Identified and fixed a critical bug in `src/celery_app.py` where background tasks were ignoring the local Ollama URL and defaulting to `api.openai.com`, causing `401 Unauthorized` errors with placeholder keys.

## 2. AI & Performance Optimizations
- **Multilingual Support (Arabic):** Replaced the `nomic-embed-text` model with **`bge-m3`** (1024-dim). This significantly improved semantic search accuracy for Arabic documents.
- **"Agentic" Speed Optimization:** 
    - Introduced a **Utility LLM Client** powered by `qwen:0.5b`. This tiny model now handles background "Agent" tasks (Language detection, Intent detection), saving the heavy lifting for the main model.
    - Disabled **Query Decomposition** and **Relevance Grading** in the `NLPController` to reduce the number of LLM calls per request from 5 down to 2, cutting response times from minutes to seconds.
- **Memory Management:** Leveraged Ollama's dynamic loading to manage 32GB RAM effectively across multiple models (`gemma`, `bge-m3`, `qwen:0.5b`).

## 3. Codebase Structural Changes
- **Settings Expansion:** Updated `Settings` and `.env` to support `UTILITY_MODEL_ID`.
- **Controller Refactoring:** Updated `NLPController` to handle multiple LLM clients (Generation vs. Utility) and streamlined the `_prepare_chat_context` workflow.
- **Dependency Cleanup:** Removed `sentence-transformers` dependency to simplify the environment and avoid local build errors, defaulting to direct Vector DB retrieval.

## 4. Current Configuration
- **Generation Model:** `gemma4:e2b` (Main Answer)
- **Utility Model:** `qwen:0.5b` (Intent/Language)
- **Embedding Model:** `bge-m3` (Vector Indexing)
- **Vector DB:** PGVector (PostgreSQL)
