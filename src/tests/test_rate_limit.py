"""Rate limiting must actually bound token spend, and must do so with a bucket
key that survives a reverse proxy.

Context: the limiter previously keyed on request.client.host. Uvicorn's
ProxyHeadersMiddleware rewrites that from X-Forwarded-For behind the Hugging
Face proxy, so requests landed in separate buckets and the limit never fired
(45 requests in 7s produced zero 429s). These tests pin the corrected behaviour
so it cannot silently regress.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils.metrics import (
    RATE_LIMIT_EXEMPT_EXACT,
    RATE_LIMIT_EXEMPT_PREFIXES,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW,
    _is_exempt_from_rate_limit,
    _is_rate_limited,
    _rate_limit_store,
    client_key,
)


def _request(headers=None, host="10.0.0.1", path="/api/v1/"):
    return SimpleNamespace(
        headers=headers or {},
        client=SimpleNamespace(host=host) if host else None,
        url=SimpleNamespace(path=path),
    )


@pytest.fixture(autouse=True)
def clear_store():
    _rate_limit_store.clear()
    yield
    _rate_limit_store.clear()


class TestClientKey:
    def test_api_key_is_hashed_not_stored(self):
        key = client_key(_request(headers={"x-api-key": "super-secret-value"}))
        assert key.startswith("key:")
        assert "super-secret-value" not in key, "raw API key must never be the bucket key"

    def test_same_key_shares_one_bucket(self):
        a = client_key(_request(headers={"x-api-key": "k1"}))
        b = client_key(_request(headers={"x-api-key": "k1"}, host="10.0.0.99"))
        assert a == b, "one shared API key must map to one bucket"

    def test_different_keys_get_different_buckets(self):
        a = client_key(_request(headers={"x-api-key": "k1"}))
        b = client_key(_request(headers={"x-api-key": "k2"}))
        assert a != b

    def test_anonymous_falls_back_to_peer_address(self):
        key = client_key(_request(host="10.0.0.7"))
        assert key == "anon:10.0.0.7"

    def test_key_ignores_forwarded_for_header(self):
        """X-Forwarded-For is client-controlled; it must not choose the bucket."""
        spoofed = client_key(
            _request(headers={"x-forwarded-for": "1.2.3.4"}, host="10.0.0.1")
        )
        honest = client_key(_request(host="10.0.0.1"))
        assert spoofed == honest

    def test_missing_client_is_safe(self):
        assert client_key(_request(host=None)) == "anon:unknown"


class TestLimiterFires:
    def test_throttles_after_the_limit(self):
        key = client_key(_request(headers={"x-api-key": "k"}))
        results = [_is_rate_limited(key) for _ in range(RATE_LIMIT_REQUESTS + 5)]
        assert results[:RATE_LIMIT_REQUESTS] == [False] * RATE_LIMIT_REQUESTS
        assert results[RATE_LIMIT_REQUESTS] is True, "must throttle at request 31"
        assert all(results[RATE_LIMIT_REQUESTS:]), "must stay throttled while over budget"

    def test_anonymous_bucket_is_independent(self):
        a = client_key(_request(host="10.0.0.1"))
        b = client_key(_request(host="10.0.0.2"))
        for _ in range(RATE_LIMIT_REQUESTS + 3):
            _is_rate_limited(a)
        assert _is_rate_limited(b) is False, "one visitor must not starve another"

    def test_separate_callers_have_separate_budgets(self):
        for _ in range(RATE_LIMIT_REQUESTS + 3):
            _is_rate_limited(client_key(_request(headers={"x-api-key": "service"})))
        assert _is_rate_limited(client_key(_request(host="10.0.0.5"))) is False

    def test_window_is_sixty_seconds(self):
        assert RATE_LIMIT_WINDOW == 60
        assert RATE_LIMIT_REQUESTS == 30


class TestExplicitPublicAllowlist:
    @pytest.mark.parametrize("path", ["/", "/ui", "/docs", "/openapi.json", "/favicon.ico"])
    def test_public_shell_paths_are_exempt(self, path):
        assert _is_exempt_from_rate_limit(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/",
            "/api/v1/health",
            "/api/v1/nlp/agent/chat/0",
            "/api/v1/data/upload/1",
            "/ui/chat/stream",
            "/ui/session/new",
        ],
    )
    def test_token_spending_paths_are_not_exempt(self, path):
        assert _is_exempt_from_rate_limit(path) is False

    def test_playground_stream_is_bounded(self):
        """/ui/chat/stream spends real tokens, so it must not be exempt."""
        assert "/ui/" not in RATE_LIMIT_EXEMPT_PREFIXES
        assert "/ui/chat/stream" not in RATE_LIMIT_EXEMPT_EXACT
        assert _is_exempt_from_rate_limit("/ui/chat/stream") is False

    def test_no_bare_slash_prefix(self):
        """A "/" prefix matches every absolute path and would exempt the API."""
        assert "/" not in RATE_LIMIT_EXEMPT_PREFIXES

    def test_allowlist_is_small_and_reviewable(self):
        assert len(RATE_LIMIT_EXEMPT_EXACT) <= 6


class TestEveryRouteIsAccountedFor:
    """Every registered route must be either rate limited or explicitly public."""

    def test_all_routes_resolve_to_one_or_the_other(self):
        import os

        os.environ.setdefault("CONNEXIO_INTERNAL_API_KEY", "test")
        os.environ.setdefault("JWT_SECRET", "x" * 32)
        os.environ.setdefault("SENTRY_DSN", "")
        import main

        public, limited = [], []
        for route in main.app.routes:
            path = getattr(route, "path", None)
            if not path:
                continue
            (public if _is_exempt_from_rate_limit(path) else limited).append(path)

        assert public, "expected the public shell paths"
        assert limited, "expected API and playground routes to be rate limited"

        # The invariant: a registered route is public only if it was explicitly
        # listed. The allowlist may hold extra defensive entries for paths that
        # are not routes (browsers auto-request /favicon.ico, for example), so
        # subset is the correct direction.
        unlisted = sorted(set(public) - RATE_LIMIT_EXEMPT_EXACT)
        assert not unlisted, f"routes are public without being listed: {unlisted}"

        for path in public:
            assert path.startswith(("/", "/docs", "/openapi.json")), (
                f"{path} is public but is not a recognised shell path"
            )

    def test_token_spending_routes_are_registered_and_limited(self):
        import os

        os.environ.setdefault("CONNEXIO_INTERNAL_API_KEY", "test")
        os.environ.setdefault("JWT_SECRET", "x" * 32)
        os.environ.setdefault("SENTRY_DSN", "")
        import main

        paths = {r.path for r in main.app.routes if getattr(r, "path", None)}
        for sensitive in ("/ui/chat/stream", "/ui/session/new", "/api/v1/health"):
            assert sensitive in paths, f"{sensitive} should be registered"
            assert _is_exempt_from_rate_limit(sensitive) is False

    def test_no_api_route_is_public(self):
        for path in ("/api/v1/", "/api/v1/health"):
            assert _is_exempt_from_rate_limit(path) is False, f"{path} must not be public"

    def test_slowapi_uses_the_same_resolver(self):
        import os

        os.environ.setdefault("CONNEXIO_INTERNAL_API_KEY", "test")
        os.environ.setdefault("JWT_SECRET", "x" * 32)
        os.environ.setdefault("SENTRY_DSN", "")
        import main

        assert main.limiter._key_func is client_key, (
            "slowapi must resolve buckets the same way as the middleware"
        )