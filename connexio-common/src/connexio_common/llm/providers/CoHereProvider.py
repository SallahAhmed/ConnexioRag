"""Cohere provider for generation and embeddings."""

import logging
from typing import List, Optional, Union

import cohere

from .. import CoHereRoles, DocumentType, LLMInterface


class CoHereProvider(LLMInterface):
    def __init__(
        self,
        api_key: str,
        default_input_max_characters: int = 1000,
        default_generation_max_output_tokens: int = 1024,
        default_generation_temperature: float = 0.1,
    ):
        self.api_key = api_key
        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature
        self.generation_model_id: Optional[str] = None
        self.embedding_model_id: Optional[str] = None
        self.embedding_size: Optional[int] = None
        self.client = cohere.AsyncClient(api_key=self.api_key)
        self.logger = logging.getLogger(__name__)

    def set_generation_model(self, model_id: str) -> None:
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id: str, embedding_size: int) -> None:
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    async def generate_text(
        self,
        prompt: str,
        chat_history: Optional[list] = None,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Optional[str]:
        if chat_history is None:
            chat_history = []

        if not self.client:
            self.logger.error("Cohere client was not set")
            return None

        if not self.generation_model_id:
            self.logger.error("Generation model for Cohere was not set")
            return None

        max_output_tokens = max_output_tokens or self.default_generation_max_output_tokens
        temperature = temperature or self.default_generation_temperature

        response = await self.client.chat(
            model=self.generation_model_id,
            chat_history=chat_history,
            message=self.process_text(prompt, self.default_input_max_characters),
            temperature=temperature,
            max_tokens=max_output_tokens,
        )

        if not response or not response.text:
            self.logger.error("Error while generating text with Cohere")
            return None

        return response.text

    async def generate_text_stream(
        self,
        prompt: str,
        chat_history: Optional[list] = None,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        if chat_history is None:
            chat_history = []

        if not self.client:
            self.logger.error("Cohere client was not set")
            return
        if not self.generation_model_id:
            self.logger.error("Generation model for Cohere was not set")
            return

        max_output_tokens = max_output_tokens or self.default_generation_max_output_tokens
        temperature = temperature or self.default_generation_temperature

        stream = await self.client.chat_stream(
            model=self.generation_model_id,
            chat_history=chat_history,
            message=self.process_text(prompt, self.default_input_max_characters),
            temperature=temperature,
            max_tokens=max_output_tokens,
        )

        async for event in stream:
            if event.event_type == "text-generation":
                yield event.text

    async def embed_text(
        self,
        text: Union[str, List[str]],
        document_type: Optional[str] = None,
    ) -> Optional[List[List[float]]]:
        if not self.client:
            self.logger.error("Cohere client was not set")
            return None

        if isinstance(text, str):
            text = [text]

        if not self.embedding_model_id:
            self.logger.error("Embedding model for Cohere was not set")
            return None

        input_type = CoHereRoles.DOCUMENT.value
        if document_type == DocumentType.QUERY.value:
            input_type = CoHereRoles.QUERY.value

        response = await self.client.embed(
            model=self.embedding_model_id,
            texts=[self.process_text(t, self.default_input_max_characters) for t in text],
            input_type=input_type,
            embedding_types=["float"],
        )

        if not response or not response.embeddings or not response.embeddings.float:
            self.logger.error("Error while embedding text with Cohere")
            return None

        return [f for f in response.embeddings.float]

    def construct_prompt(self, prompt: str, role: str) -> dict:
        return {"role": role, "text": prompt}

    def with_structured_output(self, schema):
        return self
