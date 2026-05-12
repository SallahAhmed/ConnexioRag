#!/bin/bash
# Tell Python to look in the src directory
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# Start Celery worker 
celery -A celery_app worker --loglevel=info &

# Start RAG FastAPI 
uvicorn main:app --host 0.0.0.0 --port 7860
