# 🚀 Connexios RAG API: The Complete Guide

Welcome to the Connexios API! This system is a **Project-Aware RAG (Retrieval-Augmented Generation)** platform. It doesn't just "search" documents; it understands them to act as a Project Manager, Educator, or Business Analyst.

---

## 📂 1. Data Management Endpoints
*These endpoints handle getting your files into the system and preparing them for AI.*

### **A. Upload File**
- **Endpoint:** `POST /api/v1/data/upload/{project_id}`
- **What it does:** Sends a file (PDF, TXT, etc.) to the server.
- **Example:** Use Postman `form-data` with a key named `file`.

### **B. Process File**
- **Endpoint:** `POST /api/v1/data/process/{project_id}`
- **What it does:** Takes an uploaded file and "chunks" it (breaks it into small pieces) so the AI can read it easily.
- **Postman Body (JSON):**
```json
{
    "file_id": "your_file_id",
    "chunk_size": 500,
    "overlap_size": 50
}
```

### **C. Process & Push (All-in-One)**
- **Endpoint:** `POST /api/v1/data/process-and-push/{project_id}`
- **What it does:** The "Master Workflow." It processes the file AND pushes it to the Vector Database in one go.
- **Use case:** Use this if you want a simple, one-click experience.

---

## 🧠 2. Knowledge Base (NLP) Endpoints
*These endpoints manage the "Brain" (Vector Database) of the project.*

### **A. Index Info**
- **Endpoint:** `GET /api/v1/nlp/index/info/{project_id}`
- **What it does:** Shows you how many documents/vectors are currently stored for this project.
- **Use case:** Checking if your data is actually saved in the AI's memory.

### **B. Search Index**
- **Endpoint:** `POST /api/v1/nlp/index/search/{project_id}`
- **What it does:** Returns the most relevant "snippets" from your files based on a query.
- **Postman Body (JSON):**
```json
{
    "text": "History of Lebanon",
    "limit": 3
}
```

---

## 🤖 3. Intelligent Agent Endpoints
*This is the "Smart" layer. These endpoints perform specialized tasks using your data.*

### **A. Agent Chat (Persona-Based)**
- **Endpoint:** `POST /api/v1/nlp/agent/chat/{project_id}`
- **What it does:** A conversational AI that uses your project data. You can choose a **Persona** to change how it answers.
- **Personas:** `student`, `educator`, `company`, `early_career`.
- **Postman Body (JSON):**
```json
{
    "query": "Summarize the project goals",
    "persona": "educator",
    "user_id": 1
}
```

### **B. Streaming Chat**
- **Endpoint:** `GET /api/v1/nlp/agent/chat/stream/{project_id}`
- **What it does:** Like ChatGPT, the text appears word-by-word.
- **Postman Params:** Add `query`, `persona`, and `user_id` in the Params tab.

### **C. Task Architect**
- **Endpoint:** `POST /api/v1/nlp/agent/task-architect/plan/{project_id}`
- **What it does:** Analyzes a complex problem and creates a step-by-step plan based on your documents.
- **Postman Body (JSON):**
```json
{
    "query": "How should we organize the next phase of this project?",
    "user_id": 1
}
```

### **D. Document Generation (Doc-Gen)**
- **Endpoint:** `POST /api/v1/nlp/agent/doc-gen/{project_id}`
- **What it does:** Automatically writes a **README**, a **Summary**, or a **Retrospective** for your project.
- **Postman Body (JSON):**
```json
{
    "doc_type": "readme"
}
```

### **E. Supervisor Risks**
- **Endpoint:** `GET /api/v1/nlp/agent/supervisor/risks/{project_id}`
- **What it does:** Scans your project data and identifies potential "risks" or problems that a manager should know.

### **F. Career Portfolio**
- **Endpoint:** `POST /api/v1/nlp/agent/portfolio/{project_id}`
- **What it does:** Generates a professional summary or "resume entry" based on the work found in the project files.
- **Postman Body (JSON):**
```json
{
    "user_id": 1,
    "format": "linkedin"
}
```

---

## 💡 Summary Workflow for a New User:
1. **Upload** a file.
2. **Process-and-Push** to make it searchable.
3. **Chat** with the Agent to ask questions about the file.
4. **Doc-Gen** to write a report based on the file content.
