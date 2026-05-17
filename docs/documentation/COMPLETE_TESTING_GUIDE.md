# 🧪 Complete Testing Guide — Connexio Platform

## 1. RAG Tools (Connexios)

| Tool | Test Method | Command / Payload | Expected Result |
|------|-------------|-------------------|-----------------|
| **ArXiv** | `curl` | `curl -X POST http://localhost:8000/api/v1/nlp/agent/chat/0 -H "Content-Type: application/json" -d '{"message": "What is the latest research on transformer models?"}'` | Returns ArXiv paper summaries with titles, authors, abstracts |
| **StackOverflow** | `curl` | `curl -X POST http://localhost:8000/api/v1/nlp/agent/chat/0 -H "Content-Type: application/json" -d '{"message": "How to fix CORS error in Express?"}'` | Returns SO answers with code snippets, vote counts, accepted answer |
| **Wikipedia** | `curl` | `curl -X POST http://localhost:8000/api/v1/nlp/agent/chat/0 -H "Content-Type: application/json" -d '{"message": "Who invented Python programming?"}'` | Returns Wikipedia summary with key facts |
| **Google (SerpAPI)** | `curl` | `curl -X POST http://localhost:8000/api/v1/nlp/agent/chat/0 -H "Content-Type: application/json" -d '{"message": "latest Node.js security vulnerabilities 2026"}'` | Returns top 5 search results with snippets |
| **Knowledge Base** | HF Spaces UI | Upload a PDF via `/api/v1/data/upload-and-process/{pid}`, then ask: `"Summarize the uploaded document"` | Returns accurate summary from vector search |
| **GitHub** | `curl` | `curl -X POST http://localhost:8000/api/v1/nlp/agent/chat/0 -H "Content-Type: application/json" -d '{"message": "Show me recent commits from github.com/user/repo"}'` | Returns commit list with messages and dates |
| **Backend REST** | `curl` | `curl -X POST http://localhost:8000/api/v1/nlp/agent/chat/{pid} -H "X-API-Key: $KEY" -d '{"message": "What tasks are in my project?"}'` | Returns live tasks from Node.js backend |

## 2. MasarX Agent Tools

| Tool | Test Method | Command / Payload | Expected Result |
|------|-------------|-------------------|-----------------|
| **CodeReviewTool** | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/agent/review_pr/{pid} -H "Content-Type: application/json" -d '{"pr_url": "https://github.com/user/repo/pull/1", "diff": "..."}'` | Returns quality score, security issues, suggestions |
| **DocGeneratorTool** | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/agent/generate_docs/{pid} -H "Content-Type: application/json" -d '{"repo_url": "https://github.com/user/repo"}'` | Returns README, architecture doc, setup guide |
| **SkillRecommenderTool** | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/agent/recommend_skills/{pid} -H "Content-Type: application/json" -d '{"user_id": 5, "project_id": 2}'` | Returns personalized learning path with resources |
| **GitHubTool** | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/agent/scaffold_repo/{pid} -H "Content-Type: application/json" -d '{"repo_name": "test-project", "template": "python-fastapi"}'` | Creates GitHub repo with boilerplate files |
| **TavilyTool** | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/agent/detect_risks/{pid}` | Returns web-research-backed risk assessment |
| **DBTool** | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/agent/create_tasks/{pid} -H "Content-Type: application/json" -d '{"sprint_id": 1}'` | Reads user/project data from PG, generates tasks |
| **NotificationTool** | `curl` | Trigger any intent that completes | Slack message + DB notification created |
| **EmailTool** | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/agent/onboard_member/{pid} -H "Content-Type: application/json" -d '{"user_id": 3}'` | Welcome email sent to new member |

## 3. Event-Driven Webhooks

| Event | Test Method | Command | Expected Result |
|-------|-------------|---------|-----------------|
| `user.joined_platform` | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/webhook/event/user.joined_platform/{pid}` | `202 Accepted` → team matching triggered |
| `project.sprint_started` | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/webhook/event/project.sprint_started/{pid}` | `202 Accepted` → task creation triggered |
| `task.completed` | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/webhook/event/task.completed/{pid}` | `202 Accepted` → skill endorsement triggered |
| `pullrequest.merged` | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/webhook/event/pullrequest.merged/{pid}` | `202 Accepted` → code review triggered |

## 4. HITL Approval Flow

| Step | Test Method | Command | Expected Result |
|------|-------------|---------|-----------------|
| 1. Generate plan | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/agent/create_tasks/{pid} -H "Content-Type: application/json" -d '{"sprint_id": 1}'` | Returns `approval_token` |
| 2. Approve | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/approval/{token} -H "Content-Type: application/json" -d '{"approved": true}'` | Tasks created in DB |
| 3. Reject | `curl` | `curl -X POST http://localhost:8000/api/v1/masarx/approval/{token} -H "Content-Type: application/json" -d '{"approved": false}'` | Plan discarded, notification sent |

## 5. Optimal Testing Environments

| Feature | Best Environment | Why |
|---------|------------------|-----|
| **RAG Chat / CRAG** | **HF Spaces UI** (ConnexioRag) | Full UI with streaming, markdown, history |
| **Agent Intents** | **LangSmith Studio** | Visual LangGraph tracing, step-by-step inspection |
| **Webhooks** | **Postman / curl** | Easy to fire events, inspect 202 responses |
| **Code Review** | **GitHub PR + curl** | Real PR diff, realistic review output |
| **Doc Generator** | **HF Spaces UI** | Upload repo, get generated docs |
| **Skill Recommender** | **LangSmith Studio** | See reasoning chain, skill gap analysis |
| **HITL Flow** | **Postman** | Token generation → approval → resume |
| **Cron Jobs** | **cron-job.org** | Free external pings to prevent HF sleep |
| **Rate Limiting** | **`ab` or `hey`** | `hey -n 50 -c 5 http://localhost:8000/api/v1/nlp/agent/chat/0` |
| **Circuit Breaker** | **Kill LLM endpoint** | Simulate failure, verify fallback |

## 6. Quick Smoke Test Script

```bash
# Save as test_all.sh
#!/bin/bash
BASE="http://localhost:8000"
KEY="your-api-key"

echo "=== RAG Health ==="
curl -s $BASE/health | jq

echo "=== Agent Health ==="
curl -s $BASE/api/v1/masarx/health | jq

echo "=== RAG Chat (no project) ==="
curl -s -X POST $BASE/api/v1/nlp/agent/chat/0 \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, what can you do?"}' | jq

echo "=== RAG Chat (with project) ==="
curl -s -X POST $BASE/api/v1/nlp/agent/chat/1 \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is my project about?"}' | jq

echo "=== Agent: Create Tasks ==="
curl -s -X POST $BASE/api/v1/masarx/agent/create_tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"sprint_id": 1}' | jq

echo "=== Agent: Code Review ==="
curl -s -X POST $BASE/api/v1/masarx/agent/review_pr/1 \
  -H "Content-Type: application/json" \
  -d '{"pr_url": "https://github.com/user/repo/pull/1"}' | jq

echo "=== Webhook: Sprint Started ==="
curl -s -X POST $BASE/api/v1/masarx/webhook/event/project.sprint_started/1 | jq

echo "=== Done ==="
```

## 7. Verification Checklist

- [ ] All 7 RAG tools return valid responses
- [ ] All 8 MasarX tools execute without errors
- [ ] Webhooks return 202 and trigger correct intents
- [ ] HITL flow: token → approve → tasks created
- [ ] Rate limiting: 31st request in 60s returns 429
- [ ] Circuit breaker: LLM down → graceful fallback
- [ ] Cron semaphore: max 5 concurrent projects
- [ ] No Python `exec()` calls remain in codebase
- [ ] JWT bypass only works on `localhost`
- [ ] `chunks.chunk_asset_id` is `nullable=True`
- [ ] All secrets redacted from docs and code
