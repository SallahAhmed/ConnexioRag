# Fix RAG Retrieval Inaccuracy

The RAG application is currently experiencing inaccuracies due to poor document chunking, retrieval mismatch, and prompt hallucinations. This plan addresses the end-to-end flow to improve retrieval and response generation.

## User Review Required

> [!IMPORTANT]
> Please review this plan before I proceed. The plan includes swapping out the custom naive chunking implementation with an industry standard LangChain text splitter.

## Proposed Changes

---

### Data Processing (Chunking)

Currently, `ProcessController.py` uses a custom `process_simpler_splitter` that simply splits by `\n` and aggregates chunks by absolute character limit without applying the overlap size, breaking sentences mid-way or disconnecting related context.

#### [MODIFY] ProcessController.py
- Import and use `RecursiveCharacterTextSplitter` from LangChain instead of the custom `process_simpler_splitter`.
- Allow the chunker to properly consume `chunk_size` and `overlap_size`.
- Set sensible defaults if none are provided (e.g., chunk size 1000, overlap 200).

---

### Prompts

Update the English and Arabic system/footer prompts to instruct the generation model to strictly avoid hallucinating (adding "say 'I don't know' if the context doesn't contain the answer") and to cite the provided document ID/number for its sources.

#### [MODIFY] rag.py (English)
#### [MODIFY] rag.py (Arabic)
- Update system prompt instructions to ground answers locally.
- Instruct model to cite its sources (`[Document No]`).

## Open Questions

- We currently retrieve the top 10 documents by default for any query using Cosine similarity over `nomic-embed-text`. Would you like me to incorporate a Cross-Encoder Re-ranker (e.g., using `sentence-transformers`) to narrow the 10 results down to the best 3-5, or should we stick to just top-k vector search with the improved chunking?

## Verification Plan

### Automated/Manual Verification
- Upload a test PDF document using the `/api/v1/data/upload/{project_id}` and `/api/v1/data/process/{project_id}` APIs.
- Examine the chunks generated in the PostgreSQL Vector DB.
- Run a Q&A query to verify the answer includes citations and uses contextual facts rather than hallucinating.
