# Local Environment Startup Guide

Here is the complete, step-by-step guide to starting your entire local development environment for testing the endpoints. It covers everything from Docker services, the Ollama server (with the Administrator permission), the FastAPI backend, and the Celery worker.

## Step 1: Start Background Services (Docker)

First, you need to ensure that your database (PostgreSQL), Redis, and RabbitMQ (for Celery) are running.

1. Open a terminal in your project directory (`c:\Users\salla\Connexio`).
2. Navigate to the folder containing your `docker-compose.yml` (e.g., `cd docker`).
3. Run the following command to start the containers in the background:
   ```bash
   docker compose up -d # -d for detahced mode and remove it to run in foreground
   ```

## Step 2: Start Ollama Server (Windows PowerShell - Administrator)

Because your services (like WSL or Docker containers) need to access the Ollama LLM running on your Windows host, you must expose the Ollama host IP.

1. Open the **Start Menu**, search for **PowerShell**, right-click it, and select **Run as Administrator**.
2. Run the following commands to set the binding IP and start the server:
   ```powershell
   $env:OLLAMA_HOST="0.0.0.0"
   ollama serve
   ```
3. **Leave this terminal open** while you are testing.

## Step 3: Start the FastAPI Application

Now you need to start the main Python backend application.

1. Open a new regular terminal (or VS Code terminal).
2. Navigate to your `src` directory:
   ```powershell
   cd c:\Users\salla\Connexio\src
   ```
3. Activate your Python virtual environment (if you use one).
   ```
   conda activate mini-rag-app
   ```
4. Start the application using `uvicorn`:

   ```powershell
   uvicorn main:app --reload --host 0.0.0.0 --port 8080
   ```

5. **Leave this terminal open**. Wait until you see `Application startup complete.`

## Step 4: Start the Celery Worker (WSL)

Since your application offloads heavy processing (like vector indexing) to background tasks, you must start the Celery worker, which we previously configured to run in WSL.

1. Open a new **WSL Terminal** (Ubuntu).
2. Navigate to your `src` directory inside the WSL filesystem:
   ```bash
   cd /mnt/c/Users/salla/Connexio/src
   ```
3. Activate your Python virtual environment (if applicable).
4. Run the Celery worker:
   ```bash
   python -m celery -A celery_app worker --queues==default,file_processing,data_indexing --loglevel=info
   ```
   Run the Flower worker (on port 5556 to avoid Docker conflicts):
   ```bash
   python -m celery -A celery_app flower --conf=flowerconfig.py --port=5556
   ```
5. **Leave this terminal open**. You should see it connect to RabbitMQ successfully. You can access this local dashboard at http://localhost:5556.

# If you build the fastapi again and downloaded the requirements again you have to run this command in your powershell as an adminstrator:

```powershell
New-NetFirewallRule -DisplayName "WSL to Host" -Direction Inbound -LocalPort 5672,6379,5433,6333,8000,15672 -Protocol TCP -Action Allow
```

## Step 5: Start Testing (Postman)

Once all four terminal windows are running without errors, you are fully set up.

1. Open **Postman**.
2. Make sure your base URL or host variables are pointing to the correct address (e.g., `127.0.0.1:8080` for your FastAPI endpoints).
3. You can now execute your requests (e.g., uploading files, pushing to the index, or asking the agent a question) and everything will route correctly through the API, to Celery, and to Ollama!

### if you wanna add a table on the database and you already added it to the models, you have to write the following commands in your terminal(wsl) using alembic in the following project path: /mnt/c/Users/salla/Connexios/src

```bash
alembic revision --autogenerate -m "add table X"
alembic upgrade head
```
