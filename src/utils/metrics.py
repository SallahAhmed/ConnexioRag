from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import hashlib
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

# Define metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP Request Latency', ['method', 'endpoint'])

# Rate limiting state
_rate_limit_store = defaultdict(list)
RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW = 60
_last_key_log: dict = {}


def client_key(request: Request) -> str:
    """Resolve a stable rate-limit bucket for a request.

    Keying on request.client.host did not work behind the Hugging Face proxy:
    uvicorn's ProxyHeadersMiddleware rewrites client.host from X-Forwarded-For,
    so requests that should share a bucket landed in separate ones and the limit
    effectively never fired.

    Keying on the API key instead matches how this service is actually called -
    there is a single shared key, so there is exactly one service bucket. Requests
    without a key (the public playground) fall back to the peer address.

    The API key is hashed rather than stored, so the shared secret never sits in
    a long-lived dict key.
    """
    api_key = request.headers.get("x-api-key")
    if api_key:
        return "key:" + hashlib.sha256(api_key.encode()).hexdigest()[:16]
    host = request.client.host if request.client else "unknown"
    return "anon:" + host


def _log_key_once_per_minute(request: Request, key: str, limited: bool) -> None:
    """Make the resolved bucket visible in logs, rate-limited so it cannot spam.

    This is what makes the limiter diagnosable without another deploy.
    """
    now = time.time()
    last = _last_key_log.get("at", 0.0)
    if now - last < 60:
        return
    _last_key_log["at"] = now
    host = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    logger.warning(
        "[RATELIMIT] key=%s peer_host=%s xff=%s path=%s throttled=%s keys_tracked=%d",
        key, host, forwarded or "-", request.url.path, limited, len(_rate_limit_store),
    )


def _is_rate_limited(client_key_value: str) -> bool:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    timestamps = _rate_limit_store[client_key_value]
    timestamps = [t for t in timestamps if t > window_start]
    _rate_limit_store[client_key_value] = timestamps
    if len(timestamps) >= RATE_LIMIT_REQUESTS:
        return True
    timestamps.append(now)
    return False


# Paths reachable without an API key. Everything else is rate limited.
# This is deliberately an explicit, reviewable allowlist rather than an implicit
# side effect: adding a route here is what makes it public.
RATE_LIMIT_EXEMPT_EXACT = {"/", "/ui", "/docs", "/openapi.json", "/favicon.ico"}
# "/ui" itself is the page shell. The routes under it are NOT exempt:
# /ui/chat/stream spends LLM tokens, so it has to be bounded.
RATE_LIMIT_EXEMPT_PREFIXES = ("/static/",)


def _is_exempt_from_rate_limit(path: str) -> bool:
    """
    Public, unauthenticated, non-token-spending paths are not rate limited.

    Hugging Face Spaces proxies every visitor through one address, so exempting
    paths would otherwise let a single visitor starve everyone. Exempting the
    token-spending playground would remove any bound on spend.

    Matching is by exact path or explicit sub-prefix. A bare "/" prefix is never
    used here, because every absolute path starts with "/" and it would exempt
    the entire API.
    """
    if path in RATE_LIMIT_EXEMPT_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in RATE_LIMIT_EXEMPT_PREFIXES)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        start_time = time.time()

        # Rate limiting
        bucket = client_key(request)
        limited = False
        if not _is_exempt_from_rate_limit(request.url.path):
            limited = _is_rate_limited(bucket)
        if limited:
            _log_key_once_per_minute(request, bucket, True)
            from fastapi.responses import JSONResponse
            from fastapi import status
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"signal": "RATE_LIMITED", "error": f"Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s. Try again later."},
            )
        _log_key_once_per_minute(request, bucket, False)

        # Process the request
        response = await call_next(request)

        # Record metrics after request is processed
        duration = time.time() - start_time
        endpoint = request.url.path

        REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)
        REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()

        return response
    
def setup_metrics(app: FastAPI):
    """
    Setup Prometheus metrics middleware and endpoint
    """
    # Add Prometheus middleware
    app.add_middleware(PrometheusMiddleware)

    @app.get("/TrhBVe_m5gg2002_E5VVqS", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)