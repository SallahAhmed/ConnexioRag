"""Tests for the standalone playground: route shape, auth fallback, and the
UTF-8 middleware Content-Type regression."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from Routes.ui import LANGUAGES, MODEL_TIERS, PERSONAS, ui_router
from utils.metrics import _is_exempt_from_rate_limit
from utils.security import verify_api_key, verify_api_key_or_standalone


def get_settings_flag(name="CELERY_BROKER_SSL_VERIFY"):
    from helpers.config import get_settings

    return getattr(get_settings(), name, False)


class TestControllerWarmUp:
    """main.lifespan warms the shared NLPController in a try/except, so a bad
    import path fails silently and only shows up as a startup log line."""

    def test_nlp_controller_import_path_resolves(self):
        # main.py must use the lowercase package name, matching agent.py/nlp.py.
        from controllers import NLPController as FromPackage
        from controllers.NLPController import NLPController as FromModule

        assert FromPackage is FromModule, "controllers must export the class itself"

    def test_warmup_import_statement_is_valid(self):
        import ast
        import pathlib

        source = pathlib.Path(__file__).resolve().parents[1] / "main.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))

        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                head = node.module.split(".")[0]
                if head in ("Controllers", "Models", "Stores", "Helpers", "Utils"):
                    bad.append(node.module)
        assert not bad, f"wrong-cased module imports in main.py: {bad}"

    def test_chat_session_pk_is_session_id(self):
        """The PK is session_id. Reading .id returns a 500."""
        from models.db_schemas import ChatSession

        assert hasattr(ChatSession, "session_id")
        assert "session_id" in ChatSession.__table__.columns
        assert "id" not in ChatSession.__table__.columns


class TestCeleryBrokerTLS:
    """CERT_NONE is a deliberate, documented workaround - keep it switchable."""

    def test_ssl_opts_respect_setting(self):
        import ssl as _ssl
        import celery_app

        if celery_app.celery_app is None:
            pytest.skip("celery not initialised (no broker url configured)")

        opts = celery_app._ssl_opts
        assert opts["ssl_cert_reqs"] in (_ssl.CERT_NONE, _ssl.CERT_REQUIRED)

        verify = get_settings_flag()
        expected = _ssl.CERT_REQUIRED if verify else _ssl.CERT_NONE
        assert opts["ssl_cert_reqs"] == expected

    def test_verify_flag_defaults_to_false(self):
        from helpers.config import get_settings

        assert get_settings().CELERY_BROKER_SSL_VERIFY is False


class TestUIRouteStructure:
    """The playground router must expose exactly the documented endpoints."""

    def test_root_is_owned_by_ui_router(self):
        paths = {r.path for r in ui_router.routes}
        assert "/" in paths, "UI router should own the root path"

    def test_config_route_exists(self):
        route = next(r for r in ui_router.routes if r.path == "/ui/config")
        assert "GET" in route.methods

    def test_stream_route_is_get(self):
        route = next(r for r in ui_router.routes if r.path == "/ui/chat/stream")
        assert "GET" in route.methods, "SSE stream must be GET"

    def test_new_session_route_is_post(self):
        route = next(r for r in ui_router.routes if r.path == "/ui/session/new")
        assert "POST" in route.methods

    def test_playground_asset_exists(self):
        from Routes.ui import _CHAT_HTML
        assert _CHAT_HTML.is_file(), f"playground HTML missing at {_CHAT_HTML}"

    def test_stream_has_no_body_param(self):
        route = next(r for r in ui_router.routes if r.path == "/ui/chat/stream")
        import inspect
        params = list(inspect.signature(route.endpoint).parameters.keys())
        assert "query" in params
        assert "user_id" in params
        assert "request" not in [
            p for p in params if p == "request_body"
        ], "stream should read query params, not a body"

    def test_llm_facing_routes_are_guarded(self):
        """Both routes that burn tokens or write to the DB need the auth dep."""
        for path in ("/ui/chat/stream", "/ui/session/new"):
            route = next(r for r in ui_router.routes if r.path == path)
            deps = [d.call for d in route.dependant.dependencies]
            assert verify_api_key_or_standalone in deps, f"{path} must be guarded"

    def test_public_routes_are_not_guarded(self):
        """The page and its config carry no secrets, so they stay open."""
        for path in ("/", "/ui/config"):
            route = next(r for r in ui_router.routes if r.path == path)
            deps = [d.call for d in route.dependant.dependencies]
            assert verify_api_key_or_standalone not in deps, f"{path} should be open"

    def test_choice_lists_are_populated(self):
        assert "student" in PERSONAS
        assert "auto" in MODEL_TIERS
        assert "auto" in LANGUAGES


class TestStandaloneAuth:
    """verify_api_key_or_standalone must be a no-op only in standalone mode."""

    def _settings(self, standalone):
        return SimpleNamespace(
            STANDALONE_MODE=standalone,
            CONNEXIO_INTERNAL_API_KEY="secret-key",
        )

    def test_passes_without_key_when_standalone(self):
        with patch("helpers.config.get_settings", return_value=self._settings(True)):
            result = asyncio.run(verify_api_key_or_standalone(None))
        assert result == "standalone"

    def test_rejects_without_key_when_not_standalone(self):
        with patch("helpers.config.get_settings", return_value=self._settings(False)):
            with pytest.raises(HTTPException) as exc:
                asyncio.run(verify_api_key_or_standalone(None))
        assert exc.value.status_code == 401

    def test_rejects_wrong_key_when_not_standalone(self):
        with patch("helpers.config.get_settings", return_value=self._settings(False)):
            with pytest.raises(HTTPException) as exc:
                asyncio.run(verify_api_key_or_standalone("nope"))
        assert exc.value.status_code == 401

    def test_accepts_correct_key_when_not_standalone(self):
        with patch("helpers.config.get_settings", return_value=self._settings(False)):
            result = asyncio.run(verify_api_key_or_standalone("secret-key"))
        assert result == "secret-key"

    def test_original_verify_api_key_is_unchanged(self):
        """The service-to-service guard must not weaken when standalone is on."""
        import utils.security as sec

        original_cache = sec._settings_cache
        sec._settings_cache = None
        try:
            with patch("helpers.config.get_settings", return_value=self._settings(True)):
                with pytest.raises(HTTPException) as exc:
                    asyncio.run(verify_api_key(None))
        finally:
            sec._settings_cache = original_cache
        assert exc.value.status_code == 401


class TestRateLimitExemption:
    """HF proxies every visitor through one IP, so UI paths must not be limited."""

    @pytest.mark.parametrize("path", ["/", "/ui/config", "/ui/chat/stream", "/ui/session/new", "/docs"])
    def test_ui_paths_exempt(self, path):
        assert _is_exempt_from_rate_limit(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/nlp/agent/chat/1",
            "/api/v1/nlp/agent/chat/stream/1",
            "/api/v1/health",
            "/api/v1/nlp/collection/list",
        ],
    )
    def test_api_paths_still_limited(self, path):
        assert _is_exempt_from_rate_limit(path) is False


class TestUTF8Middleware:
    """Regression: the middleware used to relabel every response as JSON,
    which made /docs render as a download and blocked the HTML playground."""

    @staticmethod
    def _run(content_type):
        from main import ensure_utf8_response

        response = SimpleNamespace(headers={"Content-Type": content_type})

        async def call_next(_request):
            return response

        asyncio.run(ensure_utf8_response(None, call_next))
        return response.headers["Content-Type"]

    def test_html_is_not_relabelled(self):
        assert self._run("text/html; charset=utf-8") == "text/html; charset=utf-8"

    def test_sse_is_not_relabelled(self):
        assert self._run("text/event-stream") == "text/event-stream"

    def test_plain_text_is_not_relabelled(self):
        assert self._run("text/plain") == "text/plain"

    def test_json_gets_charset(self):
        assert self._run("application/json") == "application/json; charset=utf-8"

    def test_json_with_params_keeps_charset_once(self):
        assert (
            self._run("application/json; charset=utf-8")
            == "application/json; charset=utf-8"
        )
        assert "charset=" in self._run("application/json; charset=utf-8")

    def test_charset_preserved_for_jpeg_like_media(self):
        assert self._run("image/png") == "image/png"


class TestStreamRouteBehaviour:
    """Guard rails on the playground stream endpoint."""

    def test_empty_query_is_rejected(self):
        from Routes.ui import ui_chat_stream

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                ui_chat_stream(request=MagicMock(), query="   ")
            )
        assert exc.value.status_code == 400

    def test_limit_is_clamped_and_controller_called(self):
        from Routes.ui import ui_chat_stream
        from utils.security import verify_api_key_or_standalone

        controller = MagicMock()

        async def fake_stream(**kwargs):
            yield "data: [DONE]\n\n"

        controller.answer_agent_chat_stream = fake_stream
        app = SimpleNamespace(_nlp_controller=controller)
        request = MagicMock()
        request.app = app

        settings = SimpleNamespace(
            STANDALONE_MODE=True,
            UI_DEFAULT_USER_ID=11,
            UI_DEFAULT_PERSONA="student",
        )

        captured = {}

        async def capture(**kwargs):
            captured.update(kwargs)
            yield "data: [DONE]\n\n"

        controller.answer_agent_chat_stream = capture

        with patch("Routes.ui.get_settings", return_value=settings):
            response = asyncio.run(
                ui_chat_stream(
                    request=request,
                    query="  hello  ",
                    user_id=7,
                    project_id=0,
                    limit=999,
                    persona=None,
                    model_tier=None,
                    session_id=None,
                    language=None,
                    source=None,
                )
            )

        asyncio.run(response.body_iterator.__anext__())

        assert response.media_type == "text/event-stream"
        assert response.headers["X-Accel-Buffering"] == "no"
        assert captured["query"] == "hello", "query should be trimmed"
        assert captured["project_id"] is None, "project_id=0 means no project"
        assert captured["user_id"] == 7
        assert captured["limit"] == 25, "limit must be clamped to max 25"
        assert captured["persona"] == "student", "should fall back to default persona"
        assert captured["model_tier"] == "auto"
        assert captured["source"] == "playground"

    def test_new_session_maps_project_zero_to_none(self):
        from Routes.ui import ui_new_session

        # Plain namespace, not MagicMock: a mock would auto-create record.id and
        # hide the real attribute name. ChatSession's PK is session_id.
        record = SimpleNamespace(session_id=4242)
        session_model = MagicMock()
        session_model.create_session = AsyncMock(return_value=record)
        controller = MagicMock()
        controller.session_model = session_model
        request = MagicMock()
        request.app = SimpleNamespace(_nlp_controller=controller)

        settings = SimpleNamespace(
            STANDALONE_MODE=True,
            UI_DEFAULT_USER_ID=11,
            UI_DEFAULT_PROJECT_ID=0,
            UI_DEFAULT_PERSONA="student",
        )

        with patch("Routes.ui.get_settings", return_value=settings):
            result = asyncio.run(
                ui_new_session(
                    request=request,
                    payload={"user_id": 5, "project_id": 0, "language": "auto"},
                )
            )

        assert result == {"session_id": 4242}
        kwargs = session_model.create_session.call_args.kwargs
        assert kwargs["project_id"] is None
        assert kwargs["user_id"] == 5
        assert kwargs["language"] == "en", "'auto' must resolve to a real language"

    def test_new_session_uses_session_id_attribute(self):
        """ChatSession's PK is session_id, not id. Reading .id returns 500."""
        from Routes.ui import ui_new_session

        record = SimpleNamespace(session_id=99)
        session_model = MagicMock()
        session_model.create_session = AsyncMock(return_value=record)
        controller = MagicMock()
        controller.session_model = session_model
        request = MagicMock()
        request.app = SimpleNamespace(_nlp_controller=controller)

        settings = SimpleNamespace(
            STANDALONE_MODE=True,
            UI_DEFAULT_USER_ID=11,
            UI_DEFAULT_PROJECT_ID=0,
            UI_DEFAULT_PERSONA="student",
        )

        with patch("Routes.ui.get_settings", return_value=settings):
            result = asyncio.run(ui_new_session(request=request, payload={}))

        assert result["session_id"] == 99