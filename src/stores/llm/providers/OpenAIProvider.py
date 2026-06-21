from ..LLMInterface import LLMInterface
from ..LLMEnums import OpenAIEnums
# pyrefly: ignore [missing-import]
from openai import AsyncOpenAI
import logging
import asyncio
import re
from typing import List, Union, Optional

class OpenAIProvider(LLMInterface):

    def __init__(self, api_key: str, api_url: str=None,
                       default_input_max_characters: int=1000,
                       default_generation_max_output_tokens: int=1000,
                       default_generation_temperature: float=0.1):
        
        self.api_key = api_key
        self.api_url = api_url

        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None

        self.embedding_model_id = None
        self.embedding_size = None

        self.client = AsyncOpenAI(
            api_key = self.api_key,
            base_url = self.api_url if self.api_url and len(self.api_url) else None,
            timeout = 180.0 # 3 minute timeout for local CPU generation
        )

        self.enums = OpenAIEnums
        self.logger = logging.getLogger(__name__)
        self.last_usage = None

    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def process_text(self, text: str):
        return text[:self.default_input_max_characters].strip()

    async def generate_text(self, prompt: str, chat_history: list=[], max_output_tokens: int=None,
                             temperature: float = None):
        
        if not self.client:
            self.logger.error("OpenAI client was not set")
            return None

        if not self.generation_model_id:
            self.logger.error("Generation model for OpenAI was not set")
            return None
        
        max_output_tokens = max_output_tokens if max_output_tokens else self.default_generation_max_output_tokens
        temperature = temperature if temperature else self.default_generation_temperature

        # Create localized copy of history to avoid side-effects in async contexts
        local_history = list(chat_history)
        local_history.append(
            self.construct_prompt(prompt=prompt, role=OpenAIEnums.USER.value)
        )

        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
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
                error_str = str(e).lower()
                is_rate_limit = "429" in error_str or "rate" in error_str or "too many" in error_str

                if is_rate_limit and attempt < max_retries - 1:
                    retry_after = self._parse_retry_after(e)
                    wait = retry_after if retry_after else retry_delay
                    self.logger.warning(f"Generation rate-limited (attempt {attempt + 1}/{max_retries}), retrying in {wait:.1f}s")
                    await asyncio.sleep(wait)
                    retry_delay = min(retry_delay * 2, 30.0)
                else:
                    print(f"DEBUG: OpenAIProvider Error: {str(e)}")
                    return f"Error during generation: {str(e)}"

    @staticmethod
    def _parse_retry_after(error: Exception) -> Optional[float]:
        """Try to extract Retry-After seconds from an HTTP error response."""
        err_str = str(error)
        match = re.search(r"[Rr]etry-?[Aa]fter[:\s]+(\d+)", err_str)
        if match:
            return float(match.group(1))
        match = re.search(r"(?:try|wait|retry)\s+(?:again\s+)?(?:in\s+)?(\d+(?:\.\d+)?)\s*s", err_str, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None
        
    async def generate_text_stream(self, prompt: str, chat_history: list=[], max_output_tokens: int=None,
                             temperature: float = None):
        
        if not self.client:
            self.logger.error("OpenAI client was not set")
            yield None
            return

        if not self.generation_model_id:
            self.logger.error("Generation model for OpenAI was not set")
            yield None
            return
        
        max_output_tokens = max_output_tokens if max_output_tokens else self.default_generation_max_output_tokens
        temperature = temperature if temperature else self.default_generation_temperature

        # Create localized copy of history to avoid side-effects in async contexts
        local_history = list(chat_history)
        local_history.append(
            self.construct_prompt(prompt=prompt, role=OpenAIEnums.USER.value)
        )

        print(f"[LLM STREAM] {self.generation_model_id} -> streaming generation started")
        self.last_usage = None

        try:
            create_kwargs = dict(
                model = self.generation_model_id,
                messages = local_history,
                max_tokens = max_output_tokens,
                temperature = temperature,
                stream = True,
            )
            # include_usage makes the provider emit a final usage-only chunk so we can log
            # token counts like the non-streaming path. Not every OpenAI-compatible endpoint
            # supports it, so fall back cleanly rather than breaking generation.
            try:
                response = await self.client.chat.completions.create(
                    **create_kwargs, stream_options={"include_usage": True}
                )
            except Exception as opt_err:
                self.logger.warning(f"stream_options unsupported, retrying without usage: {opt_err}")
                response = await self.client.chat.completions.create(**create_kwargs)

            async for chunk in response:
                # The usage-only final chunk carries usage and has empty choices.
                if getattr(chunk, "usage", None):
                    self.last_usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }
                    print(f"[LLM USAGE] {self.generation_model_id} -> Prompt: {chunk.usage.prompt_tokens} | Completion: {chunk.usage.completion_tokens} | Total: {chunk.usage.total_tokens}")
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"DEBUG: OpenAIProvider Streaming Error: {str(e)}")
            yield f"Error: {str(e)}"

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

        extra_body = {}
        if self.embedding_model_id and "jina" in self.embedding_model_id.lower():
            if document_type == "query":
                extra_body["task"] = "retrieval.query"
            elif document_type == "document":
                extra_body["task"] = "retrieval.passage"

        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = await self.client.embeddings.create(
                    model = self.embedding_model_id,
                    input = text,
                    extra_body = extra_body or None,
                )

                if not response or not response.data or len(response.data) == 0 or not response.data[0].embedding:
                    self.logger.error("Error while embedding text with OpenAI")
                    return None

                return [ rec.embedding for rec in response.data ]

            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = "429" in error_str or "rate" in error_str or "too many" in error_str

                if is_rate_limit and attempt < max_retries - 1:
                    retry_after = self._parse_retry_after(e)
                    wait = retry_after if retry_after else retry_delay
                    self.logger.warning(f"Embedding rate-limited (attempt {attempt + 1}/{max_retries}), retrying in {wait:.1f}s")
                    await asyncio.sleep(wait)
                    retry_delay = min(retry_delay * 2, 30.0)
                else:
                    self.logger.error(f"Error while embedding text: {str(e)}")
                    return None

        return None

    def construct_prompt(self, prompt: str, role: str):
        return {
            "role": role,
            "content": prompt,
        }
