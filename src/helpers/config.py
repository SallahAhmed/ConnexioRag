from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    
    APP_NAME: str = "Connexio"
    APP_VERSION: str = "0.1"

    FILE_ALLOWED_TYPES: list = ["application/pdf", "text/plain"]
    FILE_MAX_SIZE: int = 10
    FILE_DEFAULT_CHUNK_SIZE: int = 1024

    # MONGODB_URL: str
    # MONGODB_DATABASE: str

    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_MAIN_DATABASE: str

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    GENERATION_BACKEND: str = "GROQ"
    EMBEDDING_BACKEND: str = "COHERE"

    OPENAI_API_KEY: str | None = None
    OPENAI_API_URL: str | None = None
    OPENAI_GENERATION_API_URL: str | None = None
    OPENAI_EMBEDDING_API_URL: str | None = None
    COHERE_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    GROQ_API_URL: str | None = "https://api.groq.com/openai/v1"
    SERPAPI_API_KEY: str | None = None
    GITHUB_TOKEN: str | None = None

    GENERATION_MODEL_ID_LITERAL: List[str] | None = None
    GENERATION_MODEL_ID: str | None = None
    UTILITY_MODEL_ID: str | None = "llama-3.1-8b-instant"
    EMBEDDING_MODEL_ID: str | None = None
    EMBEDDING_MODEL_SIZE: int | None = None
    INPUT_DEFAULT_MAX_CHARACTERS: int | None = None
    GENERATION_DEFAULT_MAX_TOKENS: int | None = None
    GENERATION_DEFAULT_TEMPERATURE: float | None = None
    TOTAL_CONTEXT_TOKEN_BUDGET: int = 4000
    TOTAL_CONTEXT_CHAR_BUDGET: int = 12000

    VECTOR_DB_BACKEND_LITERAL: List[str] | None = None
    VECTOR_DB_BACKEND : str = "PGVECTOR"
    VECTOR_DB_PATH : str = "qdrant_db"
    VECTOR_DB_DISTANCE_METHOD: str = "cosine"
    VECTOR_DB_PGVEC_INDEX_THRESHOLD: int = 100

    DEFAULT_LANG: str = "en"
    PRIMARY_LANG: str = "en"

    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_TASK_TIME_LIMIT: int = 600
    CELERY_TASK_ACKS_LATE: bool = False
    CELERY_WORKER_CONCURRENCY: int = 2
    CELERY_FLOWER_PASSWORD: str | None = None
    CELERY_FLOWER_BROKER_API: str | None = None

    CONNEXIO_INTERNAL_API_KEY: str | None = None
    JWT_SECRET: str | None = None
    MAIN_BACKEND_URL: str = "https://connexio.icu"

    class Config:
        env_file= ".env"

def get_settings():
    return Settings()
