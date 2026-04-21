# Implementation Plan - Fixing App Startup and Connectivity Errors

This plan addresses the critical failures preventing the FastAPI server and Celery worker from starting correctly.

## User Review Required

> [!IMPORTANT]
> - **Database Host**: I am changing `POSTGRES_HOST` from `pgvector` to `localhost`. This assumes you are running the app on your host machine (Windows/WSL) while the database is in Docker.
> - **Ollama Connectivity**: My tests show `172.17.80.1:11434` is unreachable. You may need to verify your Ollama service is running and accessible from your environment.
> - **Celery Remote Control**: I will disable Celery's remote control features to bypass a known incompatibility with recent RabbitMQ versions.

## Proposed Changes

### Environment Configuration
Fixing host resolution for the database.

#### [MODIFY] .env
- Update `POSTGRES_HOST` to `localhost`.
- (Optional) Update Ollama IP if a better one is provided.

### Celery Infrastructure
Resolving RabbitMQ 3.12+ compatibility errors.

#### [MODIFY] celery_app.py
- Update `celery_app.conf` to include:
  - `worker_enable_remote_control = False`
  - `worker_send_task_events = False`
- This prevents Celery from trying to declare the deprecated "transient" queues that cause RabbitMQ to error out.

### FastAPI Dependencies
Ensuring the reranker and other modules load correctly.

#### [MODIFY] main.py
- Add additional error handling around reranker initialization to prevent the whole app from crashing if local models are missing.

## Open Questions
- **Ollama IP**: Is `172.17.80.1` definitely the IP where your Ollama service is running? If you are on WSL, `localhost` or the host IP usually works, but it depends on your networking setup.

## Verification Plan

### Automated Tests
- Restart the Celery worker and verify it reaches the "Ready" state without restarting.
- Start the Uvicorn server and verify it reaches "Waiting for application startup" and initializes the DB tables successfully.

### Manual Verification
- Check the health endpoint of the API once it's up.
