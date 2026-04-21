# Switch Generative LLM to Local Ollama Model

This plan outlines the steps required to switch the application's text generation and embedding models to your local models managed by Ollama (`qwen:4b` and `nomic-embed-text:latest`), without deleting any of the existing remote providers (Cohere, OpenAI) so that you can easily switch back in the future.

## Proposed Changes

Because the application is already designed to allow setting an `API_URL` for the `OPENAI` backend provider, we can leverage Ollama's native OpenAI-compatible API without needing to write a new provider class.

We will strictly modify the `src/.env` configuration file to point the "OPENAI" generative backend to your local Ollama server, just like what is currently done for your embedding backend.

### Configuration Updates

#### [MODIFY] .env
We will update the following variables in the `.env` file:

- **`OPENAI_GENERATION_API_URL`**: Change from the remote ngrok tunnel to Ollama's local URL `http://localhost:11434/v1`.
- **`GENERATION_MODEL_ID`**: Change from `"gemma4:e4b"` to `"qwen:4b"`.
- We will leave `GENERATION_BACKEND`, `EMBEDDING_BACKEND`, `OPENAI_API_KEY` and `COHERE_API_KEY` exactly as they are so you don't lose that configuration.
- We will leave `EMBEDDING_MODEL_ID` as `"nomic-embed-text:latest"` and `OPENAI_EMBEDDING_API_URL` as `"http://localhost:11434/v1"`, since they are already properly configured for Ollama in your `.env`.

## User Review Required

> [!IMPORTANT]
> Please review the `.env` changes described above. No Python code changes are required since the `OpenAIProvider` handles customized base URLs natively. Once you grant permission, I will proceed to implement these changes.
