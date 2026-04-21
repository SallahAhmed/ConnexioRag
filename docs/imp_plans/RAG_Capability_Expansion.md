# RAG Task Enhancements Implementation

The objective is to implement the 15+ capabilities outlined in `RAG MODEL Tasks.txt`, which ranges from basic project Q&A to generating READMEs and scoring team compatibility based on profile capabilities. 

To achieve this without creating a monolithic, spaghetti-code endpoint, we must modularize our prompts by task intent and add precise routes for specialized features. 

> [!WARNING]
> Currently, `TemplateParser` is commented out in `main.py` and missing from `stores.llm.templates`. Because `NLPController.py` relies on `self.template_parser.get("rag", "system_prompt")`, no RAG answers can be generated right now. Re-establishing prompt templates is a priority before anything else.

## Proposed Changes

---

### Prompt Management & Template Parser Configuration

Since we have a wide array of RAG functionality, we should define distinct System Prompts tailored to specific actions instead of one generic "Answer this" prompt.

#### [NEW] `src/stores/llm/templates/template_parser.py`
We will establish a basic prompt parser class that loads prompt configurations (either from YAML, JSON, or code dicts).

#### [NEW] `src/assets/prompts.yaml` (or equivalent)
Define specialized prompts for different tasks:
- `default_qa`: General assistant for project context.
- `readme_generation`: Specialized system instruction formatting context into a structured Markdown README.
- `profile_matching`: Instruction set for evaluating user profiles against a project's technical/resource needs and scoring compatibility.

#### [MODIFY] `src/main.py`
Uncomment and properly inject the `TemplateParser` dependency into the FastAPI application state so `NLPController` can use it.

---

### Request Schema Updates

To support generic task branching, we will update the `SearchRequest` schema.

#### [MODIFY] `src/Routes/schemas/nlp.py`
Add a `task_type` field explicitly mapping to our new templates.
```python
class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 5
    task_type: Optional[str] = "default_qa"  # e.g., 'default_qa', 'readme_generation', 'profile_matching'
```

---

### Dynamic RAG Answer Controller

We will update the `answer_rag_question` method to dynamically load templates based on the task type requested.

#### [MODIFY] `src/controllers/NLPController.py`
Amend `answer_rag_question` to determine which system prompt to load using `task_type`. E.g.:
```python
system_prompt = self.template_parser.get(task_type, "system_prompt")
```
This single change supports 80% of the Q&A specific tasks in the list (tasks 1-13) simply by passing different `task_type` hints and appropriately constructed prompts!

---

### Specialized High Priority Endpoints (!) 

The tasks marked with `!` dictate specialized behavior that typically wrap the core RAG function, taking parameters and returning highly structured JSON or Markdown formats.

#### [MODIFY] `src/Routes/nlp.py`
Add explicit specialized endpoints:
1. **`/index/generate-readme/{project_id}` (POST)**
   * Forces generation of a README.md string by performing a broad retrieve on project description, stack, contributors, and milestones and feeding it to the `readme_generation` prompt task.
2. **`/index/match-profile/{project_id}` (POST)**
   * Receives a specific profile ID or profile data payload.
   * Retrieves relevant team roles and project skill requests from the vector DB.
   * Prompts the LLM to score compatibility and explain "Why was I matched" (covering tasks 12 & 15).

## Open Questions

> [!IMPORTANT]
> - Do you already have a `TemplateParser` built in a different branch or directory that I shouldn't overwrite, or shall I create a simple YAML/dict based implementation in `src/stores/llm/templates/`?
> - For "Profile Compatibility" and "README Generation", should the response return direct Markdown strings, or a structured JSON with specific metadata (e.g., {"score": 85, "reason": "..."})?

## Verification Plan

### Automated Tests
* N/A - we will curl the API via Postman or script.

### Manual Verification
1. Start the FastAPI development server.
2. Load a test document/profile into a dummy project via `/index/push/{project_id}`.
3. Test standard Q&A with `/index/answer/{project_id}` to verify `TemplateParser` is wired properly.
4. Call `/index/generate-readme/{project_id}` and verify Markdown returned.
5. Call `/index/match-profile/{project_id}` and verify compatibility scoring works.
