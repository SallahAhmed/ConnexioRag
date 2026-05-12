# Multi-Source RAG Implementation Tasks

- `[ ]` **Phase 1: Workflow Routing**
    - `[ ]` Create `WorkflowController.py` for intent classification.
    - `[ ]` Implement node detection (Onboarding, Team Formation, etc.).
    - `[ ]` Integrate persona and language detection.

- `[ ]` **Phase 2: Tool Integration**
    - `[ ]` Create `ToolManager.py`.
    - `[ ]` Implement **Text-to-SQL** tool using SQLAlchemy schema.
    - `[ ]` Integrate LangChain **Wikipedia** tool.
    - `[ ]` Wrap existing Vector Search as a tool.

- `[ ]` **Phase 3: Controller Expansion**
    - `[ ]` Update `NLPController.answer_rag_question` to use the ToolManager.
    - `[ ]` Implement logic to aggregate results from multiple tools.
    - `[ ]` Update prompt construction to include persona-based tone.

- `[ ]` **Phase 4: Templates & Polish**
    - `[ ]` Add node-specific templates to `locales/en` and `locales/ar`.
    - `[ ]` Implement "Freemium" logic mentions in system prompts.
    - `[ ]` Verify matching algorithm weights.

- `[ ]` **Phase 5: Verification**
    - `[ ]` Test Text-to-SQL with project table queries.
    - `[ ]` Test Wikipedia tool with general knowledge queries.
    - `[ ]` Validate multi-language response consistency.
