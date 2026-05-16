"""OpenAI-compatible provider (works with OpenAI, Groq, Ollama, any OpenAI-compatible API)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, List, Optional, Type, Union

from openai import AsyncOpenAI
from pydantic import BaseModel

from .. import LLMInterface, OpenAIRoles


class StructuredLLMWrapper:
    """Wraps an OpenAIProvider to produce structured (Pydantic) output."""

    def __init__(self, provider: "OpenAIProvider", schema: Type[BaseModel]) -> None:
        self.provider = provider
        self.schema = schema

    async def ainvoke(self, messages: list) -> Any:
        self.provider._create_client()
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                if (
                    hasattr(self.provider.client.beta.chat.completions, "parse")
                    and "groq" not in (self.provider.api_url or "").lower()
                ):
                    response = await self.provider.client.beta.chat.completions.parse(
                        model=self.provider.generation_model_id,
                        messages=messages,
                        response_format=self.schema,
                    )
                    return response.choices[0].message.parsed
                else:
                    response = await self.provider.client.chat.completions.create(
                        model=self.provider.generation_model_id,
                        messages=messages,
                        response_format={"type": "json_object"},
                    )
                    content = response.choices[0].message.content
                    return self.schema.model_validate(json.loads(content))

            except Exception as e:
                if attempt < max_retries - 1:
                    logging.getLogger(__name__).warning(
                        f"Structured generation attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return await self._graceful_fallback(messages)

    async def _graceful_fallback(self, messages: list) -> Any:
        try:
            self.provider._create_client()
            response = await self.provider.client.chat.completions.create(
                model=self.provider.generation_model_id,
                messages=messages
                + [
                    {
                        "role": "system",
                        "content": "IMPORTANT: Return ONLY valid JSON matching this exact schema structure.",
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=1000,
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            return self._loose_validate(data)
        except Exception as fallback_error:
            raise Exception(f"All parsing attempts failed. Last error: {fallback_error}")

    def _loose_validate(self, data: dict) -> Any:
        schema_name = self.schema.__name__

        if schema_name == "EndorsedSkillsResult":
            skills = data.get("endorsedSkills", [])
            normalized = []
            for s in skills:
                if isinstance(s, str):
                    normalized.append(
                        {
                            "skill": s,
                            "evidence": "Endorsed based on task completion",
                            "proficiencyLevel": "intermediate",
                        }
                    )
                elif isinstance(s, dict):
                    normalized.append(
                        {
                            "skill": s.get("skill", s.get("skillName", "Unknown")),
                            "evidence": s.get(
                                "evidence", s.get("description", "Endorsed based on task completion")
                            ),
                            "proficiencyLevel": s.get("proficiencyLevel", s.get("level", "intermediate")),
                        }
                    )
            return self.schema(
                endorsedSkills=normalized,
                summary=data.get("summary", "Skills endorsed based on task analysis"),
            )

        if schema_name == "PRBusinessSummary":
            return self.schema(
                prNumber=data.get("prNumber", data.get("pr_number", 0)),
                prTitle=data.get("prTitle", data.get("pr_title", "Untitled PR")),
                summary=data.get("summary", "PR translated successfully"),
                businessImpact=data.get("businessImpact", data.get("business_impact", [])),
                technicalChanges=data.get("technicalChanges", data.get("technical_changes", [])),
                risksOrConcerns=data.get("risksOrConcerns", data.get("risks_or_concerns", [])),
                reviewNotes=data.get("reviewNotes", data.get("review_notes", "")),
            )

        if schema_name == "TaskPlan":
            tasks = data.get("tasks", [])
            normalized = []
            for t in tasks:
                if isinstance(t, dict):
                    normalized.append(
                        {
                            "title": t.get("title", "Untitled Task"),
                            "description": t.get("description", ""),
                            "priority": t.get("priority", "medium"),
                            "story_points": t.get("story_points", t.get("storyPoints", 1)),
                            "assignee": t.get("assignee", None),
                        }
                    )
            return self.schema(
                tasks=normalized, summary=data.get("summary", "Task plan created")
            )

        return self.schema.model_validate(data)


class OpenAIProvider(LLMInterface):
    def __init__(
        self,
        api_key: str,
        api_url: Optional[str] = None,
        default_input_max_characters: int = 1000,
        default_generation_max_output_tokens: int = 1024,
        default_generation_temperature: float = 0.1,
        request_timeout: float = 30.0,
        max_retries: int = 1,
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature
        self.generation_model_id: Optional[str] = None
        self.embedding_model_id: Optional[str] = None
        self.embedding_size: Optional[int] = None
        self.client: Optional[AsyncOpenAI] = None
        self._structured_client: Optional[Any] = None
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        self.last_usage: Optional[dict] = None

    def _create_client(self) -> None:
        if self.client is None:
            base = (
                self.api_url.strip()
                if isinstance(self.api_url, str) and self.api_url.strip()
                else None
            )
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=base,
                timeout=self.request_timeout,
                max_retries=self.max_retries,
            )

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

        self._create_client()

        if not self.generation_model_id:
            self.logger.error("Generation model was not set")
            return None

        max_output_tokens = max_output_tokens or self.default_generation_max_output_tokens
        temperature = temperature or self.default_generation_temperature

        local_history = list(chat_history)
        if isinstance(prompt, str):
            local_history.append(self.construct_prompt(prompt=prompt, role=OpenAIRoles.USER.value))
        elif isinstance(prompt, list):
            local_history.extend(prompt)

        retry_delay = 1
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.generation_model_id,
                    messages=local_history,
                    max_tokens=max_output_tokens,
                    temperature=temperature,
                )

                if response and response.usage:
                    self.last_usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }

                if not response or not response.choices:
                    self.logger.warning("LLM returned empty response")
                    return ""

                answer = response.choices[0].message.content
                return answer if answer else ""

            except Exception as e:
                if attempt < self.max_retries:
                    self.logger.warning(
                        f"Generation attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    self.logger.error(f"Generation failed after {self.max_retries + 1} attempts: {e}")
                    return f"Error during generation: {e}"

    async def generate_text_stream(
        self,
        prompt: str,
        chat_history: Optional[list] = None,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        if chat_history is None:
            chat_history = []

        self._create_client()

        if not self.generation_model_id:
            self.logger.error("Generation model was not set")
            yield None
            return

        max_output_tokens = max_output_tokens or self.default_generation_max_output_tokens
        temperature = temperature or self.default_generation_temperature

        local_history = list(chat_history)
        if isinstance(prompt, str):
            local_history.append(self.construct_prompt(prompt=prompt, role=OpenAIRoles.USER.value))
        elif isinstance(prompt, list):
            local_history.extend(prompt)

        try:
            stream = await self.client.chat.completions.create(
                model=self.generation_model_id,
                messages=local_history,
                max_tokens=max_output_tokens,
                temperature=temperature,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            self.logger.error(f"Streaming generation error: {e}")
            yield f"Error: {e}"

    async def embed_text(
        self,
        text: Union[str, List[str]],
        document_type: Optional[str] = None,
    ) -> Optional[List[List[float]]]:
        self._create_client()

        if not self.embedding_model_id:
            self.logger.error("Embedding model was not set")
            return None

        if isinstance(text, str):
            text = [text]

        text = [self.process_text(t, self.default_input_max_characters) for t in text]

        # Handle Nomic-style prefixes
        if self.embedding_model_id and "nomic-embed-text" in self.embedding_model_id:
            if document_type == "query":
                text = [f"search_query: {t}" for t in text]
            elif document_type == "document":
                text = [f"search_document: {t}" for t in text]

        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model_id,
                input=text,
            )

            if not response or not response.data or len(response.data) == 0:
                self.logger.error("Embedding response contained no data")
                return None

            return [rec.embedding for rec in response.data]

        except Exception as e:
            self.logger.error(f"Error while embedding text: {e}")
            return None

    def construct_prompt(self, prompt: str, role: str) -> dict:
        return {"role": role, "content": prompt}

    def with_structured_output(self, schema: Type[BaseModel]) -> StructuredLLMWrapper:
        return StructuredLLMWrapper(self, schema)

    def create_structured_client(self, schema: Type[BaseModel]) -> StructuredLLMWrapper:
        return StructuredLLMWrapper(self, schema)
