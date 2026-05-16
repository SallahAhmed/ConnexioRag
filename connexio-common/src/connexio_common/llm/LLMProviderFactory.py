"""Unified LLM provider factory — creates generation, utility, and embedding clients."""

import logging
from typing import Any

from .. import LLMProvider
from .providers import CoHereProvider, GroqProvider, OpenAIProvider

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    REQUEST_TIMEOUT = 30.0
    MAX_RETRIES = 1

    def __init__(self, config: Any):
        self.config = config

    def create(self, provider: str, api_url: str = None):
        logger.info(f"Creating LLM client for provider: {provider}")

        if provider == LLMProvider.GROQ.value:
            return GroqProvider(
                api_key=self.config.GROQ_API_KEY,
                api_url=api_url or self.config.GROQ_API_URL,
                default_input_max_characters=self.config.INPUT_DEFAULT_MAX_CHARACTERS,
                default_generation_max_output_tokens=self.config.GENERATION_DEFAULT_MAX_TOKENS,
                default_generation_temperature=self.config.GENERATION_DEFAULT_TEMPERATURE,
                request_timeout=self.REQUEST_TIMEOUT,
                max_retries=self.MAX_RETRIES,
            )

        if provider == LLMProvider.OPENAI.value:
            return OpenAIProvider(
                api_key=self.config.OPENAI_API_KEY,
                api_url=api_url or self.config.OPENAI_GENERATION_API_URL,
                default_input_max_characters=self.config.INPUT_DEFAULT_MAX_CHARACTERS,
                default_generation_max_output_tokens=self.config.GENERATION_DEFAULT_MAX_TOKENS,
                default_generation_temperature=self.config.GENERATION_DEFAULT_TEMPERATURE,
                request_timeout=self.REQUEST_TIMEOUT,
                max_retries=self.MAX_RETRIES,
            )

        if provider == LLMProvider.COHERE.value:
            return CoHereProvider(
                api_key=self.config.COHERE_API_KEY,
                default_input_max_characters=self.config.INPUT_DEFAULT_MAX_CHARACTERS,
                default_generation_max_output_tokens=self.config.GENERATION_DEFAULT_MAX_TOKENS,
                default_generation_temperature=self.config.GENERATION_DEFAULT_TEMPERATURE,
            )

        logger.error(f"Unknown LLM provider: {provider}")
        return None

    def create_generation_client(self):
        backend = self.config.GENERATION_BACKEND
        api_url = (
            self.config.GROQ_API_URL
            if backend == LLMProvider.GROQ.value
            else self.config.OPENAI_GENERATION_API_URL
        )
        client = self.create(backend, api_url)
        if client:
            client.set_generation_model(self.config.GENERATION_MODEL_ID)
        return client

    def create_utility_client(self):
        backend = getattr(self.config, "UTILITY_BACKEND", None) or self.config.GENERATION_BACKEND
        api_url = (
            self.config.GROQ_API_URL
            if backend == LLMProvider.GROQ.value
            else self.config.OPENAI_GENERATION_API_URL
        )
        client = self.create(backend, api_url)
        if client:
            client.set_generation_model(self.config.UTILITY_MODEL_ID)
        return client

    def create_embedding_client(self):
        backend = self.config.EMBEDDING_BACKEND
        if backend == LLMProvider.GROQ.value:
            api_url = self.config.GROQ_API_URL
        elif backend == LLMProvider.OPENAI.value:
            api_url = self.config.OPENAI_EMBEDDING_API_URL
        elif backend == LLMProvider.COHERE.value:
            api_url = None
        else:
            api_url = self.config.OPENAI_EMBEDDING_API_URL

        client = self.create(backend, api_url)
        if client:
            client.set_embedding_model(
                self.config.EMBEDDING_MODEL_ID,
                self.config.EMBEDDING_MODEL_SIZE,
            )
        return client
