"""
HTTP client for calling the main Connexio backend REST API.

The RAG never touches the main backend's database directly.
All live project/user/task data is fetched through these REST calls.

Authentication: the RAG authenticates to the main backend using a
short-lived service JWT signed with the shared JWT_SECRET. This is
the same pattern MasarX uses for backend→agent communication.

Caching: user profiles and project details are cached in-memory for
5 minutes per instance to avoid hammering the main backend on every
tool invocation. Tasks are NOT cached because they change frequently.
"""
import asyncio
import logging
import time
import jwt
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Seconds before a cached entry is considered stale
_CACHE_TTL_STABLE = 300   # 5 min
_CACHE_TTL_VOLATILE = 0   # no cache — tasks
_REQUEST_TIMEOUT = 10.0
_MAX_RETRIES = 2


class BackendApiClient:
    """
    Async HTTP client for the main Connexio backend.

    Instantiate once at application startup and reuse across requests
    so the in-memory cache is shared and effective.

    Example (in main.py startup):
        app.backend_client = BackendApiClient(
            base_url=settings.MAIN_BACKEND_URL,
            api_key=settings.CONNEXIO_INTERNAL_API_KEY,
            jwt_secret=settings.JWT_SECRET,
        )
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        jwt_secret: Optional[str] = None,
        service_user_id: Optional[int] = None,
        timeout: float = _REQUEST_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._jwt_secret = jwt_secret
        self._service_user_id = service_user_id
        self._timeout = timeout
        self._cache: dict[str, tuple[Any, float]] = {}
        # Persistent client — reuse connections across requests
        self._client = httpx.AsyncClient(timeout=self._timeout)

    async def close(self) -> None:
        """Gracefully close the underlying HTTP client. Call during app shutdown."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_service_token(self) -> Optional[str]:
        """Generate a short-lived service JWT for outbound backend calls."""
        if not self._jwt_secret:
            return None
        if self._service_user_id is None:
            logger.warning("SERVICE_USER_ID is not configured — skipping service JWT generation")
            return None
        try:
            return jwt.encode(
                {
                    "UID": self._service_user_id,
                    "service": True,
                    "iat": int(time.time()),
                    "exp": int(time.time()) + 300,
                },
                self._jwt_secret,
                algorithm="HS256",
            )
        except Exception as e:
            logger.error("Failed to generate service JWT: %s", e)
            return None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        token = self._make_service_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _get_cached(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() < expiry:
            return value
        del self._cache[key]
        return None

    def _set_cached(self, key: str, value: Any, ttl: float) -> None:
        if ttl > 0:
            self._cache[key] = (value, time.monotonic() + ttl)

    async def _get(
        self,
        path: str,
        cache_key: Optional[str] = None,
        cache_ttl: float = _CACHE_TTL_STABLE,
    ) -> Optional[Any]:
        """
        Execute a GET request against the main backend.
        Returns the parsed JSON body, or None on any error.
        Retries up to _MAX_RETRIES times on network failures.
        """
        if cache_key:
            cached = self._get_cached(cache_key)
            if cached is not None:
                logger.debug("Cache HIT for key: %s", cache_key)
                return cached

        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await self._client.get(url, headers=self._headers())

                if resp.status_code == 200:
                    data = resp.json()
                    if cache_key:
                        self._set_cached(cache_key, data, cache_ttl)
                    return data

                if resp.status_code == 404:
                    logger.warning("Main backend 404 for %s", url)
                    return None

                logger.warning(
                    "Main backend returned %s for %s — body: %s (attempt %d/%d)",
                    resp.status_code, url, resp.text[:300], attempt + 1, _MAX_RETRIES + 1,
                )
                return None  # Non-retriable HTTP error

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    wait = 0.5 * (attempt + 1)
                    logger.warning(
                        "Network error calling %s (attempt %d/%d), retrying in %.1fs: %s",
                        url, attempt + 1, _MAX_RETRIES + 1, wait, exc,
                    )
                    await asyncio.sleep(wait)

        logger.error(
            "All %d attempts failed for %s: %s",
            _MAX_RETRIES + 1, url, last_error,
        )
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_user(self, user_id: int) -> Optional[dict]:
        """
        Fetch a user's full profile from the main backend.
        """
        return await self._get(
            f"/api/users/{user_id}",
            cache_key=f"user:{user_id}",
            cache_ttl=_CACHE_TTL_STABLE,
        )

    async def get_project(self, project_id: int) -> Optional[dict]:
        """
        Fetch project details from the main backend.
        """
        return await self._get(
            f"/api/projects/{project_id}",
            cache_key=f"project:{project_id}",
            cache_ttl=_CACHE_TTL_STABLE,
        )

    async def get_project_members(self, project_id: int) -> Optional[list]:
        """
        Fetch all members of a project with their skills.
        """
        return await self._get(
            f"/api/projects/{project_id}/members",
            cache_key=f"members:{project_id}",
            cache_ttl=_CACHE_TTL_STABLE,
        )

    async def get_project_tasks(self, project_id: int) -> Optional[list]:
        """
        Fetch all tasks for a project. NOT cached (task status changes frequently).
        """
        return await self._get(
            f"/api/tasks/project/{project_id}",
            cache_key=None,
            cache_ttl=_CACHE_TTL_VOLATILE,
        )

    async def get_rich_context(
        self, user_id: int, project_id: int
    ) -> dict[str, Any]:
        """
        Fetch user profile, project details, members, and tasks in parallel.
        """
        user, project, members, tasks = await asyncio.gather(
            self.get_user(user_id),
            self.get_project(project_id),
            self.get_project_members(project_id),
            self.get_project_tasks(project_id),
            return_exceptions=False,
        )
        return {
            "user": user,
            "project": project,
            "members": members,
            "tasks": tasks,
        }

    def invalidate_project_cache(self, project_id: int) -> None:
        """Manually evict all cached entries for a given project."""
        for key in [f"project:{project_id}", f"members:{project_id}"]:
            self._cache.pop(key, None)

    def invalidate_user_cache(self, user_id: int) -> None:
        """Manually evict cached user profile."""
        self._cache.pop(f"user:{user_id}", None)