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

| Feature | description  
| Matching algorithm | Weighted 6-factor scoring (business-defined weights) |
| Persona handling | Student vs Early-career — different tone, depth, focus |
| Language | English + Arabic (auto-detected) |
| Workflow nodes | 5 nodes: onboarding, team_formation, phase_transition, blocker, milestone_warning |
| Phase transition | Validates deliverable checklist before allowing advancement |
| Team gap check | Warns on missing technical or non-technical roles |
| Session tracking | Persists persona, language, phase across conversation turns |
| Freemium logic | Agent aware of free vs premium limits, mentions naturally |
| Rating in matching | Yes — 20% weight in scoring |

---

## Architecture: Workflow Nodes

The agent routes every message through one of 5 workflow nodes based on what the user needs at that moment. Each node has its own retrieval strategy, system prompt instructions, and response behavior.

```
User Message
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                  WORKFLOW NODE DETECTOR                  │
│                                                         │
│  Keywords → Route to one of:                            │
│                                                         │
│  1. ONBOARDING       → "where do I start", "new here"   │
│  2. TEAM_FORMATION   → "find teammate", "need a dev"    │
│  3. PHASE_TRANSITION → "next phase", "done with MVP"    │
│  4. BLOCKER          → "stuck", "not responding"        │
│  5. MILESTONE_WARNING→ "behind", "overdue", "late"      │
│  6. GENERAL          → everything else                  │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│                   RAG RETRIEVAL                          │
│                                                         │
│  Node-specific retrieval:                               │
│  • onboarding      → onboarding docs + persona guide    │
│  • team_formation  → user profiles (weighted) + rules   │
│  • phase_transition→ lifecycle docs for current phase   │
│  • blocker         → best_practices + community docs    │
│  • milestone_warning→ lifecycle + sprint docs           │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│             PERSONA + LANGUAGE DETECTION                 │
│                                                         │
│  Persona: student | early_career | educator | company   │
│  Language: English | Arabic (auto from message)         │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│              LLM (Claude Sonnet 4)                       │
│                                                         │
│  System prompt = persona guide + node instruction       │
│               + retrieved context                       │
│  Responds in user's language                            │
│  Grounded in KB only — no hallucination                 │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│              PERSIST + RESPOND                           │
│                                                         │
│  • Save to chat_history with workflow_node tag          │
│  • Update session (persona, language, phase)            │
│  • Log milestone warnings if applicable                 │
│  • Return: reply + sources + workflowNode + language    │
└─────────────────────────────────────────────────────────┘
```

---

## Matching Algorithm

The matching engine scores every user profile across 6 factors using business-defined weights:

```
Final Score = (skill_complementarity × 0.35)
            + (availability_match    × 0.25)
            + (rating_history        × 0.20)
            + (phase_experience      × 0.12)
            + (learning_goals        × 0.05)
            + (domain_alignment      × 0.03)
```
