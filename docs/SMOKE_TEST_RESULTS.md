# 🔬 Smoke Test Results — May 16, 2026

## Services Status

| Service | URL | Health Check | Status |
|---------|-----|--------------|--------|
| **RAG (ConnexioRag)** | `https://sallahahmed-connexiorag.hf.space` | `/api/v1/health` → `healthy` | ✅ Running |
| **Agent (ConnexioAgent)** | `https://sallahahmed-connexioagent.hf.space` | `/api/v1/masarx/health` → `healthy` | ✅ Running |
| **Backend** | `https://connexio.icu` | Not tested yet | ⏳ Pending |

## Test Results

### 1. RAG Health Check
```
GET /api/v1/health
Response: {"status": "healthy", "service": "ConnexiosRAG", "version": "0.1"}
✅ PASS
```

### 2. MasarX Agent Health Check
```
GET /api/v1/masarx/health
Response: {"signal": "health_check_success", "status": "healthy", "service": "MasarX", "llm_status": "ok", "model": "llama-3.3-70b-versatile"}
✅ PASS
```

### 3. RAG Chat (No Project — Tier 1)
```
POST /api/v1/nlp/agent/chat/0
Body: {"query": "Hello, what can you do?", "user_id": 11}
Headers: X-API-Key: [redacted]
Response: {"signal": "agent_chat_success", "answer": "I'm Connexio AI, a project collaboration assistant...", "node": "general", "language": "en", "session_id": 28}
✅ PASS
```

### 4. RAG Chat — ArXiv Tool Trigger
```
POST /api/v1/nlp/agent/chat/0
Body: {"query": "What is the latest research on transformer models in machine learning?", "user_id": 11}
Response: Detailed answer covering Efficient Transformers, Large-Scale Transformers, Multimodal Transformers, Explainability, and Applications Beyond NLP. Cited papers: Transformer-XL, Reformer, Linformer, Vision Transformer.
✅ PASS
```

### 5. MasarX Webhook Event (project.sprint_started)
```
POST /api/v1/masarx/webhook/event/project.sprint_started/1
Body: {}
Headers: Authorization: Bearer [JWT token]
Response: {"signal": "masarx_event_accepted", "event": "project.sprint_started", "intent": "create_tasks", "project_id": "1"}
✅ PASS
```

## Pending Tests

| Test | Status | Notes |
|------|--------|-------|
| RAG Chat with project_id (Tier 2) | ⏳ | Need valid project with indexed documents |
| StackOverflow tool | ⏳ | Ask a coding error question |
| Wikipedia tool | ⏳ | Ask a general knowledge question |
| Google (SerpAPI) tool | ⏳ | Ask a current events question |
| GitHub tool | ⏳ | Ask about a specific repo |
| Knowledge Base search | ⏳ | Need project with uploaded files |
| Backend REST integration | ⏳ | Need project with members/tasks |
| Code Review (review_pr) | ⏳ | Need real GitHub PR URL |
| Doc Generator (generate_docs) | ⏳ | Need repo URL |
| Skill Recommender (recommend_skills) | ⏳ | Need user with skill gaps |
| HITL Approval Flow | ⏳ | Need to trigger create_tasks first |
| Rate Limiting | ⏳ | Send 31+ requests in 60s |
| Circuit Breaker | ⏳ | Simulate LLM failure |
| Cron Jobs | ⏳ | Wait for scheduled execution |

## Notes

- **JWT Token Generation**: Working correctly with shared `JWT_SECRET`. Tokens expire in 5 minutes.
- **API Key Auth**: RAG correctly requires `X-API-Key` header.
- **Service Token Auth**: MasarX correctly requires `Authorization: Bearer <JWT>` header.
- **Response Format**: Both services return consistent JSON with `signal`, `status`, and data fields.
- **ArXiv Tool**: Successfully triggered and returned relevant academic paper summaries.
- **Webhook Events**: Correctly mapped `project.sprint_started` → `create_tasks` intent.

## Next Steps

1. Test remaining RAG tools (StackOverflow, Wikipedia, Google, GitHub, KB)
2. Test MasarX agent intents (create_tasks, review_pr, generate_docs, recommend_skills)
3. Test HITL approval flow end-to-end
4. Test rate limiting and circuit breaker
5. Verify cron job execution logs
