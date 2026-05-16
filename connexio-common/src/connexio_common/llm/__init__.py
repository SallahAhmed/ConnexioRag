"""Shared LLM provider interface and enumerations."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, List, Optional


class LLMProvider(str, Enum):
    OPENAI = "OPENAI"
    COHERE = "COHERE"
    GROQ = "GROQ"


class OpenAIRoles(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class CoHereRoles(str, Enum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    ASSISTANT = "CHATBOT"
    DOCUMENT = "search_document"
    QUERY = "search_query"


class DocumentType(str, Enum):
    DOCUMENT = "document"
    QUERY = "query"


class LLMInterface(ABC):
    @abstractmethod
    def set_generation_model(self, model_id: str) -> None: ...

    @abstractmethod
    def set_embedding_model(self, model_id: str, embedding_size: int) -> None: ...

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        chat_history: Optional[list] = None,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Optional[str]: ...

    @abstractmethod
    async def generate_text_stream(
        self,
        prompt: str,
        chat_history: Optional[list] = None,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ): ...

    @abstractmethod
    async def embed_text(
        self,
        text: str | List[str],
        document_type: Optional[str] = None,
    ) -> Optional[List[List[float]]]: ...

    @abstractmethod
    def construct_prompt(self, prompt: str, role: str) -> dict: ...

    def process_text(self, text: str, max_chars: int = 1000) -> str:
        return text[:max_chars].strip()
