# Walkthrough - Split API URL Configuration

I have updated the application to support using a local Ollama instance for embeddings while keeping the remote Colab/ngrok instance for text generation.

## Changes Made

### 1. Configuration Layer
- **config.py**: Added `OPENAI_GENERATION_API_URL` and `OPENAI_EMBEDDING_API_URL` to support multiple endpoints. I also fixed a type validation issue by allowing `None` values for optional settings.
- **.env**: Updated with the following configuration:
  - `OPENAI_GENERATION_API_URL`: Points to your Colab ngrok link.
  - `OPENAI_EMBEDDING_API_URL`: Points to `http://localhost:11434/v1` for your local Ollama.

### 2. Provider Factory
- **LLMProviderFactory.py**: Modified the `create` method to accept a specific `api_url`, allowing different instances of the OpenAI provider to point to different servers.

### 3. Application Startup
- **main.py**: Updated the startup logic to pass the separate generation and embedding URLs to the factory.

## Verification Results

- Started the application using `uvicorn`.
- Successfully validated that the application initializes both the generation and embedding clients with their respective URLs.
- The server is now running on `http://0.0.0.0:8001`.

> [!TIP]
> To ensure everything works, make sure your local Ollama is running and you have pulled the model by running:
> `ollama pull nomic-embed-text`
