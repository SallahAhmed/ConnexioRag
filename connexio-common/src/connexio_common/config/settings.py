"""Base settings class shared by both Connexio RAG and MasarX Agent.

Each service defines its own Settings class that inherits from this base,
adding service-specific fields. Common fields (LLM config, DB, auth)
live here to avoid duplication.
"""

import os
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseSettingsMixin:
    """Mixin providing Pydantic v2 config pattern for all Connexio services."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )


class SharedLLMConfig(BaseSettings):
    """LLM configuration shared across all services."""

    GENERATION_BACKEND: str = "GROQ"
    UTILITY_BACKEND: str = "GROQ"
    EMBEDDING_BACKEND: str = "COHERE"

    GROQ_API_KEY: Optional[str] = None
    GROQ_API_URL: Optional[str] = "https://api.groq.com/openai/v1"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_URL: Optional[str] = None
    OPENAI_GENERATION_API_URL: Optional[str] = None
    OPENAI_EMBEDDING_API_URL: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None

    GENERATION_MODEL_ID: Optional[str] = None
    GENERATION_MODEL_ID_LITERAL: Optional[List[str]] = None
    UTILITY_MODEL_ID: Optional[str] = "llama-3.1-8b-instant"
    EMBEDDING_MODEL_ID: Optional[str] = None
    EMBEDDING_MODEL_SIZE: Optional[int] = None

    INPUT_DEFAULT_MAX_CHARACTERS: int = 4000
    GENERATION_DEFAULT_MAX_TOKENS: int = 1024
    GENERATION_DEFAULT_TEMPERATURE: float = 0.1
    TOTAL_CONTEXT_TOKEN_BUDGET: int = 8000
    TOTAL_CONTEXT_CHAR_BUDGET: int = 25000


class SharedDBConfig(BaseSettings):
    """Database configuration shared across all services."""

    POSTGRES_URL: Optional[str] = None
    PGVECTOR_URL: Optional[str] = None
    POSTGRES_USERNAME: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[int] = None
    POSTGRES_MAIN_DATABASE: Optional[str] = None
    DB_FAIL_FAST: bool = False


class SharedAuthConfig(BaseSettings):
    """Authentication configuration shared across all services."""

    JWT_SECRET: Optional[str] = None
    CONNEXIO_INTERNAL_API_KEY: Optional[str] = None
    SERVICE_USER_ID: Optional[int] = None
    MAIN_BACKEND_URL: str = "https://connexio.icu"


class SharedCeleryConfig(BaseSettings):
    """Celery configuration shared across all services."""

    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_TASK_ACKS_LATE: bool = True
    CELERY_TASK_TIME_LIMIT: int = 600
    CELERY_WORKER_CONCURRENCY: int = 2
    CELERY_FLOWER_PASSWORD: Optional[str] = None
    CELERY_FLOWER_BROKER_API: Optional[str] = None
