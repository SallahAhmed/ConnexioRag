# Testing Guide — Connexio RAG Agent V2

Follow these steps to verify that every component of the V2 Agent is working correctly.

## 🟢 Step 0: Ensure Services are Running
Before testing, make sure your local infrastructure is up:
1. **Docker**: Start your containers (PostgreSQL & Qdrant).
2. **FastAPI**: Start the server:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
3. **Postman**: Import the [Connexio_Agent_V2.postman_collection.json](file:///c:/Users/salla/mini-rag-app/src/postman/collections/Connexio_Agent_V2.postman_collection.json) file.

---

## 🏗️ Phase 1: Knowledge Ingestion
The agent needs ground truth data before it can answer project-specific questions.

1. **Index Project Data**
   - **Endpoint**: `POST /api/v1/nlp/index/push`
   - **Payload**: `{"project_id": 1, "do_reset": 1}`
   - **What to verify**: You should see a success signal and a count of `inserted_items_count`.
2. **Verify Index Info**
   - **Endpoint**: `POST /api/v1/nlp/index/info`
   - **Payload**: `{"project_id": 1}`
   - **What to verify**: Confirm the `collection_info` shows the correct number of points in the vector DB.

---

## 🤖 Phase 2: Core Agent Chat
Test the "Brain" of the system and its ability to remember conversations.

1. **Ask a General Question**
   - **Endpoint**: `POST /api/v1/nlp/agent/chat`
   - **Payload**: `{"user_id": 1, "project_id": 1, "query": "Hello, how can you help me today?", "persona": "student"}`
2. **Test Grounding (Why matched?)**
   - **Payload**: `{"user_id": 1, "project_id": 1, "query": "Why was I matched to this specific project?", "persona": "student"}`
   - **What to verify**: The agent should call the **SQL Matching Tool** and explain the 6-factor rationale.
3. **Test Memory (Following Up)**
   - **Payload**: `{"user_id": 1, "project_id": 1, "query": "Can you explain that more simply?", "session_id": 1}`
   - **What to verify**: Check the response to see if it refers to the previous answer.

---

## 💼 Phase 3: Specialized Persona Features
Test the specific tools built for Students and Supervisors.

1. **Portfolio Career Builder**
   - **Endpoint**: `POST /api/v1/nlp/agent/portfolio`
   - **Payload**: `{"user_id": 1, "format": "linkedin"}`
   - **What to verify**: You should get a professional summary of the user's task history.
2. **Supervisor Risk Assessment**
   - **Endpoint**: `POST /api/v1/nlp/agent/supervisor/risks`
   - **Payload**: `{"project_id": 1}`
   - **What to verify**: A summary of project progress and potential "stalled" tasks.
3. **Skill Coach**
   - **Endpoint**: `POST /api/v1/nlp/agent/coach/path`
   - **Payload**: `{"user_id": 1, "project_id": 1}`

---

## 📝 Phase 4: Document Generation & Planning
Test the creative and architectural capabilities.

1. **Automated Document Generation**
   - **Endpoint**: `POST /api/v1/nlp/agent/doc-gen`
   - **Payload**: `{"project_id": 1, "doc_type": "readme"}`
   - **What to verify**: High-quality Markdown text for a README.
2. **Task Architect Planning**
   - **Endpoint**: `POST /api/v1/nlp/agent/task-architect/plan`
   - **Payload**: `{"query": "How do I implement user authentication in this project?", "user_id": 1, "project_id": 1}`
   - **What to verify**: A step-by-step technical execution plan.

---

## 🔍 Troubleshooting Tips
- **Empty Answers**: Ensure you ran the `/index/push` step first.
- **SQL Errors**: Ensure the PostgreSQL database contains the tables shown in your ERD.
- **Wrong Language**: The agent auto-detects English vs. Arabic based on your query. Try asking in Arabic!

> [!NOTE]
> All endpoints are standardized to use the JSON Body (Body ID Style) as per your final preference.
