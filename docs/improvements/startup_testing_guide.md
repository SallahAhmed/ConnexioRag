# Connexio Startup & Testing Guide

Follow this guide to start the Connexio environment and verify the full RAG pipeline.

## Phase 1: Infrastructure (Docker)

Start only the essential database and broker services.

> [!IMPORTANT]
> Do NOT start the `celery-worker` in Docker if you want to see progress bars in your terminal.

```powershell
# From the project root
docker compose up -d pgvector rabbitmq redis
```

```powershell
conda activate mini-rag-app
```

## Phase 2: Local AI (Ollama)

Ensure the required models are pulled and ready.

```powershell
ollama pull qwen:4b
ollama pull bge-m3
ollama pull qwen:0.5b
```

## Phase 3: Application Services

Open **three separate terminals** (WSL preferred) in the `src` directory:

### Terminal 1: FastAPI Web Server

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

### Terminal 2: Celery Worker

```bash
python -m celery -A celery_app worker --loglevel=info --queues=file_processing,default,data_indexing --without-mingle --without-gossip --without-heartbeat
```

### Terminal 3: Flower Monitoring

```bash
python -m celery -A celery_app flower --conf=flowerconfig.py
```

---

## Phase 4: Testing Workflow (Postman)

Follow this sequence exactly to verify the system:

### 1. Upload File

- **Endpoint:** `POST /api/v1/data/upload/1`
- **Body:** `form-data` with `file`.
- **Result:** Copy the `file_id`.

### 2. Process File (Chunking)

- **Endpoint:** `POST /api/v1/data/process/1`
- **Body:**

```json
{
    "file_id": "YOUR_FILE_ID",
    "chunk_size": 512,
    "overlap_size": 50,
    "do_reset": 1
}
```

- **Verify:** Look for the "Processing Files" bar in the Celery terminal.

### 3. Index Push (Vectorizing)

- **Endpoint:** `POST /api/v1/nlp/index/push/1`
- **Body:** `{ "do_reset": 1 }`
- **Verify:** Look for the "Vector Indexing" bar in the Celery terminal.

### 4. Semantic Search

- **Endpoint:** `POST /api/v1/nlp/index/search/1`
- **Body:** `{ "text": "Your question here", "limit": 3 }`

### 5. RAG Answer

- **Endpoint:** `POST /api/v1/nlp/index/answer/1`
- **Body:** `{ "text": "Your question here", "limit": 3 }`

---

## Troubleshooting

- **401 OpenAI Error:** Ensure you restarted Celery after updating `.env`.
- **Offline Worker:** Check that the `.env` IP matches your WSL gateway (`ip route show | grep default`).
- **Slow Responses:** Check if Ollama is using your GPU and that `qwen:0.5b` is installed for utility tasks.
