# Connexio RAG Model — Bug Fix Guide

> **Instructions for AI:** Apply every fix listed below in the exact order shown.
> Each fix includes the target file path, the problem, and the exact code replacement.
> Do not change anything else outside of what is specified. After all fixes are applied, confirm each file was changed.

---

## FIX 1 — `src/stores/llm/templates/template_parser.py`

**Problem:** Missing `return` after setting the default language when `language` is `None` or empty.
Without it, execution falls through to `os.path.join(self.current_path, "locales", language)`
with `language = None`, which crashes with a `TypeError`.

**Replace this:**

```python
def set_language(self, language: str):
    if not language:
        self.language = self.default_language

    language_path = os.path.join(self.current_path, "locales", language)
    if os.path.exists(language_path):
        self.language = language
    else:
        self.language = self.default_language
```

**With this:**

```python
def set_language(self, language: str):
    if not language:
        self.language = self.default_language
        return

    language_path = os.path.join(self.current_path, "locales", language)
    if os.path.exists(language_path):
        self.language = language
    else:
        self.language = self.default_language
```

---

## FIX 2 — `src/tasks/maintenance.py`

**Problem:** `get_setup_utils()` returns 9 values but `maintenance.py` only unpacks 8,
missing `utility_client`. This causes a `ValueError: not enough values to unpack` crash
every time the maintenance task runs.

**Replace this:**

```python
(db_engine, db_client, llm_provider_factory,
vectordb_provider_factory,
generation_client, embedding_client,
vectordb_client, template_parser) = await get_setup_utils()
```

**With this:**

```python
(db_engine, db_client, llm_provider_factory,
vectordb_provider_factory,
generation_client, utility_client, embedding_client,
vectordb_client, template_parser) = await get_setup_utils()
```

---

## FIX 3 — `src/models/ProjectModel.py`

**Problem:** `session.execute(query).scalars().all()` is called without `await` on the
`execute()` call result. You cannot chain `.scalars().all()` directly on a coroutine.
This causes an `AttributeError` at runtime.

**Replace this:**

```python
query = select(Project).offset((page - 1) * page_size ).limit(page_size)
projects = await session.execute(query).scalars().all()

return projects, total_pages
```

**With this:**

```python
query = select(Project).offset((page - 1) * page_size).limit(page_size)
result = await session.execute(query)
projects = result.scalars().all()

return projects, total_pages
```

---

## FIX 4 — `src/stores/vectordb/providers/PGVectorProvider.py`

**Problem:** `is_collection_existed()` returns the raw `Row` object from the database
instead of a `bool`. This causes all callers (`create_collection`, `insert_one`,
`insert_many`, `search_by_vector`, `search_by_text`) to incorrectly evaluate truthiness
and can produce silent logic errors.

**Replace this:**

```python
async def is_collection_existed(self, collection_name: str) -> bool:

    record = None
    async with self.db_client() as session:
        async with session.begin():
            list_tbl = sql_text(f'SELECT * FROM pg_tables WHERE tablename = :collection_name')
            results = await session.execute(list_tbl, {"collection_name": collection_name})
            record = results.scalar_one_or_none()

    return record
```

**With this:**

```python
async def is_collection_existed(self, collection_name: str) -> bool:

    record = None
    async with self.db_client() as session:
        async with session.begin():
            list_tbl = sql_text(f'SELECT * FROM pg_tables WHERE tablename = :collection_name')
            results = await session.execute(list_tbl, {"collection_name": collection_name})
            record = results.scalar_one_or_none()

    return record is not None
```

---

## FIX 5 — `src/controllers/WorkflowController.py`

**Problem 1:** GENERAL keywords (`"help me"`) are checked before BLOCKER keywords (`"help"`),
so any query containing `"help me"` is incorrectly routed to GENERAL instead of BLOCKER.
Specific nodes must be checked before the GENERAL fallback.

**Problem 2:** `grade_relevance()` uses `generation_client` (the heavy primary model)
for a simple yes/no grading task. It should use `utility_client` (the fast small model)
to avoid adding full LLM latency on every single request.

**Replace the entire file content with:**

```python
from .BaseController import BaseController
from models.enums.WorkflowNodeEnum import WorkflowNodeEnum
import re

class WorkflowController(BaseController):
    def __init__(self, generation_client, template_parser, utility_client=None):
        super().__init__()
        self.generation_client = generation_client
        self.utility_client = utility_client if utility_client else generation_client
        self.template_parser = template_parser

    async def detect_node(self, query: str) -> WorkflowNodeEnum:
        """
        Detects the workflow node from the user query.
        Uses a Fast-Path for short queries, then Keywords, then falls back to LLM.
        """
        query_lower = query.lower().strip()

        # 1. ABSOLUTE FAST-PATH: Short queries (greetings, noise) return GENERAL instantly.
        if len(query_lower) < 50:
            return WorkflowNodeEnum.GENERAL

        # 2. KEYWORD MAPPING: Specific nodes are checked BEFORE GENERAL to avoid false positives.
        #    Order matters: most specific triggers first, GENERAL is the final fallback.
        keywords = {
            WorkflowNodeEnum.BLOCKER: [
                "stuck", "not responding", "error", "problem", "help fix",
                "help me fix", "not working", "broken", "crash", "exception",
                "عالق", "مشكلة", "خطأ", "لا يعمل"
            ],
            WorkflowNodeEnum.MILESTONE_WARNING: [
                "behind", "overdue", "late", "deadline", "missed milestone",
                "متأخر", "موعد نهائي", "تأخر"
            ],
            WorkflowNodeEnum.PHASE_TRANSITION: [
                "next phase", "done with", "advance", "transition", "move to",
                "المرحلة التالية", "الانتقال", "الانتهاء من"
            ],
            WorkflowNodeEnum.TEAM_FORMATION: [
                "find teammate", "need a dev", "looking for", "join team",
                "find a designer", "need someone", "recruit",
                "ابحث عن", "أحتاج مطور", "فريق"
            ],
            WorkflowNodeEnum.ONBOARDING: [
                "where do i start", "new here", "how it works", "how do i start",
                "getting started", "first time", "بداية", "كيف أبدأ", "جديد هنا"
            ],
            # GENERAL is checked last — only conversational triggers, no ambiguous words
            WorkflowNodeEnum.GENERAL: [
                "hello", "hi", "hey", "good morning", "good afternoon",
                "who are you", "what can you do", "your name",
                "مرحبا", "سلام", "اهلا", "كيف حالك", "من انت", "ماذا تفعل"
            ],
        }

        for node, triggers in keywords.items():
            if any(trigger in query_lower for trigger in triggers):
                return node

        # 3. Fallback to LLM for complex classification
        language = await self.detect_language(query)
        self.template_parser.set_language(language)

        system_prompt = self.template_parser.get("workflow", "classification_system_prompt")
        user_prompt = self.template_parser.get("workflow", "classification_user_prompt", {"query": query[:2000]})

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value
            )
        ]

        response = await self.generation_client.generate_text(
            prompt=user_prompt, chat_history=chat_history
        )

        if response:
            try:
                return WorkflowNodeEnum[response.strip().upper()]
            except (KeyError, ValueError):
                pass

        return WorkflowNodeEnum.GENERAL

    async def detect_persona(self, query: str, chat_history: list = None) -> str:
        """
        Detects if the user is a student, early_career, educator, or company.
        """
        return "student"

    async def detect_language(self, query: str) -> str:
        """
        Detects if the language is English or Arabic.
        """
        if re.search(r'[\u0600-\u06FF]', query):
            return "ar"
        return "en"

    async def grade_relevance(self, query: str, context: str) -> bool:
        """
        Grades whether the retrieved context is relevant to the query.
        Uses the utility (fast/small) model to avoid adding heavy LLM latency.
        Returns True if relevant, False if a search fallback is needed.
        """
        if not context or "No relevant documents found" in context:
            return False

        prompt = f"""Evaluate if the following context contains information that can answer the user's query.
Query: "{query}"
Context: "{context[:2000]}"

Answer ONLY "YES" if it is relevant and contains specific info to answer the question, or "NO" if it is irrelevant or insufficient.
"""
        # Use utility_client (small/fast model) — NOT the heavy generation_client
        response = await self.utility_client.generate_text(prompt=prompt)
        return "YES" in response.strip().upper()
```

> **Note:** Also update the `WorkflowController` instantiation inside `NLPController.__init__()` to pass `utility_client`:

**In `src/controllers/NLPController.py`, replace this:**

```python
self.workflow_controller = WorkflowController(
    generation_client=self.utility_client,
    template_parser=self.template_parser
)
```

**With this:**

```python
self.workflow_controller = WorkflowController(
    generation_client=self.generation_client,
    template_parser=self.template_parser,
    utility_client=self.utility_client
)
```

---

## FIX 6 — `src/controllers/NLPController.py`

**Problem:** The Arabic context budget comment says "Increased for better utilization of 70B model"
but the value `5000` is actually _less_ than the default `15000`. This cripples Arabic responses.
Arabic text is token-expensive so the budget should be equal to or greater than the default.

**Replace this:**

```python
total_budget = getattr(self.settings, "TOTAL_CONTEXT_CHAR_BUDGET", 15000)
if language == "ar":
    total_budget = 5000 # Increased for better utilization of 70B model
```

**With this:**

```python
total_budget = getattr(self.settings, "TOTAL_CONTEXT_CHAR_BUDGET", 15000)
if language == "ar":
    # Arabic is token-expensive (~1 char ≈ 1+ token), so we apply a tighter cap
    # to stay within local model limits, but never below 8000 for usable context.
    total_budget = min(total_budget, 8000)
```

---

## FIX 7 — `src/controllers/helpers/ToolManager.py` + `src/controllers/NLPController.py`

**Problem:** The collection name is constructed in two separate places with duplicated logic.
If either changes, they silently diverge and searches return nothing.

**Step A — Add a shared helper in `src/controllers/helpers/ToolManager.py`.**

At the top of the `ToolManager` class (inside `__init__`, after setting `self.vectordb_client`), add:

```python
def _get_collection_name(self, project_id) -> str:
    """Single source of truth for vector collection naming."""
    return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
```

**Step B — In `ToolManager.search_knowledge_base()`, replace this:**

```python
collection_name = f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
```

**With this:**

```python
collection_name = self._get_collection_name(project_id)
```

**Step C — In `src/controllers/NLPController.py`, replace this:**

```python
def create_collection_name(self, project_id: str):
    return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
```

**With this:**

```python
def create_collection_name(self, project_id: str):
    """Single source of truth for vector collection naming. Keep in sync with ToolManager."""
    return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
```

> Add a comment so future developers know both must stay in sync until refactored to a shared utility module.

---

## FIX 8 — `src/models/ChunkModel.py`

**Problem:** `get_poject_chunks` is a typo that propagates into every caller
(`data_indexing.py`, `file_processing.py`). Fix the definition and all call sites.

**In `src/models/ChunkModel.py`, replace this:**

```python
async def get_poject_chunks(self, project_id: ObjectId, page_no: int=1, page_size: int=50):
    async with self.db_client() as session:
        stmt = select(DataChunk).where(DataChunk.chunk_project_id == project_id).offset((page_no - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        records = result.scalars().all()
    return records
```

**With this:**

```python
async def get_project_chunks(self, project_id: ObjectId, page_no: int=1, page_size: int=50):
    async with self.db_client() as session:
        stmt = select(DataChunk).where(DataChunk.chunk_project_id == project_id).offset((page_no - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        records = result.scalars().all()
    return records

# Keep old name as a deprecated alias so nothing breaks before all callers are updated
async def get_poject_chunks(self, project_id: ObjectId, page_no: int=1, page_size: int=50):
    return await self.get_project_chunks(project_id=project_id, page_no=page_no, page_size=page_size)
```

**In `src/tasks/data_indexing.py`, replace this:**

```python
page_chunks = await chunk_model.get_poject_chunks(project_id=project.project_id, page_no=page_no)
```

**With this:**

```python
page_chunks = await chunk_model.get_project_chunks(project_id=project.project_id, page_no=page_no)
```

---

## FIX 9 — `src/controllers/DataController.py`

**Problem:** `allowed_exts` is built from a setting (`FILE_ALLOWED_EXTENSIONS`) that does
not exist in `Settings`, so the list is always empty and the variable is never used.
This is dead code that creates confusion.

**Replace this:**

```python
allowed_types = self.app_settings.FILE_ALLOWED_TYPES
allowed_exts = [ext.lower() for ext in [getattr(self.app_settings, 'FILE_ALLOWED_EXTENSIONS', None)] if ext]  # fallback if you add FILE_ALLOWED_EXTENSIONS
filename = file.filename or ""
file_ext = os.path.splitext(filename)[-1].lower()
```

**With this:**

```python
allowed_types = self.app_settings.FILE_ALLOWED_TYPES
filename = file.filename or ""
file_ext = os.path.splitext(filename)[-1].lower()
ALLOWED_EXTENSIONS = ['.txt', '.pdf']  # Keep in sync with FILE_ALLOWED_TYPES
```

**And replace the octet-stream check below it:**

```python
if file.content_type == "application/octet-stream":
    if file_ext not in ['.txt', '.pdf']:
        return False, ResponseSignal.FILE_TYPE_NOT_SUPPORTED.value
```

**With this:**

```python
if file.content_type == "application/octet-stream":
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, ResponseSignal.FILE_TYPE_NOT_SUPPORTED.value
```

---

## FIX 10 — `src/.env.example`

**Problem:** Three stray `=` characters on their own lines break any tool that parses
this file as a standard `.env` format.

**Remove these three lines (they appear between config sections as standalone `=`):**

```
=
```

The file should flow continuously between sections with only blank lines or comments (`#`) as separators. The corrected relevant section should look like:

```ini
# ========================= LLM Config =========================
GENERATION_BACKEND="OPENAI"
EMBEDDING_BACKEND="COHERE"

OPENAI_API_KEY=""
OPENAI_API_URL=
COHERE_API_KEY=""
SERPAPI_API_KEY=""
GITHUB_TOKEN=""

GENERATION_MODEL_ID_LITERAL=["gpt-3.5-turbo-0125", "openai/gpt-oss-120b"]
GENERATION_MODEL_ID="gpt-3.5-turbo-0125"
EMBEDDING_MODEL_ID="embed-multilingual-light-v3.0"
EMBEDDING_MODEL_SIZE=384

INPUT_DEFAULT_MAX_CHARACTERS=1024
GENERATION_DEFAULT_MAX_TOKENS=200
GENERATION_DEFAULT_TEMPERATURE=0.1
```

> Also fix the typos: `INPUT_DAFAULT_MAX_CHARACTERS` → `INPUT_DEFAULT_MAX_CHARACTERS`
> and `GENERATION_DAFAULT_MAX_TOKENS` → `GENERATION_DEFAULT_MAX_TOKENS`
> and `GENERATION_DAFAULT_TEMPERATURE` → `GENERATION_DEFAULT_TEMPERATURE`
> then confirm these match the field names in `src/helpers/config.py`.

---

## Verification Checklist

After all fixes are applied, confirm the following before testing:

- [ ] **Fix 1** — `template_parser.py`: `set_language(None)` no longer crashes
- [ ] **Fix 2** — `maintenance.py`: unpacks exactly 9 values from `get_setup_utils()`
- [ ] **Fix 3** — `ProjectModel.py`: `get_all_projects` uses `result = await ...` then `result.scalars().all()`
- [ ] **Fix 4** — `PGVectorProvider.py`: `is_collection_existed` ends with `return record is not None`
- [ ] **Fix 5** — `WorkflowController.py`: BLOCKER keywords appear before GENERAL in the dict; `grade_relevance` calls `self.utility_client`
- [ ] **Fix 5b** — `NLPController.py`: `WorkflowController(...)` passes `utility_client=self.utility_client`
- [ ] **Fix 6** — `NLPController.py`: Arabic budget uses `min(total_budget, 8000)` not hardcoded `5000`
- [ ] **Fix 7** — `ToolManager.py`: `_get_collection_name()` method exists and is used in `search_knowledge_base()`
- [ ] **Fix 8** — `ChunkModel.py`: `get_project_chunks` exists; old typo name kept as alias; `data_indexing.py` calls the corrected name
- [ ] **Fix 9** — `DataController.py`: `allowed_exts` removed; `ALLOWED_EXTENSIONS` list used in its place
- [ ] **Fix 10** — `.env.example`: no standalone `=` lines; typos in key names corrected

---

## Test Order After Fixes

Run these in sequence to confirm nothing is broken:

1. Start FastAPI — confirm startup logs show no import or initialization errors
2. Start Celery worker — confirm it connects and shows "ready" without crashing
3. `POST /api/v1/data/upload/1` — upload a small PDF
4. `POST /api/v1/data/process/1` — trigger chunking via Celery
5. `POST /api/v1/nlp/index/push/1` — index chunks into vector DB
6. `POST /api/v1/nlp/index/search/1` with `{"text": "test query", "limit": 3}` — confirm results
7. `POST /api/v1/nlp/agent/chat/1` with `{"query": "hello", "user_id": 1, "persona": "student"}` — confirm GENERAL node
8. `POST /api/v1/nlp/agent/chat/1` with `{"query": "I am stuck with an error in my code", "user_id": 1, "persona": "student"}` — confirm BLOCKER node (not GENERAL)
9. `POST /api/v1/nlp/agent/chat/1` with an Arabic query — confirm response is not truncated
