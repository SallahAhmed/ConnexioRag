from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
from collections import defaultdict

# Define metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP Request Latency', ['method', 'endpoint'])

# Rate limiting state
_rate_limit_store = defaultdict(list)
RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW = 60

def _is_rate_limited(client_ip: str) -> bool:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    timestamps = _rate_limit_store[client_ip]
    timestamps = [t for t in timestamps if t > window_start]
    _rate_limit_store[client_ip] = timestamps
    if len(timestamps) >= RATE_LIMIT_REQUESTS:
        return True
    timestamps.append(now)
    return False

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        start_time = time.time()

        # Rate limiting
        client_ip = request.client.host if request.client else "unknown"
        if _is_rate_limited(client_ip):
            from fastapi.responses import JSONResponse
            from fastapi import status
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"signal": "RATE_LIMITED", "error": f"Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s. Try again later."},
            )

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