#!/bin/bash
# Tell Python to look in the src directory
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# Start Celery worker with embedded beat scheduler (-B runs Beat in-process)
celery -A celery_app worker -B --loglevel=info &

# Start RAG FastAPI
# Wrap with opentelemetry-instrument only when OTLP is configured (Grafana Cloud).
# When OTEL_EXPORTER_OTLP_ENDPOINT is unset, run plain uvicorn (no overhead, no export errors).
if [ -n "$OTEL_EXPORTER_OTLP_ENDPOINT" ]; then
  exec opentelemetry-instrument uvicorn main:app --host 0.0.0.0 --port 7860
else
  exec uvicorn main:app --host 0.0.0.0 --port 7860
fi
