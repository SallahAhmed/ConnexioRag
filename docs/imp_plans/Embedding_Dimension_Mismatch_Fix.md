# Fix Embedding Dimension Mismatch

The `nomic-embed-text` model returns vectors with **768 dimensions**, but the application is configured for **384 dimensions**. This causes a `ValueError` during search operations. We need to update the configuration and reset the vector database.

## User Review Required

> [!WARNING]
> We will update `EMBEDDING_MODEL_SIZE` to `768` in your `.env` file.
> Because the vector database collection was created with the wrong dimension (384), **you will need to re-index your documents**. The easiest way is to delete the current database folder.

## Proposed Changes

### Configuration Update

#### [MODIFY] .env
Update `EMBEDDING_MODEL_SIZE` to `768`.

### System Cleanup
- Delete the local Qdrant storage folder (`src/assets/vector_db/qdrant_db`) so the application can recreate it with the correct 768-dimension schema.

## Open Questions

1. Do you have important data in the vector database that you cannot re-index? (Usually not an issue in dev).

## Verification Plan

### Manual Verification
- Restart the application.
- Upload/Index a new document.
- Perform a search.
- Verify that the `ValueError` no longer occurs.
