# 📘 Connexio API Documentation

Welcome to the Connexio API. This document explains every endpoint in the system in plain language, categorized by their role in the RAG (Retrieval-Augmented Generation) pipeline.

---

## 1. Data Ingestion & Processing

_These endpoints handle getting your documents (PDFs, TXT) into the system and preparing them for the AI._

### 📤 Upload File

`POST /api/v1/data/upload/{project_id}`

- **What it does**: Takes a physical file from your computer and saves it in the project's folder on the server.
- **Use this when**: You have a new project document (like a syllabus or a technical guide) you want the AI to learn.

### ⚙️ Process Files

`POST /api/v1/data/process/{project_id}`

- **What it does**: Takes the uploaded files, cleans the text, and breaks them into small "chunks."
- **Why**: AI cannot read a 100-page PDF all at once; it needs small pieces to find specific answers efficiently.

### 🚀 Process and Push (The All-in-One)

`POST /api/v1/data/process-and-push/{project_id}`

- **What it does**: Runs the upload, chunking, and vector database indexing in one single step.
- **Use this when**: You want the fastest way to make a document "searchable" by the AI.

---

## 2. The Search & "Pure RAG" Layer

_These endpoints are for testing the raw search capabilities without the advanced agent logic._

### 🔍 Semantic Search

`POST /api/v1/nlp/index/search/{project_id}`

- **What it does**: Returns the actual snippets of text from your documents that are most similar to your question.
- **Use this when**: You want to see exactly what "evidence" the AI is finding in your files.

### 📄 Index Answer (Simple RAG)

`POST /api/v1/nlp/index/answer/{project_id}`

- **What it does**: Searches your documents and generates a text answer based _only_ on those documents.
- **Limitation**: If the answer isn't in your files, it won't try to look elsewhere. It has no memory of previous questions.

---

## 3. The Agentic AI Layer (The "Brain")

_These are the most powerful endpoints. They use reasoning, memory, and external tools._

### 💬 Agent Chat

`POST /api/v1/nlp/agent/chat/{project_id}`

- **What it does**: A full conversation with an AI agent. It uses memory (remembers previous messages) and switches between English/Arabic.
- **Tool Power**: If it can't find the answer in your local files, it will automatically use **GitHub**, **Python**, **Google Search**, or **Wikipedia** to find the answer.
- **Personas**: You can tell it to act like a "Student", "Educator", or "Company" to get different tones of voice.

### 🌊 Streaming Agent Chat

`GET /api/v1/nlp/agent/chat/stream/{project_id}`

- **What it does**: Same as the Chat, but it sends the answer character-by-character as it's being "thought of."
- **Use this when**: You are building a frontend chat app (like ChatGPT) where you want to see the text appearing in real-time.

---

## 4. Specialized Professional Tools

_Advanced tools designed for specific project management and educational tasks._

### 💼 Portfolio Generator

`POST /api/v1/nlp/agent/portfolio/{project_id}`

- **What it does**: Scans a user's task history and contribution docs to generate a professional summary for a resume or portfolio.

### ⚠️ Supervisor Risk Assessment

`GET /api/v1/nlp/agent/supervisor/risks/{project_id}`

- **What it does**: Analyzes project progress, deadlines, and task stalls to identify which parts of the project are at risk of failing.

### 🏗️ Task Architect

`POST /api/v1/nlp/agent/task-architect/plan/{project_id}`

- **What it does**: Takes a complex goal (e.g., "Build a login system") and breaks it down into a technical step-by-step plan based on your project's specific context.

### 📝 Document Generator

`POST /api/v1/nlp/agent/doc-gen/{project_id}`

- **What it does**: Automatically writes a README.md or a Project Retrospective document based on the data indexed in the system.

### 💡 Coach Path

`GET /api/v1/nlp/agent/coach/path/{project_id}`

- **What it does**: Provides motivational insights and recommended learning paths based on the user's progress and current skills.
