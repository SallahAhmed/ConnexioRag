# RAG Tool Prioritization Overhaul — Implementation Plan

**Date:** 2026-05-17
**Status:** Approved — implementation in progress

---

## Problem Summary

The current RAG pipeline has 8 interconnected issues:

| # | Issue | Impact |
|---|-------|--------|
| 1 | **Binary KB decision** — if grader says IRRELEVANT, entire KB is discarded | Loses useful partial context |
| 2 | **Single-tool CRAG** — LLM picks ONE tool only | Complex queries get incomplete answers |
| 3 | **Duplicate CRAG logic** — 100+ lines repeated twice (no-project + project paths) | Bug surface doubled, hard to maintain |
| 4 | **Platform node canned responses** — ONBOARDING/TEAM_FORMATION/PHASE_TRANSITION with empty KB get hardcoded "I don't have docs" | Wasted opportunity to use external tools |
| 5 | **Dead `is_technical` code** — hardcoded `True`, entire else-branch unreachable | Confusing, misleading code |
| 6 | **Grader too aggressive** — "strict and highly critical" pushes toward IRRELEVANT too easily | Premature KB discard |
| 7 | **Language override from URL content** — when a URL is pasted in an English query pointing to an Arabic page, the `language` variable is overwritten from URL content, causing Arabic system prompts for an English-speaking user | English query → Arabic answer |
| 8 | **Unconfigured tools silently inject error strings** — LLM may select GOOGLE/STACKOVERFLOW/GITHUB even when their API keys are missing; error strings like "not configured" end up in the RAG context as if they were real knowledge | Garbage context, confusing answers |

---

## Design Decisions (Confirmed)

| Decision | Value | Reason |
|----------|-------|--------|
| Multi-tool cap | **2 tools max** per query | Balance completeness vs latency |
| Temporal queries | **Google forced** — skip KB entirely | Fresh data needed, KB is stale |
| Grading approach | **Batch LLM** — one call grades all docs | Same latency as current single-blob, per-doc accuracy, no model-specific score thresholds |
| Language detection | **Query language only** — URL content language never overrides response language | User language follows their message, not a pasted document |

---

## Files Changed

| File | Change Type | Details |
|------|-------------|---------|
| `src/controllers/WorkflowController.py` | Add method + fix | Add `grade_relevance_batch()`; fix client mismatch in `grade_relevance()` |
| `src/controllers/helpers/ToolManager.py` | Add method | Add `search_knowledge_base_raw()` |
| `src/stores/llm/templates/locales/en/relevance_grading.py` | Modify prompts | Soften relevance grader |
| `src/stores/llm/templates/locales/ar/relevance_grading.py` | Modify prompts | Soften relevance grader |
| `src/controllers/NLPController.py` | Major rewrite | Fix language bug; add `_run_crag_tools()`; rewrite KB decision block; remove dead code |

---

## Step 1: Add `search_knowledge_base_raw()` to ToolManager

**File:** `src/controllers/helpers/ToolManager.py`

**Why:** The existing `search_knowledge_base()` returns a single formatted string. Batch grading needs individual doc objects.

**New method:**

```python
async def search_knowledge_base_raw(self, project_id, query: str, limit: int = 5):
    """Same retrieval as search_knowledge_base but returns list of raw doc objects.
    Enables batch relevance grading. Returns [] on failure."""
    try:
        vectors = await self.embedding_client.embed_text(text=query, document_type="query")
        if not vectors or len(vectors) == 0:
            return []

        query_vector = vectors[0]
        k = 60
        scores = {}
        doc_map = {}

        def add_results(results, prefix=""):
            if not results:
                return
            for rank, doc in enumerate(results):
                doc_id = prefix + doc.text
                doc_map[doc_id] = doc
                scores[doc_id] = scores.get(doc_id, 0) + (1.0 / (k + rank + 1))

        project_collection = self._get_collection_name(project_id)
        try:
            project_results = await self.vectordb_client.hybrid_search(
                collection_name=project_collection, query=query, vector=query_vector, limit=limit * 2,
            )
        except Exception:
            project_results = await self.vectordb_client.search_by_vector(
                collection_name=project_collection, vector=query_vector, limit=limit * 2,
            )
        add_results(project_results, "proj_")

        try:
            global_results = await self.vectordb_client.hybrid_search(
                collection_name=self.get_global_collection_name(), query=query, vector=query_vector, limit=limit * 2,
            )
        except Exception:
            global_results = await self.vectordb_client.search_by_vector(
                collection_name=self.get_global_collection_name(), vector=query_vector, limit=limit * 2,
            )
        add_results(global_results, "global_")

        if not scores:
            return []

        sorted_doc_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:limit]

        if self.reranker and sorted_doc_ids:
            docs_to_rerank = [doc_map[did] for did in sorted_doc_ids]
            reranked = await self.reranker.rerank(query=query, documents=docs_to_rerank, top_k=limit)
            return reranked
        else:
            return [doc_map[did] for did in sorted_doc_ids]

    except Exception as e:
        self.logger.error(f"Knowledge Base Raw Tool Error: {str(e)}")
        return []
```

**Key difference from existing method:** Returns `List[doc]` instead of a formatted string. Returns `[]` on empty/failure — no "No relevant documents found" string.

---

## Step 2: Add `grade_relevance_batch()` to WorkflowController + Fix Client Mismatch

**File:** `src/controllers/WorkflowController.py`

### 2a. Add `grade_relevance_batch()`

**Why:** The plan originally called for per-document grading, which would require N sequential LLM calls (5x+ latency increase). Batch grading grades all docs in a single LLM call — same latency as current single-blob grading but with per-doc accuracy.

**Critical note:** The existing `grade_relevance()` returns `bool` (True for both RELEVANT and AMBIGUOUS, False for IRRELEVANT). It cannot be used for the decision matrix. `grade_relevance_batch()` returns explicit strings.

```python
async def grade_relevance_batch(self, query: str, docs: list) -> list:
    """
    Grade N documents for relevance in a single LLM call.
    Returns a list of "RELEVANT", "AMBIGUOUS", or "IRRELEVANT" strings,
    one per doc in the same order. Falls back to all-RELEVANT on failure.
    """
    if not docs:
        return []

    docs_text = "\n\n".join([
        f"[Doc {i+1}]: {d.text[:800]}"
        for i, d in enumerate(docs)
    ])

    prompt = (
        f'Query: "{query}"\n\n'
        f"Documents to grade:\n{docs_text}\n\n"
        f"Grade each document as RELEVANT, AMBIGUOUS, or IRRELEVANT.\n"
        f"- RELEVANT: directly answers or provides useful domain context\n"
        f"- AMBIGUOUS: same general topic but doesn't directly address the question\n"
        f"- IRRELEVANT: completely unrelated or false-positive keyword match\n\n"
        f"Be generous — domain context is valuable even without a direct answer.\n"
        f"Return ONLY a JSON array with one grade per document in order.\n"
        f'Example for 3 docs: ["RELEVANT", "AMBIGUOUS", "IRRELEVANT"]'
    )

    try:
        import json as _json
        response = await self.utility_client.generate_text(prompt=prompt)
        raw = (response or "").strip().replace("```json", "").replace("```", "")
        grades = _json.loads(raw)
        normalized = []
        for g in grades:
            g_up = str(g).strip().upper()
            if "IRRELEVANT" in g_up:
                normalized.append("IRRELEVANT")
            elif "AMBIGUOUS" in g_up:
                normalized.append("AMBIGUOUS")
            else:
                normalized.append("RELEVANT")
        while len(normalized) < len(docs):
            normalized.append("RELEVANT")
        return normalized[:len(docs)]
    except Exception:
        return ["RELEVANT"] * len(docs)
```

### 2b. Fix `grade_relevance()` client mismatch

**Current bug:** `grade_relevance()` builds `chat_history` with `self.generation_client.construct_prompt()` but calls `self.utility_client.generate_text()`. If providers differ, message format is wrong.

**Fix:** Use `self.utility_client.construct_prompt()` for the system prompt history in `grade_relevance()`.

---

## Step 3: Add `_run_crag_tools()` to NLPController

**File:** `src/controllers/NLPController.py`

**Why:** Extracts the duplicated 100+ line CRAG tool-selection block into a single reusable method. Fixes all 4 issues with the original plan's version.

**Fixes vs original plan:**
- `force_tool` parameter preserves the temporal → Google hardcode (prevents regression)
- Tool list built dynamically — only configured tools (with API keys) are shown to the LLM
- Error strings filtered from results before appending to context
- JSON parse fallback via regex scan if LLM returns non-JSON

```python
async def _run_crag_tools(
    self,
    query: str,
    language: str,
    utility_history: list,
    trace_id: str,
    max_tools: int = 2,
    force_tool: str = None,
) -> list:
    """
    Select and fire up to max_tools external tools for CRAG fallback.
    Returns list of (source_name, result_text) tuples — error responses excluded.
    force_tool bypasses LLM selection (used for temporal queries → GOOGLE).
    """
    ERROR_STRINGS = (
        "not configured", "Unable to perform", "Unable to search",
        "Error fetching", "Error searching", "is not configured",
    )
    tool_results = []

    if force_tool:
        tools = [force_tool]
    else:
        # Build tool list dynamically — only show tools that are actually configured
        available = ["WIKIPEDIA", "ARXIV"]  # always available (no key needed)
        if self.tool_manager.serp_tool:
            available.append("GOOGLE")
        if self.tool_manager.github_token:
            available.append("GITHUB")
        if self.tool_manager.stackoverflow_api_key:
            available.append("STACKOVERFLOW")

        tool_descriptions = {
            "WIKIPEDIA": "General knowledge, history, science, definitions.",
            "ARXIV": "Academic papers, research, ML/AI topics, scientific studies.",
            "GOOGLE": "News, recent events, technical stats, product info.",
            "GITHUB": "Searching repositories, finding open-source files.",
            "STACKOVERFLOW": "Developer questions, coding errors, API usage, debugging.",
        }
        tool_lines = "\n".join(
            [f'- "{t}": {tool_descriptions[t]}' for t in available]
        ) + '\n- "NONE": Conversational or no tool needed.'

        decision_prompt = (
            f'Analyze the user query: "{query}" and select up to {max_tools} tools ranked by priority.\n'
            f"{tool_lines}\n"
            f'Return ONLY JSON: {{"tools": ["TOOL1", "TOOL2"]}} or {{"tools": ["TOOL1"]}}'
        )
        raw = await self.utility_client.generate_text(prompt=decision_prompt)
        raw = (raw or "").strip()
        try:
            parsed = json.loads(raw.replace("```json", "").replace("```", ""))
            tools = [t.strip().upper() for t in parsed.get("tools", []) if t.strip().upper() != "NONE"]
        except Exception:
            # Fallback: scan raw text for known tool names
            tools = []
            for t in ["STACKOVERFLOW", "ARXIV", "GITHUB", "WIKIPEDIA", "GOOGLE"]:
                if t in raw.upper():
                    tools.append(t)
                    break
        tools = tools[:max_tools]

    self.logger.info(f"[RAG TOOL CHOICE] Query: '{query[:50]}' -> Tools: {tools}")

    for choice in tools:
        try:
            if choice == "GITHUB":
                step_id = tracer.start_trace(trace_id, "GitHub Tool Search")
                refine = (
                    f"Extract the GitHub repo name (owner/repo) and mode "
                    f"('summary','commits','issues') from: {query}. "
                    'Return ONLY JSON: {"repo": "...", "mode": "..."}'
                )
                gh_raw = await self.utility_client.generate_text(
                    prompt=refine, chat_history=utility_history
                )
                try:
                    gh_info = json.loads(
                        gh_raw.strip().replace("```json", "").replace("```", "")
                    )
                    repo = gh_info.get("repo", "")
                    result = (
                        await self.tool_manager.fetch_github_data(
                            repo_name=repo, mode=gh_info.get("mode", "summary")
                        )
                        if repo and "/" in repo
                        else "No specific GitHub repository was identified."
                    )
                except Exception:
                    result = "Could not parse GitHub repository from query."
                tracer.end_trace(trace_id, step_id, result[:50], usage=self.utility_client.last_usage)
                if not any(e in result for e in ERROR_STRINGS):
                    tool_results.append(("GitHub", result))

            elif choice == "ARXIV":
                step_id = tracer.start_trace(trace_id, "ArXiv Research Search")
                refine = f"Create a concise academic search query (2-4 keywords) for: {query}. Return ONLY the query."
                refined = (
                    await self.utility_client.generate_text(prompt=refine, chat_history=utility_history) or query
                ).strip().strip('"').strip("'")
                result = await self.tool_manager.search_arxiv(query=refined)
                tracer.end_trace(trace_id, step_id, f"Length: {len(result)}", usage=self.utility_client.last_usage)
                if not any(e in result for e in ERROR_STRINGS):
                    tool_results.append(("ArXiv", result))

            elif choice == "STACKOVERFLOW":
                step_id = tracer.start_trace(trace_id, "StackOverflow Developer Q&A")
                refine = f"Create a concise developer search query (2-5 keywords) for: {query}. Return ONLY the query."
                refined = (
                    await self.utility_client.generate_text(prompt=refine, chat_history=utility_history) or query
                ).strip().strip('"').strip("'")
                result = await self.tool_manager.search_stackoverflow(query=refined)
                tracer.end_trace(trace_id, step_id, f"Length: {len(result)}", usage=self.utility_client.last_usage)
                if not any(e in result for e in ERROR_STRINGS):
                    tool_results.append(("StackOverflow", result))

            elif choice == "GOOGLE":
                step_id = tracer.start_trace(trace_id, "Google Search")
                refine = f"Create a 3-word Google search query for: {query}. Return ONLY the query."
                refined = (
                    await self.utility_client.generate_text(prompt=refine, chat_history=utility_history) or query
                ).strip().strip('"').strip("'")
                result = await self.tool_manager.search_google(query=refined)
                tracer.end_trace(trace_id, step_id, f"Length: {len(result)}", usage=self.utility_client.last_usage)
                if not any(e in result for e in ERROR_STRINGS):
                    tool_results.append(("Google Search", result))

            elif choice == "WIKIPEDIA":
                step_id = tracer.start_trace(trace_id, "Wikipedia Search")
                refine = f"Search Wikipedia for: {query}. Return ONLY the main subject name."
                refined = (
                    await self.utility_client.generate_text(prompt=refine, chat_history=utility_history) or query
                ).strip().strip('"').strip("'")
                result = await self.tool_manager.search_wiki(query=refined, lang=language)
                tracer.end_trace(trace_id, step_id, f"Length: {len(result)}", usage=self.utility_client.last_usage)
                if result and not any(e in result for e in ERROR_STRINGS):
                    tool_results.append(("Wikipedia", result))

        except Exception as e:
            self.logger.warning(f"CRAG tool {choice} failed: {e}")

    return tool_results
```

---

## Step 4: Rewrite `_prepare_chat_context()` KB Decision Block + Language Bug Fix

### Language bug fix

**Root cause:** In the URL parsing block, `language` is overwritten from the downloaded URL content:
```python
# BUGGY — overwrites query language with document language:
language = await self.workflow_controller.detect_language(extracted[:500])
```

**Fix:** Preserve original query language at the start of `_prepare_chat_context()` and never override it from URL content. URL content is context data — the response language always follows the user's query.

```python
# At start of _prepare_chat_context(), after detect_language:
query_language = language  # preserve — never override from URL content

# In URL block, replace the language override with:
# (just remove the two lines — language stays as query_language)
```

### Replacement KB decision block (replaces lines 386-692)

**New flow:**
```
1. Temporal query? → Google forced (1 tool), skip KB
2. OUT_OF_SCOPE? → skip all
3. Memory query? → skip KB (already have history in context)
4. Otherwise:
   a. search_knowledge_base_raw() → list of doc objects
   b. grade_relevance_batch() → ["RELEVANT"/"AMBIGUOUS"/"IRRELEVANT", ...]  (1 LLM call)
   c. Decision matrix:
      All RELEVANT       → KB only
      Mix (R+A+I)        → filtered KB + 1 CRAG tool
      All AMBIGUOUS      → filtered KB + 1 CRAG tool
      All IRRELEVANT     → 2 CRAG tools (KB discarded cleanly via separate kb_context list)
      Empty KB           → 2 CRAG tools
```

**What this changes:**

| Before | After |
|--------|-------|
| Grade entire KB blob (1 LLM call) | Batch-grade all docs (1 LLM call, per-doc results) |
| Binary: use KB OR 1 external tool | Hybrid: KB + tools based on grade distribution |
| Platform nodes get canned response | Platform nodes flow through full pipeline |
| `is_technical = True` dead code | Removed |
| 100+ lines duplicated twice | Single `_run_crag_tools()` call |
| Temporal → skip KB, ask LLM for tool | Temporal → Google forced via `force_tool="GOOGLE"` |
| URL content overrides response language | Query language preserved throughout |
| Unconfigured tools may be selected | Only configured tools in decision prompt |
| Error strings enter context | Error strings filtered before appending |

---

## Step 5: Soften Relevance Grader Prompts

**Files:** `src/stores/llm/templates/locales/en/relevance_grading.py` and `ar/`

Grader is changed from "strict and highly critical" to "generous — domain context is valuable."
See detailed prompt text in Steps 2a (batch grader) and the file edits.

---

## Step 6: Remove Dead Code

- `is_technical = True` / `if is_technical:` block — removed
- Platform node canned response blocks — removed (both copies)
- Duplicate CRAG tool dispatch blocks — replaced by `_run_crag_tools()`

---

## Testing Strategy

| Test Case | Expected Behavior |
|-----------|-------------------|
| "How do I set up Django?" (project KB has Django docs) | All RELEVANT → KB only |
| "What's the latest React 19 features?" (temporal) | Google forced, KB skipped |
| "How does Python handle memory?" (KB empty) | Up to 2 CRAG tools |
| "Who won the World Cup?" | OUT_OF_SCOPE → canned refusal |
| "Where do I start?" (no project, onboarding) | CRAG tools fire (no canned response) |
| "Explain the project architecture" (mixed KB relevance) | Filtered KB + 1 CRAG tool |
| "Can you summarize this? https://arabic-site.com" | English response (query language preserved) |
| "stuck on a null pointer" (BLOCKER node) | KB graded → CRAG if needed |

---

## Rollback Plan

1. Revert the 5 changed files via git
2. No schema changes, no new dependencies, no DB migrations required
