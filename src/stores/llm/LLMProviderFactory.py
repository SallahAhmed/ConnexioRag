from .LLMEnums import LLMEnums
from .providers import OpenAIProvider, CoHereProvider, GroqProvider

class LLMProviderFactory:
    def __init__(self, config: dict):
        self.config = config

    def create(self, provider: str, api_url: str = None):
        if provider == LLMEnums.OPENAI.value:
            return OpenAIProvider(
                api_key = self.config.OPENAI_API_KEY,
                api_url = api_url if api_url else self.config.OPENAI_API_URL,
                default_input_max_characters=self.config.INPUT_DEFAULT_MAX_CHARACTERS,
                default_generation_max_output_tokens=self.config.GENERATION_DEFAULT_MAX_TOKENS,
                default_generation_temperature=self.config.GENERATION_DEFAULT_TEMPERATURE
            )

        if provider == LLMEnums.COHERE.value:
            return CoHereProvider(
                api_key = self.config.COHERE_API_KEY,
                default_input_max_characters=self.config.INPUT_DEFAULT_MAX_CHARACTERS,
                default_generation_max_output_tokens=self.config.GENERATION_DEFAULT_MAX_TOKENS,
                default_generation_temperature=self.config.GENERATION_DEFAULT_TEMPERATURE
            )

        if provider == LLMEnums.GROQ.value:
            return GroqProvider(
                api_key = self.config.GROQ_API_KEY,
                api_url = api_url if api_url else self.config.GROQ_API_URL,
                default_input_max_characters=self.config.INPUT_DEFAULT_MAX_CHARACTERS,
                default_generation_max_output_tokens=self.config.GENERATION_DEFAULT_MAX_TOKENS,
                default_generation_temperature=self.config.GENERATION_DEFAULT_TEMPERATURE
            )

        return None

    def create_generation_client(self):
        backend = self.config.GENERATION_BACKEND
        api_url = self.config.GROQ_API_URL if backend == LLMEnums.GROQ.value else self.config.OPENAI_GENERATION_API_URL
        client = self.create(backend, api_url)
        if client:
            client.set_generation_model(model_id=self.config.GENERATION_MODEL_ID)
        return client

    def create_utility_client(self):
        backend = getattr(self.config, 'UTILITY_BACKEND', None) or self.config.GENERATION_BACKEND
        api_url = self.config.GROQ_API_URL if backend == LLMEnums.GROQ.value else self.config.OPENAI_GENERATION_API_URL
        client = self.create(backend, api_url)
        if client:
            client.set_generation_model(model_id=self.config.UTILITY_MODEL_ID)
        return client