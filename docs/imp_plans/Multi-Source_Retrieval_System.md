# Multi-Source Data Retrieval & Workflow Node System

This plan outlines the architecture and implementation steps to evolve the current RAG model into a multi-source agentic system capable of querying structured SQL data, external knowledge (Wikipedia), and internal document batches (Vector DB). It also implements the "Workflow Node" architecture described in the project tasks.

## User Review Required

> [!IMPORTANT]
> This change introduces **Agentic behavior**. The LLM will now decide which tool to use based on the query. This may increase token usage and latency for complex queries.

> [!WARNING]
> **Text-to-SQL**: We will use LangChain's SQL tools. For this to be safe and accurate, we need to provide the LLM with a clear schema description. I will implement a "Schema Provider" that limits the model's view to relevant tables (`projects`, `data_chunks`, `assets`).

## Proposed Changes

### 1. Workflow Routing Layer
We will implement a `WorkflowController` that classifies user intent into the nodes requested: `ONBOARDING`, `TEAM_FORMATION`, `PHASE_TRANSITION`, `BLOCKER`, `MILESTONE_WARNING`, or `GENERAL`.

#### [NEW] WorkflowController.py
- Logic to detect the workflow node using a lightweight LLM call or keyword matching.
- Maps each node to a specific retrieval strategy.

### 2. Multi-Source Retrieval (Tools)
We will introduce a `ToolManager` that wraps various data sources.

#### [NEW] ToolManager.py
- **SQL Tool**: Uses `langchain_community.utilities.SQLDatabase` to connect to the existing PostgreSQL instance. Converts English to SQL.
- **Wikipedia Tool**: Integrates `langchain_community.tools.WikipediaQueryRun`.
- **Knowledge Tool**: Wraps the existing `search_vector_db_collection` logic.

### 3. Controller Updates
Modify `NLPController` to move from a single-source RAG to a multi-source "Grounded Response" system.

#### [MODIFY] NLPController.py
- Update `answer_rag_question` to:
    1. Call the `WorkflowRouter`.
    2. Depending on the node/query, trigger the relevant tools from `ToolManager`.
    3. Aggregate tool outputs (SQL results, Wikipedia snippets, Vector chunks).
    4. Generate a final response in the detected language (Arabic/English).

### 4. Prompt Templates
Update the template system to handle different nodes.

#### [MODIFY] templates.json
- Add node-specific system prompts.
- Add "Persona" instructions (Student vs Early-career) as requested in v2.

## Open Questions

> [!IMPORTANT]
> For the **Text-to-SQL** part: Do you have a specific list of "Admin" tables or "Business" tables that the model should *not* see? Currently, I plan to expose `projects`, `data_chunks`, and `assets`.

> [!NOTE]
> Which LLM model do you want to use for the "Workflow Node Detection"? I recommend the same one used for generation, or a faster one if available.

## Verification Plan

### Automated Tests
- `pytest` for the `WorkflowController` to ensure keywords route to correct nodes.
- Mock database queries to verify Text-to-SQL logic doesn't generate destructive SQL.

### Manual Verification
- Ask "How many projects are currently registered?" (Tests SQL Tool).
- Ask "What is RAG according to Wikipedia?" (Tests Wikipedia Tool).
- Ask project-specific questions from uploaded files (Tests Vector DB).
