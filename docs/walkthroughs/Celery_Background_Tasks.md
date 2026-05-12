# Celery & Background Tasks Walkthrough

This walkthrough outlines the steps taken to fully resolve the Celery and RabbitMQ integration within the RAG application and delegate text processing out of the FastAPI main thread.

## 1. What was Broken?
- **RabbitMQ Compatibility**: Celery was attempting to use deprecated transient queue features to orchestrate worker communications via "mingle" and "gossip", causing a restart loop and connection timeouts.
- **Synchronous Bottleneck**: The `/api/v1/data/process` endpoint was blocking the FastAPI thread by processing and chunking PDFs synchronously, preventing the app from scaling.

## 2. What we fixed

### RabbitMQ & Celery Connectivity
- We completely bypassed the transient queue issue with RabbitMQ by turning off all internal Celery communication protocols that trigger it.
- **Worker Command**: The worker must now be launched with:
  ```bash
  python -m celery -A celery_app worker --loglevel=info --queues=file_processing,default --without-mingle --without-gossip --without-heartbeat
  ```

### Delegating `/process` to Background
- We refactored `Routes/data.py` to completely decouple document processing from the API server.
- When `/api/v1/data/process/{project_id}` is hit, it now instantly returns an HTTP 200 via `JSONResponse` along with a Celery `task_id`.
- The actual heavy lifting (reading the file, chunking it, creating vectors, and interacting with the Postgres Database) happens completely automatically in the `process_project_files` Celery task we refactored earlier.
- Fixed the argument type annotations in `tasks/file_processing.py` to correctly map `file_id` as an optional UUID string rather than an integer.

## 3. How to Test End-to-End

1. **Start RabbitMQ, Postgres, Redis via Docker**
2. **Start your FastAPI Server**
3. **Start the Celery worker** using the explicit flags:
   ```bash
   python -m celery -A celery_app worker --loglevel=info --queues=file_processing,default --without-mingle --without-gossip --without-heartbeat
   ```
4. **Trigger the flow**:
    - Upload a PDF via POSTMAN to `/api/v1/data/upload/{project_id}`
    - Trigger processing to `/api/v1/data/process/{project_id}`
    - Observe the FastAPI respond instantly, while the Celery terminal logs chunk creation and database insertion!
