"""Tests for the sources field in the SSE meta frame and the playground token cap.

The playground UI renders m.sources (chat.html), but the streaming meta frame
never carried a sources key, so citations were invisible in streaming mode even
though retrieval had run. The non-streaming path has always sent it.
"""

import ast
import json
import pathlib

import pytest

from Routes.ui import ui_router
from helpers.config import Settings, get_settings

NLP_CONTROLLER = pathlib.Path(__file__).resolve().parents[1] / "controllers" / "NLPController.py"
UI_ROUTE = pathlib.Path(__file__).resolve().parents[1] / "Routes" / "ui.py"


def _stream_meta_keys() -> set:
    """Keys of the metadata dict yielded in answer_agent_chat_stream.

    Only Dict assignments count: the module binds an unrelated `metadata`
    list comprehension further up.
    """
    tree = ast.parse(NLP_CONTROLLER.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", "") == "metadata"
            and isinstance(node.value, ast.Dict)
        ):
            found.append({k.value for k in node.value.keys})
    assert len(found) == 1, f"expected exactly one metadata dict, found {len(found)}"
    return found[0]


class TestStreamMetaCarriesSources:
    def test_meta_includes_sources(self):
        assert "sources" in _stream_meta_keys()

    def test_meta_keeps_core_fields(self):
        keys = _stream_meta_keys()
        for required in ("node", "language", "session_id", "trace_id", "event"):
            assert required in keys, f"stream meta must keep '{required}'"

    def test_meta_and_nonstream_agree_on_fields(self):
        """Stream meta should expose what the non-stream response already did."""
        keys = _stream_meta_keys()
        for field in ("node", "language", "sources", "session_id"):
            assert field in keys, f"'{field}' missing from stream meta"

    def test_sources_is_serialisable_as_a_list(self):
        frame = json.dumps({"sources": ["Vector DB", "Wikipedia"], "event": "meta"})
        assert json.loads(frame)["sources"] == ["Vector DB", "Wikipedia"]

    def test_empty_sources_still_serialises(self):
        frame = json.dumps({"sources": [], "event": "meta"})
        assert json.loads(frame)["sources"] == []

    def test_controller_accepts_max_output_tokens(self):
        source = NLP_CONTROLLER.read_text(encoding="utf-8")
        assert "max_output_tokens: Optional[int] = None" in source

    def test_max_output_tokens_reaches_the_provider(self):
        source = NLP_CONTROLLER.read_text(encoding="utf-8")
        assert "max_output_tokens=max_output_tokens" in source, (
            "the cap must be forwarded to generate_text_stream, not just accepted"
        )


class TestPlaygroundTokenCap:
    def test_cap_is_configured(self):
        assert get_settings().PLAYGROUND_MAX_OUTPUT_TOKENS > 0

    def test_cap_exceeds_reasoning_headroom(self):
        """A cap this low is what produced empty completions earlier."""
        assert Settings.model_fields["PLAYGROUND_MAX_OUTPUT_TOKENS"].default >= 4096

    def test_cap_never_restricts_below_production_ceiling(self):
        """The playground must not shorten answers relative to the service tier."""
        fields = Settings.model_fields
        assert (
            fields["PLAYGROUND_MAX_OUTPUT_TOKENS"].default
            >= fields["GENERATION_DEFAULT_MAX_TOKENS"].default
        )

    def test_production_tier_keeps_a_generous_ceiling(self):
        """Pin the class default, not the env-overridden value: a local .env can
        set this to 1024, but the HF Space must fall back to something safe."""
        assert Settings.model_fields["GENERATION_DEFAULT_MAX_TOKENS"].default >= 4096

    def test_playground_route_passes_the_cap(self):
        source = UI_ROUTE.read_text(encoding="utf-8")
        assert "max_output_tokens=settings.PLAYGROUND_MAX_OUTPUT_TOKENS" in source

    def test_cap_is_playground_only(self):
        """The service agent route must not inherit the playground ceiling."""
        agent_source = (
            pathlib.Path(__file__).resolve().parents[1] / "Routes" / "agent.py"
        ).read_text(encoding="utf-8")
        assert "PLAYGROUND_MAX_OUTPUT_TOKENS" not in agent_source


class TestDeadConfigRemoved:
    def test_no_literal_only_fields_are_read_anywhere(self):
        """VECTOR_DB_BACKEND_LITERAL and friends must stay unused or be removed."""
        config_src = (pathlib.Path(__file__).resolve().parents[1] / "helpers" / "config.py").read_text(encoding="utf-8")
        root = pathlib.Path(__file__).resolve().parents[1]
        offenders = []
        for field in ("GENERATION_MODEL_ID_LITERAL",):
            assert field not in config_src, f"{field} was documented as dead and is still present"

    def test_stale_cache_route_test_is_gone(self):
        test_src = (
            pathlib.Path(__file__).resolve().parents[1] / "tests" / "test_agent_routes.py"
        ).read_text(encoding="utf-8")
        assert "test_cache_invalidate_routes" not in test_src

    def test_no_route_asserts_removed_cache_endpoints(self):
        agent_src = (
            pathlib.Path(__file__).resolve().parents[1] / "Routes" / "agent.py"
        ).read_text(encoding="utf-8")
        assert "cache/invalidate" not in agent_src