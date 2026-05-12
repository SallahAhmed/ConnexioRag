#!/bin/bash

# 1. Tell Python to look in the src directory for modules
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# 2. Start Celery worker using the full path
celery -A src.celery_app worker --loglevel=info &

# 3. Start RAG FastAPI from the root
uvicorn src.main:app --host 0.0.0.0 --port 7860
