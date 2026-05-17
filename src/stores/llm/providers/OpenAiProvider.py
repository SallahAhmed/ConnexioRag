from .BaseProvider import BaseProvider
from stores.llm.LLMEnums import OpenAIEnums, DocumentTypeEnum
from typing import Union, List
import logging

class OpenAIProvider(BaseProvider):

    def __init__(self, api_key, api_url, default_input_max_characters=1000,
                 default_generation_max_output_tokens=None,
                 default_generation_temperature=0.1,
                 generation_model_id=None,
                 embedding_model_id=None,
                 embedding_size=None):
        super().__init__(api_key, api_url, default_input_max_characters,
                         default_generation_max_output_tokens,
                         default_generation_temperature)

        self.logger = logging.getLogger(__name__)

        self.generation_model_id = generation_model_id
        self.embedding_model_id = embedding_model_id
        self.embedding_size = embedding_size

        self.client = self.create_client()

        self.enums = OpenAIEnums

    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def process_text(self, text):
        return text[:self.default_input_max_characters].strip()

    def create_client(self):

        from openai import AsyncOpenAI

        if self.api_key and self.api_url:
            return AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_url,
            )

        if self.api_key and not self.api_url:
            return AsyncOpenAI(
                api_key=self.api_key,
            )

        if not self.api_key and self.api_url:
            return AsyncOpenAI(
                api_key="sk-no-key-required",
                base_url=self.api_url,
            )

        return None

    async def generate_text(self, prompt: str, chat_history: list=[], max_output_tokens: int=None,
                             temperature: float = None):

        if not self.client:
            self.logger.error("OpenAI client was not set")
            return ""

        if not self.generation_model_id:
            self.logger.error("Generation model for OpenAI was not set")
            return ""

        max_output_tokens = max_output_tokens if max_output_tokens else self.default_generation_max_output_tokens
        temperature = temperature if temperature else self.default_generation_temperature

        # Create localized copy of history to avoid side-effects in async contexts
        local_history = list(chat_history)
        local_history.append(
            self.construct_prompt(prompt=prompt, role=OpenAIEnums.USER.value)
        )

        try:
            response = await self.client.chat.completions.create(
                model = self.generation_model_id,
                messages = local_history,
                max_tokens = max_output_tokens,
                temperature = temperature
            )

            if response and response.usage:
                self.last_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
                print(f"[LLM USAGE] {self.generation_model_id} -> Prompt: {response.usage.prompt_tokens} | Completion: {response.usage.completion_tokens} | Total: {response.usage.total_tokens}")
            else:
                self.last_usage = None

            if not response or not response.choices:
                print("DEBUG: Ollama returned an empty response object!")
                return ""

            answer = response.choices[0].message.content
            return answer if answer else ""

        except Exception as e:
            self.logger.error("OpenAIProvider Error: %s", str(e))
            return ""

    async def generate_text_stream(self, prompt: str, chat_history: list=[], max_output_tokens: int=None,
                             temperature: float = None):

        if not self.client:
            self.logger.error("OpenAI client was not set")
            yield ""
            return

        if not self.generation_model_id:
            self.logger.error("Generation model for OpenAI was not set")
            yield ""
            return

        max_output_tokens = max_output_tokens if max_output_tokens else self.default_generation_max_output_tokens
        temperature = temperature if temperature else self.default_generation_temperature

        # Create localized copy of history to avoid side-effects in async contexts
        local_history = list(chat_history)
        local_history.append(
            self.construct_prompt(prompt=prompt, role=OpenAIEnums.USER.value)
        )

        try:
            response = await self.client.chat.completions.create(
                model = self.generation_model_id,
                messages = local_history,
                max_tokens = max_output_tokens,
                temperature = temperature,
                stream=True
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            self.logger.error("OpenAIProvider Streaming Error: %s", str(e))
            yield ""

    async def embed_text(self, text: Union[str, List[str]], document_type: str = None):

        if not self.client:
            self.logger.error("OpenAI client was not set")
            return None

        if isinstance(text, str):
            text = [text]

        text = [self.process_text(t) for t in text]

        # Handle Nomic specific prefixes if document_type is provided
        if self.embedding_model_id and "nomic-embed-text" in self.embedding_model_id:
            if document_type == "query":
                text = [f"search_query: {t}" for t in text]
            elif document_type == "document":
                text = [f"search_document: {t}" for t in text]

        if not self.embedding_model_id:
            self.logger.error("Embedding model for OpenAI was not set")
            return None

        response = await self.client.embeddings.create(
            model = self.embedding_model_id,
            input = text,
        )

        if not response or not response.data or len(response.data) == 0 or not response.data[0].embedding:
            self.logger.error("Error while embedding text with OpenAI")
            return None

        return [ rec.embedding for rec in response.data ]

    def construct_prompt(self, prompt: str, role: str):
        return {
            "role": role,
            "content": prompt,
        }
