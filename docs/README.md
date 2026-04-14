# Local Setup & Testing Guide

This guide provides steps to run and test the application locally using Docker, Ollama, and FastAPI.

## 1. Prerequisites
- Docker & Docker Compose installed.
- Ollama installed (Windows or WSL).
- Python 3.10+ and virtual environment set up.

---

## 2. Infrastructure Setup (Docker)
Always start the database services first.

### Commands:
```bash
cd docker
docker-compose up -d
```

### Safe Shutdown:
To keep your data safe in the database:
- **DO:** Use `docker-compose stop` or `docker-compose down`.
- **DON'T:** Use `docker-compose down -v` (This will delete all your data).

---

## 3. AI Models (Ollama)
Ensure Ollama is running and has the required models.

### Step A: Start Ollama Server
If running on Windows to serve a WSL application:
1. Quit Ollama from System Tray.
2. Run in PowerShell:
   ```powershell
   $env:OLLAMA_HOST="0.0.0.0"
   ollama serve
   ```

### Step B: Pull Models
```bash
ollama pull qwen:4b
ollama pull nomic-embed-text:latest
```

---

## 4. Database Initialization (Migrations)
If you recreate the database or it is empty, you must run migrations to create the tables.

### Commands:
```bash
# From the project root
cd src/models/db_schemas/connexio
alembic upgrade head
```

---

## 5. Running the Application
Activate your virtual environment and start the development server.

### PowerShell (Windows):
```powershell
cd src
..\.venv\Scripts\activate
python -m uvicorn main:app --reload
```

### Bash (WSL):
```bash
cd src
source ../.venv/bin/activate
python3 -m uvicorn main:app --reload
```

---

## 6. Connectivity Troubleshooting (WSL to Windows)
If the app in WSL cannot connect to Ollama on Windows:
1. Get Windows Host IP in WSL: `grep nameserver /etc/resolv.conf | awk '{print $2}'`
2. Update `src/.env` URLs with that IP:
   `OPENAI_GENERATION_API_URL="http://<WINDOWS_IP>:11434/v1"`
