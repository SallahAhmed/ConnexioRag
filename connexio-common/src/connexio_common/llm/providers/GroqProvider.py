"""Groq provider — extends OpenAI-compatible provider with Groq defaults."""

from .OpenAIProvider import OpenAIProvider


class GroqProvider(OpenAIProvider):
    def __init__(
        self,
        api_key: str,
        api_url: str = "https://api.groq.com/openai/v1",
        default_input_max_characters: int = 4000,
        default_generation_max_output_tokens: int = 2000,
        default_generation_temperature: float = 0.2,
        request_timeout: float = 30.0,
        max_retries: int = 1,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_url=api_url,
            default_input_max_characters=default_input_max_characters,
            default_generation_max_output_tokens=default_generation_max_output_tokens,
            default_generation_temperature=default_generation_temperature,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
