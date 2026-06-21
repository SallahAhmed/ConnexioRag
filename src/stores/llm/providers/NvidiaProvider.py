from .OpenAIProvider import OpenAIProvider

class NvidiaProvider(OpenAIProvider):
    """NVIDIA NIM (build.nvidia.com) — OpenAI-compatible endpoint.

    Identical wire protocol to OpenAI/Groq, only the base URL and key differ.
    Kept as a dedicated backend so it never collides with the Jina key the
    OPENAI backend uses for embeddings (see LLMProviderFactory.create).
    """
    def __init__(self, api_key: str, api_url: str = "https://integrate.api.nvidia.com/v1",
                 default_input_max_characters: int = 1000,
                 default_generation_max_output_tokens: int = 1000,
                 default_generation_temperature: float = 0.1):

        super().__init__(api_key=api_key, api_url=api_url,
                         default_input_max_characters=default_input_max_characters,
                         default_generation_max_output_tokens=default_generation_max_output_tokens,
                         default_generation_temperature=default_generation_temperature)
