# Memory

> Chronological action log. Hooks and AI append to this file automatically.
> Old sessions are consolidated by the daemon weekly.

## Session: 2026-05-12 20:02

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|

## Session: 2026-05-12 21:20

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|

## Session: 2026-05-12 21:20

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|

## Session: 2026-05-12 21:20

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 21:23 | Edited f:/MasarX_A/src/models/db_schemas/live_models.py | 8→9 lines | ~170 |
| 21:23 | Edited f:/MasarX_A/src/main.py | 4→6 lines | ~135 |
| 21:23 | Created src/models/db_schemas/connexio/schemas/project_id_map.py | — | ~170 |
| 21:24 | Edited src/models/db_schemas/connexio/schemas/__init__.py | added 1 import(s) | ~81 |
| 21:24 | Created src/models/db_schemas/connexio/alembic/versions/f1a2b3c4d5e6_add_project_id_map_table.py | — | ~328 |
| 21:24 | Edited src/models/db_schemas/connexio/alembic.ini | inline fix | ~39 |
| 21:24 | Edited src/utils/backend_client.py | 5→5 lines | ~54 |
| 21:25 | Edited src/celery_app.py | expanded (+7 lines) | ~60 |
| 21:25 | Edited src/celery_app.py | 15→18 lines | ~155 |
| 21:26 | Edited src/celery_app.py | 5→4 lines | ~21 |
| 21:26 | Edited src/Routes/data.py | modified process_endpoint() | ~579 |
| 21:27 | Session end: 11 writes across 9 files (live_models.py, main.py, project_id_map.py, __init__.py, f1a2b3c4d5e6_add_project_id_map_table.py) | 12 reads | ~3207 tok |
| 21:29 | Edited f:/MasarX_A/src/helpers/config.py | 2→3 lines | ~35 |
| 21:29 | Created f:/MasarX_A/src/utils/auth.py | — | ~337 |
| 21:29 | Edited f:/MasarX_A/src/Routes/webhook_routes.py | 15→20 lines | ~165 |
| 21:29 | Edited f:/MasarX_A/src/requirements.txt | 4→5 lines | ~27 |
| 21:30 | Session end: 15 writes across 13 files (live_models.py, main.py, project_id_map.py, __init__.py, f1a2b3c4d5e6_add_project_id_map_table.py) | 14 reads | ~3773 tok |
| 21:36 | Session end: 15 writes across 13 files (live_models.py, main.py, project_id_map.py, __init__.py, f1a2b3c4d5e6_add_project_id_map_table.py) | 14 reads | ~3773 tok |

## Session: 2026-05-12 21:48

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 21:51 | Edited src/Routes/data.py | added 2 import(s) | ~240 |
| 21:52 | Edited src/Routes/data.py | modified _background_index() | ~1001 |
| 21:52 | Edited src/Routes/data.py | modified process_and_push_endpoint() | ~1051 |
| 21:52 | Created src/Routes/projects.py | — | ~784 |
| 21:52 | Edited src/main.py | added 1 import(s) | ~25 |
| 21:52 | Edited src/main.py | 4→5 lines | ~53 |
| 21:54 | Phase 4.1: added POST /api/v1/data/upload-and-process/{pid} + _background_index to data.py | Routes/data.py | fire-and-forget upload+chunk+embed | ~400 |
| 21:54 | Phase 4.2: created Routes/projects.py with POST /api/v1/projects/sync + registered in main.py | Routes/projects.py, main.py | project_id_map upsert | ~200 |
| 21:54 | Fixed Connexios .env: EMBEDDING_BACKEND=COHERE, EMBEDDING_MODEL_ID=embed-multilingual-v3.0 | src/.env | matches MasarX embedding model | ~50 |
| 21:54 | Session end: 6 writes across 3 files (data.py, projects.py, main.py) | 16 reads | ~4942 tok |
| 22:03 | Created .dockerignore | — | ~134 |
| 22:03 | Edited Dockerfile | 4→4 lines | ~24 |
| 22:03 | Edited F:/MasarX_A/Dockerfile | 4→4 lines | ~24 |
| 22:04 | Phase 5: fixed both Dockerfiles (chown -R user), created Connexios .dockerignore, fixed EMBEDDING_BACKEND/MODEL_ID in Connexios .env | Dockerfile, .dockerignore, src/.env | HF deployment ready | ~200 |
| 22:05 | Session end: 9 writes across 5 files (data.py, projects.py, main.py, .dockerignore, Dockerfile) | 23 reads | ~6979 tok |
| 22:35 | Edited src/main.py | 2→2 lines | ~77 |
| 22:35 | Edited src/celery_app.py | 3→3 lines | ~76 |
| 22:35 | Edited src/celery_app.py | added 1 import(s) | ~28 |
| 22:36 | Edited src/celery_app.py | 3→6 lines | ~64 |
| 22:36 | Edited F:/MasarX_A/src/main.py | 1→2 lines | ~54 |
| 22:36 | Edited F:/MasarX_A/src/stores/vectordb/rag_tool.py | 1→2 lines | ~57 |
| 22:36 | Edited F:/MasarX_A/src/celery_app.py | added 1 import(s) | ~35 |
| 22:36 | Edited F:/MasarX_A/src/celery_app.py | 18→23 lines | ~231 |
| 22:45 | Session end: 17 writes across 7 files (data.py, projects.py, main.py, .dockerignore, Dockerfile) | 28 reads | ~10427 tok |
| 22:46 | Session end: 17 writes across 7 files (data.py, projects.py, main.py, .dockerignore, Dockerfile) | 28 reads | ~10427 tok |

## Session: 2026-05-12 23:03

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 23:04 | Edited CLAUDE.md | 4→4 lines | ~142 |
| 23:04 | Edited CLAUDE.md | 6→7 lines | ~128 |
| 23:04 | Edited CLAUDE.md | 1→3 lines | ~75 |
| 23:04 | Edited CLAUDE.md | 9→10 lines | ~158 |
| 23:04 | Edited CLAUDE.md | modified Agent() | ~292 |
| 23:04 | Edited CLAUDE.md | modified Agent() | ~63 |
| 23:10 | Fixed src/.env: POSTGRES_PORT 5433→5432 (Neon.tech pooler uses default port 5432) | src/.env | DB connection fix for ConnexioRag HF Space | ~20 |
| 23:10 | Updated CLAUDE.md: HF Spaces deployment status, Phase 4 done, Phase 5 partial, new routes | CLAUDE.md | Committed 8c87d22 | ~300 |
| 23:05 | Session end: 6 writes across 1 files (CLAUDE.md) | 2 reads | ~5358 tok |
| 23:09 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~64 |
| 23:09 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | 3→3 lines | ~34 |
| 23:09 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | 3→3 lines | ~30 |
| 23:09 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | 6→6 lines | ~61 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~14 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~13 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~18 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~15 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | 5→5 lines | ~47 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~9 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~11 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~23 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | 3→3 lines | ~47 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~11 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~11 |
| 23:10 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~13 |
| 23:11 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~13 |
| 23:11 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | 5→5 lines | ~55 |
| 23:11 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~15 |
| 23:11 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~12 |
| 23:11 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~14 |
| 23:11 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | 6→6 lines | ~83 |
| 23:11 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~27 |
| 23:11 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~24 |
| 23:11 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~32 |
| 23:11 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~20 |
| 23:11 | Edited F:/MasarX_A/docs/documentation/AGENT_RAG_INTEGRATION_STRATEGY.md | inline fix | ~23 |
| 23:12 | Session end: 33 writes across 2 files (CLAUDE.md, AGENT_RAG_INTEGRATION_STRATEGY.md) | 3 reads | ~6152 tok |

## Session: 2026-05-14 17:55

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 18:07 | Edited src/Routes/base.py | getenv() → health_check() | ~217 |
| 18:07 | Edited src/Routes/base.py | 5→3 lines | ~30 |
| 18:08 | Edited src/helpers/config.py | 4→4 lines | ~50 |
| 18:08 | Edited src/utils/backend_client.py | modified __init__() | ~62 |
| 18:08 | Edited src/utils/backend_client.py | modified _make_service_token() | ~192 |
| 18:09 | Rewrote phase6 Postman collection: CryptoJS JWT, fixed HITL token extraction, added x-api-key to 8a, busy-wait delays, cleared hardcoded secret | f:/MasarX_A/scratch/phase6_e2e_postman_collection.json | All 4 critical test bugs resolved | ~300 |
| 18:10 | Session: Phase 6 E2E test prep — fixed 4 Postman bugs, added RAG /health, hardened SERVICE_USER_ID config | 5 files across Connexios + MasarX_A | Collection ready for testing | ~2200 |
| 18:09 | Created f:/MasarX_A/scratch/phase6_e2e_postman_collection.json | — | ~5802 |
| 18:10 | Session end: 6 writes across 4 files (base.py, config.py, backend_client.py, phase6_e2e_postman_collection.json) | 13 reads | ~18756 tok |
| 18:13 | Created f:/MasarX_A/scratch/e2e_test_runner.py | — | ~5716 |
| 18:13 | Edited f:/MasarX_A/scratch/e2e_test_runner.py | modified hasattr() | ~85 |
| 18:16 | Edited f:/MasarX_A/scratch/e2e_test_runner.py | modified _load_env() | ~244 |
| 18:16 | Edited f:/MasarX_A/scratch/e2e_test_runner.py | expanded (+16 lines) | ~380 |
| 18:17 | Session end: 10 writes across 5 files (base.py, config.py, backend_client.py, phase6_e2e_postman_collection.json, e2e_test_runner.py) | 13 reads | ~25181 tok |
| 18:20 | Session end: 10 writes across 5 files (base.py, config.py, backend_client.py, phase6_e2e_postman_collection.json, e2e_test_runner.py) | 13 reads | ~25181 tok |
| 18:27 | Edited f:/MasarX_A/scratch/e2e_test_runner.py | 2→3 lines | ~57 |
| 18:27 | Edited f:/MasarX_A/scratch/e2e_test_runner.py | 2→5 lines | ~76 |

## Session: 2026-05-14 18:37

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 19:17 | Edited src/Routes/schemas/agent.py | modified AgentChatRequest() | ~149 |
| 19:17 | Edited src/Routes/agent.py | modified agent_chat() | ~190 |
| 19:17 | Edited src/Routes/agent.py | modified agent_chat_stream() | ~226 |
| 19:18 | Edited F:/connexio_back2/modules/chats/chatAIHelpers.js | 7→9 lines | ~136 |
| 19:19 | Edited F:/connexio_back2/socket.js | modified if() | ~285 |
| 19:19 | Edited F:/connexio_back2/modules/chats/chats.controller.js | expanded (+6 lines) | ~223 |
| 19:20 | Session end: @connexio feature — 4 bug fixes across 4 files | agent.py, chatAIHelpers.js, socket.js, chats.controller.js | RAG+backend wired for team mention + individual chatbot | ~8000 tok |
| 19:20 | Session end: 6 writes across 4 files (agent.py, chatAIHelpers.js, socket.js, chats.controller.js) | 10 reads | ~1209 tok |
| 23:26 | Session end: 6 writes across 4 files (agent.py, chatAIHelpers.js, socket.js, chats.controller.js) | 21 reads | ~1209 tok |
| 23:31 | Edited src/controllers/WorkflowController.py | modified __init__() | ~1409 |
| 23:31 | Edited src/controllers/NLPController.py | modified strip() | ~2064 |
| 23:32 | Edited src/controllers/NLPController.py | expanded (+20 lines) | ~396 |
| 23:32 | Edited src/controllers/NLPController.py | expanded (+18 lines) | ~398 |
| 23:32 | Edited src/stores/llm/templates/locales/en/rag.py | reduced (-16 lines) | ~158 |
| 23:33 | Edited src/stores/llm/templates/locales/ar/rag.py | reduced (-16 lines) | ~135 |

## Session: 2026-05-14 (scope + token fixes)

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| session | Fixed OUT_OF_SCOPE detection: added jailbreak keywords + _SKIP_FAST_PATH to stop "who is X" fast-pathing to GENERAL | WorkflowController.py | trivia/historical queries now go to LLM classifier | ~200 |
| session | Fixed CRAG: disabled external-tool fallback when project_id is None; refactored if/elif/else into clear 4-branch structure | NLPController.py | Wikipedia/Google no longer called for projectless sessions | ~150 |
| session | Added OUT_OF_SCOPE short-circuit in both answer_agent_chat and answer_agent_chat_stream — returns canned refusal, 0 LLM tokens | NLPController.py | out-of-scope queries: ~1300 tok → ~0 tok | ~200 |
| session | Compressed EN + AR system prompts from ~250 tok to ~55 tok each | en/rag.py, ar/rag.py | ~170 tok saved per request | ~100 |
| 23:33 | Session end: 12 writes across 7 files (agent.py, chatAIHelpers.js, socket.js, chats.controller.js, WorkflowController.py) | 22 reads | ~5769 tok |
| 23:53 | Edited src/controllers/NLPController.py | expanded (+6 lines) | ~319 |
| 23:53 | Edited src/controllers/NLPController.py | expanded (+13 lines) | ~459 |
| 23:53 | Edited src/controllers/NLPController.py | inline fix | ~33 |
| 23:53 | Edited src/controllers/NLPController.py | 30→30 lines | ~398 |
| 23:53 | Edited src/controllers/NLPController.py | 8→8 lines | ~108 |
| 23:54 | Edited src/controllers/NLPController.py | 27→27 lines | ~402 |
| 23:54 | Edited src/controllers/NLPController.py | modified generate_text_stream() | ~47 |
| 23:54 | Session end: 19 writes across 7 files (agent.py, chatAIHelpers.js, socket.js, chats.controller.js, WorkflowController.py) | 22 reads | ~16173 tok |
| 00:02 | Edited CLAUDE.md | expanded (+15 lines) | ~876 |
| 00:03 | Edited README.md | modified sessions() | ~655 |
| 00:03 | Edited README.md | modified context() | ~666 |
| 00:03 | Edited f:/MasarX_A/README.md | 15→16 lines | ~218 |
| 00:04 | Edited f:/MasarX_A/README.md | 38→35 lines | ~503 |
| 00:04 | Edited f:/MasarX_A/README.md | 13→13 lines | ~479 |
| 00:04 | Session end: 25 writes across 9 files (agent.py, chatAIHelpers.js, socket.js, chats.controller.js, WorkflowController.py) | 25 reads | ~24252 tok |

## Session: 2026-05-16 11:10

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 11:38 | Edited f:/MasarX_A/src/utils/tools/db_tool.py | modified initialize() | ~375 |
| 11:38 | Edited f:/MasarX_A/src/main.py | 4→9 lines | ~126 |
| 11:38 | Edited f:/MasarX_A/src/models/db_schemas/live_models.py | modified PendingPlan() | ~336 |
| 11:38 | Edited f:/MasarX_A/src/main.py | 3→3 lines | ~75 |
| 11:39 | Edited f:/MasarX_A/src/utils/tools/db_tool.py | modified save_webhook_result() | ~247 |
| 11:39 | Edited f:/MasarX_A/src/utils/tools/db_tool.py | 2→1 lines | ~4 |
| 11:39 | Edited f:/MasarX_A/src/Routes/webhook_routes.py | modified run_workflow() | ~357 |
| 11:39 | Edited f:/MasarX_A/src/Routes/webhook_routes.py | modified get_webhook_results() | ~437 |
| 11:40 | Edited f:/MasarX_A/src/Routes/webhook_routes.py | modified get_webhook_result() | ~532 |
| 11:40 | Created src/utils/masarx_client.py | — | ~942 |
| 11:40 | Edited src/main.py | 6→9 lines | ~103 |
| 11:40 | Edited src/Routes/agent.py | 11→12 lines | ~190 |
| 11:41 | Edited src/controllers/NLPController.py | modified __init__() | ~280 |
| 11:41 | Edited src/controllers/NLPController.py | 27→30 lines | ~437 |
| 11:41 | Edited src/controllers/NLPController.py | 18→19 lines | ~255 |
| 11:42 | Edited src/controllers/helpers/ToolManager.py | modified __init__() | ~260 |
| 11:42 | Edited src/controllers/helpers/ToolManager.py | modified get_masarx_tasks() | ~333 |

## Session: 2026-05-16 11:44

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 11:44 | Edited src/controllers/NLPController.py | modified in() | ~236 |
| 11:46 | Edited f:/connexio_back2/models/Message.js | 6→7 lines | ~76 |
| 11:46 | Edited f:/connexio_back2/services/aiService.js | 9→9 lines | ~111 |
| 11:47 | Edited f:/connexio_back2/modules/ai/ai.routes.js | modified catch() | ~342 |
| 11:47 | Edited f:/connexio_back2/modules/chats/chatAIHelpers.js | 2→2 lines | ~36 |
| 11:47 | Edited f:/connexio_back2/modules/chats/chatAIHelpers.js | 6→6 lines | ~102 |
| 11:47 | Edited f:/connexio_back2/socket.js | 9→13 lines | ~160 |
| 11:47 | Edited f:/connexio_back2/socket.js | added error handling | ~1332 |
| 11:47 | Edited f:/connexio_back2/bootstrap.js | added 1 import(s) | ~32 |
| 11:47 | Edited f:/connexio_back2/bootstrap.js | expanded (+18 lines) | ~272 |
| 11:48 | Edited f:/Connexio_Frontend2/src/pages/ConnexioAI.jsx | added 1 condition(s) | ~145 |
| 11:48 | Edited f:/Connexio_Frontend2/src/pages/ConnexioAI.jsx | added optional chaining | ~523 |
| 11:48 | Edited f:/Connexio_Frontend2/src/components/ChatWidget.jsx | 4→5 lines | ~63 |
| 11:48 | Edited f:/Connexio_Frontend2/src/components/ChatWidget.jsx | CSS: roomId | ~141 |
| 11:48 | Edited f:/Connexio_Frontend2/src/components/ChatWidget.jsx | 3→3 lines | ~32 |
| 11:49 | Edited f:/Connexio_Frontend2/src/components/ChatWidget.jsx | expanded (+10 lines) | ~127 |
| 11:49 | Edited f:/MasarX_A/src/tasks/cron_jobs.py | modified _run_workload_scan() | ~150 |
| 11:49 | Edited f:/MasarX_A/src/tasks/cron_jobs.py | modified _run_risk_scan() | ~147 |
| 11:49 | Edited f:/MasarX_A/src/stores/vectordb/rag_tool.py | removed 10 lines | ~8 |
| 11:49 | Edited f:/MasarX_A/src/stores/vectordb/rag_tool.py | 5→7 lines | ~105 |
| 11:50 | Session end: 20 writes across 11 files (NLPController.py, Message.js, aiService.js, ai.routes.js, chatAIHelpers.js) | 15 reads | ~14102 tok |
| 11:52 | Session end: 20 writes across 11 files (NLPController.py, Message.js, aiService.js, ai.routes.js, chatAIHelpers.js) | 15 reads | ~14102 tok |
| 11:59 | Session end: 20 writes across 11 files (NLPController.py, Message.js, aiService.js, ai.routes.js, chatAIHelpers.js) | 15 reads | ~14102 tok |
| 12:45 | Edited f:/MasarX_A/src/stores/llm/LLMProviderFactory.py | modified create_utility_client() | ~86 |
| 12:45 | Edited f:/MasarX_A/src/main.py | 2→4 lines | ~54 |
| 12:46 | Session end: 22 writes across 13 files (NLPController.py, Message.js, aiService.js, ai.routes.js, chatAIHelpers.js) | 19 reads | ~15779 tok |
| 12:59 | Edited src/controllers/NLPController.py | 8→4 lines | ~30 |
| 12:59 | Edited src/controllers/NLPController.py | 9→10 lines | ~152 |
| 12:59 | Edited src/controllers/NLPController.py | modified strip() | ~150 |
| 13:00 | Edited src/stores/llm/templates/locales/en/rag.py | 3→3 lines | ~43 |
| 13:00 | Edited src/stores/llm/templates/locales/ar/rag.py | "الشخصية: $persona | السيا" → "الجمهور المستهدف: متعلم م" | ~18 |
| 13:00 | Session end: 27 writes across 14 files (NLPController.py, Message.js, aiService.js, ai.routes.js, chatAIHelpers.js) | 21 reads | ~16751 tok |

## Session: 2026-05-16 (project_id resolve + auth + chunking fixes)

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 14:49 | Investigated project_id=0 in RAG streaming URL — found hardcoded 0 in socket.js | socket.js | root cause identified | ~200 |
| 14:49 | Added resolveProjectId(chatRoom, userId) helper with metadata check + DB fallback in socket.js | socket.js | replaces hardcoded 0 | ~300 |
| 14:49 | Updated createAIChatbot to accept projectId in body, store in room metadata | chats.controller.js | project context stored on room | ~150 |
| 14:50 | Updated ConnexioAI.jsx: read projectId from URL params, auto-create session on navigation | ConnexioAI.jsx | frontend passes project context | ~250 |
| 14:50 | Added AI Assistant button in ProjectDetail.jsx overview tab | ProjectDetail.jsx | navigates to /ai-chat?projectId=X | ~100 |
| 14:51 | Removed sources.append("Live Backend Data") from NLPController | NLPController.py | source tag no longer shown to user | ~50 |
| 14:51 | Fixed get_project_context_summary to unwrap data field from backend API responses | ToolManager.py | N/A project/description fixed | ~200 |
| 14:51 | Added X-API-Key to outbound headers in BackendApiClient._headers() | backend_client.py | RAG can auth to backend | ~50 |
| 14:51 | Added X-API-Key bypass to protect middleware | authMiddleware.js | internal services skip JWT | ~100 |
| 14:51 | Increased limit: 5 → 20 in socket.js RAG params | socket.js | more chunks retrieved per query | ~30 |
| 14:54 | Uploaded test document to project 27 (chunk_size=500, do_reset=1) | — | 3 chunks indexed | ~50 |
| 14:55 | Verified via UI — project context flows, answers use doc content | — | core fix working | ~100 |
| 15:00 | Session end: project_id resolve + auth fixes + chunking — full stack end to end tested | 7 files | Ready for production | ~1800 |

## Session: 2026-05-16 22:51

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
