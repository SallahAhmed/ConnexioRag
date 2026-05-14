# Connexio Agentic RAG: Advanced Memory & Advisor Behavior Implementation Plan

## 1. Overview

This document outlines the blueprint for adding **Long-Term Semantic Memory (PGVector)**, **Ambiguity Handling**, and **Advisor Persona Enforcement** to the Connexio AI ecosystem.

This plan is written to be easily understood by future developers. It balances advanced RAG capabilities with our current API token economics.

### 1.1 Token Economics Context

- **Generation Model:** Groq/OpenRouter fallback (100k - 200k tokens/day).
- **Utility Model:** `llama-3.1-8b` via Groq (500k tokens/day).
- **Embedding Model:** `bge-m3` running locally (Zero token cost).

Since Embedding is free and Utility tokens are abundant, we can build a highly robust background extraction pipeline without exhausting the primary generation quota.

---

## 2. Component 1: Prompt Improvements (Ambiguity & Persona)

### The Problem

Large Language Models have a "people-pleaser" syndrome. If a user asks an ambiguous question, the model tries to guess or hallucinate instead of stopping to ask for missing context.

### The Solution

We will update the system prompts to strictly enforce an "Advisor" persona that asks clarifying questions.

### Where to Implement

- **Files:**
  - `src/stores/llm/templates/locales/en/rag.py`
  - `src/stores/llm/templates/locales/ar/rag.py`
- **Changes Required:** Add the following directives to the `system_prompt`:
  > _"If the user's request is ambiguous, lacks necessary project details, or if the retrieved context is insufficient, do NOT guess. Instead, ask the user specific, clarifying questions to get the right information."_
  > _"You have access to the user's Past Extracted Memories. Use them to personalize your answers. If past memories conflict, always trust the most recent memory."_

---

## 3. Component 2: Memory Extraction Pipeline (The "Brain")

### The Problem

We cannot save raw chat history (e.g., "Hello", "Thanks") into PGVector, as it pollutes the semantic search space with noise.

### The Solution

We will use the **Utility Model** (500k quota) to act as a "Memory Manager." It will quietly read the user's message in the background and extract only hard facts, technical stack choices, or user preferences.

### Where to Implement

- **File:** `src/controllers/WorkflowController.py`
- **Changes Required:** Create a new async method `extract_memory_fact(query: str, language: str) -> str`.
- **Extraction Prompt Strategy:**
  > _"Analyze this user query: '{query}'. Does it contain a core project fact, a technical choice (like 'we use React'), or a user preference? If YES, extract it as a single concise sentence. If NO, return 'NONE'. IMPORTANT: Always translate the extracted fact to English to maintain a unified bilingual vector space."_

---

## 4. Component 3: Asynchronous Execution (Zero Latency Penalty)

### The Problem

If we run the Utility Model extraction _during_ the chat cycle, the user has to wait an extra 1-2 seconds for their response.

### The Solution

We will offload the memory extraction and embedding to a background task using `asyncio.create_task()`.

### Where to Implement

- **File:** `src/controllers/NLPController.py` (Inside `answer_agent_chat` and `answer_agent_chat_stream`).
- **Changes Required:**
  ```python
  # After generating the final answer and before returning the response:
  asyncio.create_task(
      self._background_memory_extraction(project_id, user_id, query)
  )
  ```
- **Inside `_background_memory_extraction`:**
  1. Call `WorkflowController.extract_memory_fact()`.
  2. If a fact is returned (not "NONE"), use `embedding_client.embed_text()`.
  3. Save to PGVector.

---

## 5. Component 4: PGVector Storage & Injection

### The Problem

We need a dedicated space for these memories, separate from the main project document chunks.

### The Solution

We will create a specialized PGVector collection for long-term memory.

### Where to Implement

- **Storage (`src/controllers/NLPController.py`):**
  - Create a new collection naming convention: `user_memory_{embedding_size}_{user_id}`.
  - Insert the embedded extracted facts here.
- **Injection (`src/controllers/NLPController.py` -> `_prepare_chat_context`):**
  - Before generating the prompt, search the `user_memory` collection using the current query.
  - **CRITICAL SAFEGUARDS:**
    - Set `limit=2` to prevent Context Budget Clutter (since our budget is reduced to 12,000 chars).
    - Sort results by `created_at DESC` to solve the "Memory Conflict" problem (newest facts take priority).
  - Inject these facts into the `footer_prompt` under a new heading: `[Past Personal Memories]`.

---

## 6. Summary Checklist for Future Developers

If you are picking up this task, follow this order:

1. [ ] Update `en/rag.py` and `ar/rag.py` system prompts to handle ambiguity and recognize memories.
2. [ ] Add `extract_memory_fact` to `WorkflowController.py` using `self.utility_client`.
3. [ ] Create `_background_memory_extraction` in `NLPController.py` to embed and store facts without blocking the user response.
4. [ ] Update `_prepare_chat_context` in `NLPController.py` to search `user_memory` (limit=2) and inject results into the chat history/context.
