"""Tests for agent route definitions: streaming headers, API structure."""

from Routes.agent import agent_router


class TestAgentRouteStructure:
    """Routes must have correct paths, methods, and dependencies."""

    def test_chat_route_exists(self):
        route = next(r for r in agent_router.routes if r.path == "/api/v1/nlp/agent/chat/{project_id}")
        assert "POST" in route.methods, "Chat should be POST"

    def test_stream_route_exists(self):
        route = next(r for r in agent_router.routes if r.path == "/api/v1/nlp/agent/chat/stream/{project_id}")
        assert "GET" in route.methods, "Stream should be GET for SSE"

    def test_stream_has_no_body_param(self):
        route = next(r for r in agent_router.routes if r.path == "/api/v1/nlp/agent/chat/stream/{project_id}")
        # Should use query params, not request body
        assert hasattr(route, "endpoint")
        import inspect
        sig = inspect.signature(route.endpoint)
        params = list(sig.parameters.keys())
        assert "query" in params, "Stream route needs 'query' param"
        assert "user_id" in params, "Stream route needs 'user_id' param"

    def test_cache_invalidate_routes(self):
        routes = [
            r for r in agent_router.routes
            if "/cache/invalidate/" in r.path
        ]
        assert len(routes) == 2, "Expected 2 cache invalidation routes"

    def test_api_key_dependency(self):
        assert len(agent_router.dependencies) == 1
        from utils.security import verify_api_key
        dep = agent_router.dependencies[0]
        assert dep.dependency is verify_api_key, "Router should require X-API-Key"


class TestStreamingHeaders:
    """StreamingResponse must include anti-buffering headers for HF Spaces proxy."""

    def test_stream_response_has_headers(self):
        """Verify the streaming endpoint wraps response with proper SSE headers."""
        import inspect
        from fastapi.responses import StreamingResponse

        route = next(
            r for r in agent_router.routes
            if r.path == "/api/v1/nlp/agent/chat/stream/{project_id}"
        )

        source = inspect.getsource(route.endpoint)
        assert "StreamingResponse" in source, "Stream endpoint must use StreamingResponse"
        assert "Cache-Control" in source, "Must set Cache-Control header"
        assert "no-cache" in source, "Cache-Control must include no-cache"
        assert "X-Accel-Buffering" in source, "Must set X-Accel-Buffering=no"
        assert "Connection" in source, "Must set Connection header"
        assert "keep-alive" in source, "Connection must be keep-alive"
        assert "Pragma" in source, "Must set Pragma header"
        assert "Expires" in source, "Must set Expires header"
        assert "text/event-stream" in source, "Media type must be text/event-stream"
