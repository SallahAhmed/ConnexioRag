from .OpenAIProvider import OpenAIProvider

class GroqProvider(OpenAIProvider):
    def __init__(self, api_key: str, api_url: str = "https://api.groq.com/openai/v1",
                 default_input_max_characters: int = 1000,
                 default_generation_max_output_tokens: int = 1000,
                 default_generation_temperature: float = 0.1):
        
        super().__init__(api_key=api_key, api_url=api_url,
                         default_input_max_characters=default_input_max_characters,
                         default_generation_max_output_tokens=default_generation_max_output_tokens,
                         default_generation_temperature=default_generation_temperature)
