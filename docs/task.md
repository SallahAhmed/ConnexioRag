# Multi-Source RAG Implementation Tasks

- `[x]` **Phase 1: Workflow Routing**
    - `[x]` Create `WorkflowController.py` for intent classification.
    - `[x]` Implement node detection (Onboarding, Team Formation, etc.).
    - `[x]` Integrate persona and language detection.

- `[x]` **Phase 2: Tool Integration**
    - `[x]` Create `ToolManager.py`.
    - `[x]` Implement **Text-to-SQL** tool using SQLAlchemy schema.
    - `[x]` Integrate LangChain **Wikipedia** tool.
    - `[x]` Wrap existing Vector Search as a tool.

- `[x]` **Phase 3: Controller Expansion**
    - `[x]` Update `NLPController.answer_rag_question` to use the ToolManager.
    - `[x]` Implement logic to aggregate results from multiple tools.
    - `[x]` Update prompt construction to include persona-based tone.

- `[x]` **Phase 4: Templates & Polish**
    - `[x]` Add node-specific templates to `locales/en` and `locales/ar`.
    - `[x]` Implement "Freemium" logic mentions in system prompts.
    - `[x]` Verify matching algorithm weights.

- `[/]` **Phase 5: Verification**
    - `[ ]` Test Text-to-SQL with project table queries.
    - `[ ]` Test Wikipedia tool with general knowledge queries.
    - `[ ]` Validate multi-language response consistency.
