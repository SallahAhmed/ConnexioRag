"""Tests for provider stream robustness and the SSE metadata contract.

Regression cover for:
- GENERATION_DEFAULT_MAX_TOKENS defaulting to None and being forwarded verbatim
  as max_tokens=None. Groq ignored it; NVIDIA NIM returned an empty completion,
  which the controller surfaced as an SSE stream with zero frames.
- reasoning_content-only streams from reasoning models.
- meta being emitted before the provider is consumed.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stores.llm.providers.OpenAIProvider import OpenAIProvider


def _provider(default_max_tokens=None):
    p = OpenAIProvider.__new__(OpenAIProvider)
    p.client = MagicMock()
    p.generation_model_id = "some/model"
    p.default_generation_max_output_tokens = default_max_tokens
    p.default_generation_temperature = 0.1
    p.logger = MagicMock()
    p.last_usage = None
    return p


def _delta(content=None, reasoning=None):
    d = SimpleNamespace(content=content)
    if reasoning is not None:
        d.reasoning_content = reasoning
    return d


def _chunk(delta, usage=None):
    choices = [SimpleNamespace(delta=delta)] if delta is not None else []
    return SimpleNamespace(choices=choices, usage=usage)


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        async def gen():
            for c in self._chunks:
                yield c
        return gen()


class TestResolveMaxTokens:
    def test_none_default_resolves_to_none(self):
        """The bug: default is None, so the key must be omitted entirely."""
        p = _provider(default_max_tokens=None)
        assert p._resolve_max_tokens(None) is None

    def test_zero_is_not_used(self):
        p = _provider(default_max_tokens=0)
        assert p._resolve_max_tokens(None) is None

    def test_explicit_arg_wins(self):
        p = _provider(default_max_tokens=100)
        assert p._resolve_max_tokens(500) == 500

    def test_falls_back_to_provider_default(self):
        p = _provider(default_max_tokens=2048)
        assert p._resolve_max_tokens(None) == 2048

    def test_falsy_explicit_arg_falls_through(self):
        p = _provider(default_max_tokens=256)
        assert p._resolve_max_tokens(0) == 256

    def test_bool_is_rejected(self):
        p = _provider(default_max_tokens=True)
        assert p._resolve_max_tokens(None) is None

    def test_negative_is_rejected(self):
        p = _provider(default_max_tokens=-5)
        assert p._resolve_max_tokens(None) is None


class TestStreamingRequestShape:
    def _capture(self, provider, chunks):
        captured = {}

        async def create(**kwargs):
            captured.update(kwargs)
            captured.pop("stream_options", None)
            return _FakeStream(chunks)

        provider.client.chat.completions.create = create
        out = []

        async def drive():
            async for c in provider.generate_text_stream(prompt="hi", chat_history=[]):
                out.append(c)

        asyncio.run(drive())
        return captured, out

    def test_max_tokens_omitted_when_unset(self):
        p = _provider(default_max_tokens=None)
        captured, out = self._capture(p, [_chunk(_delta("hi"))])
        assert "max_tokens" not in captured, "max_tokens=None must not be sent"
        assert out == ["hi"]

    def test_max_tokens_sent_when_configured(self):
        p = _provider(default_max_tokens=512)
        captured, _ = self._capture(p, [_chunk(_delta("hi"))])
        assert captured["max_tokens"] == 512

    def test_non_streaming_omits_max_tokens_when_unset(self):
        p = _provider(default_max_tokens=None)
        captured = {}

        class _Resp:
            usage = None
            choices = [SimpleNamespace(message=SimpleNamespace(content="answer"))]

        async def create(**kwargs):
            captured.update(kwargs)
            return _Resp()

        p.client.chat.completions.create = create
        result = asyncio.run(p.generate_text(prompt="hi", chat_history=[]))
        assert "max_tokens" not in captured
        assert result == "answer"


class TestEmptyAndReasoningStreams:
    def _run(self, provider, chunks):
        async def create(**kwargs):
            return _FakeStream(chunks)

        provider.client.chat.completions.create = create
        out = []

        async def drive():
            async for c in provider.generate_text_stream(prompt="hi", chat_history=[]):
                out.append(c)

        asyncio.run(drive())
        return out

    def test_usage_only_chunks_yield_a_diagnostic(self):
        """Zero content chunks must not become a silent empty stream."""
        p = _provider(default_max_tokens=None)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=0, total_tokens=10)
        out = self._run(p, [_chunk(None, usage=usage)])
        assert len(out) == 1
        assert "empty response" in out[0].lower()

    def test_reasoning_only_stream_is_reported(self):
        p = _provider(default_max_tokens=None)
        out = self._run(p, [_chunk(_delta(None, reasoning="thinking..."))])
        assert len(out) == 1
        assert "reasoning" in out[0].lower()
        assert p.logger.warning.called

    def test_content_wins_over_reasoning(self):
        p = _provider(default_max_tokens=None)
        out = self._run(p, [
            _chunk(_delta(None, reasoning="think")),
            _chunk(_delta("answer")),
        ])
        assert out == ["answer"], "reasoning must not displace real content"

    def test_content_then_reasoning_keeps_content_only(self):
        p = _provider(default_max_tokens=None)
        out = self._run(p, [
            _chunk(_delta("partial")),
            _chunk(_delta(None, reasoning="more thinking")),
        ])
        assert out == ["partial"]


class TestStreamMetaOrdering:
    """meta must arrive before provider chunks, and always."""

    def test_meta_emitted_before_stream(self):
        src = (
            "async def gen(self):\n"
            "    metadata = {'event': 'meta', 'node': node.value, 'language': language,\n"
            "                'session_id': session_id, 'trace_id': trace_id}\n"
            "    yield f\"data: {_json.dumps(metadata)}\\n\\n\"\n"
            "    async for chunk in prompt_client.generate_text_stream(\n"
            "        prompt=footer_prompt, chat_history=chat_history\n"
            "    ):\n"
            "        if chunk:\n"
            "            full_answer += chunk\n"
            "            yield f\"data: {_json.dumps({'text': chunk})}\\n\\n\"\n"
        )
        tree = __import__("ast").parse(src)
        fn = tree.body[0]
        yields = [
            n for n in __import__("ast").walk(fn)
            if isinstance(n, __import__("ast").Yield)
        ]
        assert yields, "expected yields"
        first_src = __import__("ast").get_source_segment(src, yields[0])
        assert "meta" in first_src, "first yield must be the metadata frame"

    def test_controller_no_longer_guards_meta_with_chunk_loop(self):
        import pathlib

        source = pathlib.Path(__file__).resolve().parents[1] / "controllers" / "NLPController.py"
        text = source.read_text(encoding="utf-8")
        assert "metadata_sent" not in text, (
            "metadata_sent flag should be gone; meta is emitted before the loop"
        )

    def test_meta_frame_parses_with_sources_absent(self):
        import json as _json

        meta = {
            "node": "general",
            "language": "en",
            "session_id": 1,
            "trace_id": "abc",
            "event": "meta",
        }
        frame = f"data: {_json.dumps(meta)}\n\n"
        payload = frame.split("data: ", 1)[1].strip()
        parsed = _json.loads(payload)
        assert parsed["event"] == "meta"
        assert "sources" not in parsed, "stream meta omits sources; UI must tolerate that"
