#!/bin/bash

# 1. Start the Celery Worker for data processing
celery -A src.celery_app worker --loglevel=info &

# 2. Start the RAG FastAPI application on port 7860
cd src && uvicorn main:app --host 0.0.0.0 --port 7860
