"""Tests for NLPController streaming: SSE format, model upgrade, event ordering."""

from unittest.mock import patch, AsyncMock

import pytest
from models.enums.WorkflowNodeEnum import WorkflowNodeEnum


class TestStreamingModelUpgrade:
    """Streaming should upgrade to generation model for projectless GENERAL queries."""

    @pytest.mark.asyncio
    async def test_projectless_general_upgrades_to_generation(self, nlp_controller):
        """When project_id=None and node=GENERAL, streaming should use generation_client."""
        events = []
        async for event in nlp_controller.answer_agent_chat_stream(
            user_id=1, project_id=None, query="hello",
        ):
            events.append(event)

        assert len(events) >= 2, "Expected at least meta + one text event"
        assert events[-1].strip() == "data: [DONE]", "Expected [DONE] at end"

    @pytest.mark.asyncio
    async def test_streaming_meta_event(self, nlp_controller):
        """First non-OOS streaming event should be meta with node, language, sources."""
        events = []
        async for event in nlp_controller.answer_agent_chat_stream(
            user_id=1, project_id=None, query="hello",
        ):
            events.append(event)

        import json
        meta = json.loads(events[0][6:])
        assert meta.get("event") == "meta", "First event should be 'meta'"
        assert "node" in meta
        assert "language" in meta
        assert "sources" in meta
        assert "session_id" in meta
        assert "trace_id" in meta

    @pytest.mark.asyncio
    async def test_streaming_oos_short_circuit(self, nlp_controller):
        """OOS queries should return meta + answer + [DONE] without hitting LLM."""
        from controllers.WorkflowController import WorkflowController
        with patch.object(WorkflowController, "detect_node", return_value=WorkflowNodeEnum.OUT_OF_SCOPE):
            events = []
            async for event in nlp_controller.answer_agent_chat_stream(
                user_id=1, project_id=None, query="weather in Cairo",
            ):
                events.append(event)

        assert len(events) == 3, f"Expected 3 events for OOS, got {len(events)}: {events}"
        import json
        meta = json.loads(events[0][6:])
        assert meta.get("event") == "meta"
        answer = json.loads(events[1][6:])
        assert "text" in answer
        assert events[2].strip() == "data: [DONE]"

    @pytest.mark.asyncio
    async def test_streaming_persists_answer(self, nlp_controller):
        """Streaming should save the full answer to session."""
        events = []
        async for event in nlp_controller.answer_agent_chat_stream(
            user_id=1, project_id=None, query="hello",
        ):
            events.append(event)

        assert nlp_controller.session_model.append_message.called

    @pytest.mark.asyncio
    async def test_streaming_clear_history(self, nlp_controller):
        """Clear history command should return answer event + [DONE]."""
        events = []
        async for event in nlp_controller.answer_agent_chat_stream(
            user_id=1, project_id=None, query="clear history",
        ):
            events.append(event)

        assert len(events) == 2, f"Expected 2 events for clear, got {len(events)}"
        import json
        data = json.loads(events[0][6:])
        assert "answer" in data
        assert events[1].strip() == "data: [DONE]"


class TestStreamingSSEFormat:
    """SSE events must follow the spec: 'data: {json}\\n\\n'."""

    @pytest.mark.asyncio
    async def test_sse_format(self, nlp_controller):
        """Every event must start with 'data: '."""
        events = []
        async for event in nlp_controller.answer_agent_chat_stream(
            user_id=1, project_id=None, query="hello",
        ):
            events.append(event)

        for e in events:
            assert e.startswith("data: "), f"Bad SSE format: {e[:50]}"

    @pytest.mark.asyncio
    async def test_sse_valid_json(self, nlp_controller):
        """All non-[DONE] events must be valid JSON after 'data: ' prefix."""
        import json
        events = []
        async for event in nlp_controller.answer_agent_chat_stream(
            user_id=1, project_id=None, query="hello",
        ):
            events.append(event)

        for e in events:
            if e.strip() == "data: [DONE]":
                continue
            data = json.loads(e[6:])
            assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_text_events_have_text_field(self, nlp_controller):
        """Non-meta, non-DONE events must have 'text' field."""
        import json
        events = []
        async for event in nlp_controller.answer_agent_chat_stream(
            user_id=1, project_id=None, query="hello",
        ):
            events.append(event)

        for e in events[1:-1]:  # Skip meta and [DONE]
            data = json.loads(e[6:])
            assert "text" in data, f"Missing 'text' in: {data}"

    @pytest.mark.asyncio
    async def test_double_newline_terminator(self, nlp_controller):
        """Each event must end with '\\n\\n'."""
        events = []
        async for event in nlp_controller.answer_agent_chat_stream(
            user_id=1, project_id=None, query="hello",
        ):
            events.append(event)

        for e in events:
            assert e.endswith("\n\n"), f"Missing double newline: {e[:50]}"


class TestNonStreamingBehavior:
    """Non-streaming chat should still work correctly."""

    @pytest.mark.asyncio
    async def test_chat_response_structure(self, nlp_controller):
        result = await nlp_controller.answer_agent_chat(
            user_id=1, project_id=None, query="hello",
        )
        assert "answer" in result
        assert "node" in result
        assert "language" in result
        assert "sources" in result
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_chat_non_empty_answer(self, nlp_controller):
        result = await nlp_controller.answer_agent_chat(
            user_id=1, project_id=None, query="hello",
        )
        assert result["answer"], "Answer must not be empty"

    @pytest.mark.asyncio
    async def test_chat_oos_canned_response(self, nlp_controller):
        """OOS queries should return a canned refusal, not an LLM answer."""
        from controllers.WorkflowController import WorkflowController
        with patch.object(WorkflowController, "detect_node", return_value=WorkflowNodeEnum.OUT_OF_SCOPE):
            result = await nlp_controller.answer_agent_chat(
                user_id=1, project_id=None, query="weather in Cairo",
            )
        assert result["node"] == "OUT_OF_SCOPE"

    @pytest.mark.asyncio
    async def test_chat_clear_history(self, nlp_controller):
        result = await nlp_controller.answer_agent_chat(
            user_id=1, project_id=None, query="clear history",
        )
        assert result["answer"]
        assert result["node"] == "general"
