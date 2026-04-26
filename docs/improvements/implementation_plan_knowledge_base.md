# Implementation Plan: Knowledge Base Strategy

This plan outlines the steps to build, organize, and maintain a high-quality knowledge base for the Connexio RAG system, covering both Technical and Non-Technical domains.

## Phase 1: Knowledge Audit & Categorization

**Goal**: Identify the "Knowledge Gaps" in your current project.

- **Action**: Create a "Knowledge Matrix" for each project ID.
- **Tasks**:
  - [ ] Audit existing `README.md` and codebase for technical instructions.
  - [ ] List required domain knowledge (e.g., History, Economics, Engineering) for the specific project.
  - [ ] Identify common "Blockers" students face and document the solutions.

## Phase 2: Document Standardization (RAG-Ready)

**Goal**: Ensure the AI can ingest documents with high fidelity.

- **Action**: Standardize all sources into clean `.txt` or `.pdf` formats.
- **Tasks**:
  - [ ] **Technical**: Export API docs and setup guides into structured PDFs.
  - [ ] **Non-Technical**: Clean historical texts or research papers (remove ads, complex headers, and sidebars).
  - [ ] **Formatting**: Ensure headings are clear (H1, H2) to help the `RecursiveCharacterTextSplitter` chunk logic.

## Phase 3: Folder-to-Project Mapping

**Goal**: Automate the ingestion pipeline.

- **Action**: Use the `/api/v1/data/process-and-push/{project_id}` endpoint for batch processing.
- **Tasks**:
  - [ ] Organize local documents into a project-based structure:
    ```text
    /assets/{project_id}/
       ├── tech/        # Setup, Architecture
       ├── domain/      # Historical data, Research
       └── ops/         # Milestones, Team rules
    ```
  - [ ] Create a small script (using `httpx`) to iterate through these folders and call the `process-and-push` endpoint for each.

## Phase 4: Metadata & Semantic Tagging

**Goal**: Improve retrieval precision.

- **Action**: Use the `chunk_metadata` field in your database.
- **Tasks**:
  - [ ] Add tags during ingestion: `domain`, `difficulty_level`, `last_updated`.
  - [ ] Implement a system to prioritize "Pinned" or "Verified" documents over experimental ones in the search results.

## Phase 5: Evaluation & Feedback Loop

**Goal**: Continuous improvement of the "Brain."

- **Action**: Use the **RAGAS** or **TruLens** framework (from your roadmap).
- **Tasks**:
  - [ ] Run the "Lebanon River" or "GitHub Commit" questions against the indexed data.
  - [ ] If the agent fails, identify if the failure is:
    - **Retrieval Failure**: Document is missing or chunk is too small.
    - **Generation Failure**: LLM is not following the context.
  - [ ] Update the knowledge base documents to explicitly address the failed queries.

---

## Success Criteria

1. **Zero Gaps**: The agent no longer says "I don't have enough information" for core project questions.
2. **Context Precision**: The retrieved documents are exactly what is needed to solve a `BLOCKER`.
3. **Multilingual Support**: Knowledge base contains both English and Arabic versions of key documents.
