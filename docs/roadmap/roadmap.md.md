# Connexio: Future Roadmap

This document outlines the planned enhancements for the Connexio Agentic RAG platform. These items are deferred for future implementation phases.

## 1. Frontend / UI Integration

- **Goal**: Transition from Postman-based testing to a user-facing interface.
- **Components**:
  - **SSE Streaming Support**: A responsive chat window that renders Server-Sent Events in real-time.
  - **Dashboard**: Integration with the Prometheus/Grafana metrics.
  - **Persona Switcher**: UI controls to toggle between Student, Educator, and Company personas.
- **Tech Stack**: Streamlit (fastest) or Next.js (production-ready).

## 2. Advanced Reranking

- **Goal**: Improve the precision of document retrieval.
- **Method**:
  - Integrate a cross-encoder reranker (e.g., Cohere Rerank API or local BGE Reranker).
  - Update `ToolManager.search_knowledge_base` to utilize the reranker before passing context to the LLM.

## 3. RAG Evaluation Framework

- **Goal**: Quantitatively measure the quality of AI responses.
- **Metrics**: Faithfulness, Answer Relevance, Context Precision, and Context Recall.
- **Tools**: RAGAS or TruLens.

## 4. Authentication & Multi-Tenancy

- **Goal**: Secure endpoints and ensure data isolation.
- **Features**:
  - **JWT Auth**: Protect all `/api/v1/` routes.
  - **Role-Based Access Control (RBAC)**: Restrict supervisor/educator endpoints.
  - **Data Isolation**: Ensure `project_id` queries are strictly scoped to the authenticated user's permissions.
