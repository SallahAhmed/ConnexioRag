"""
Unified HTTP client for the main Connexio backend REST API.

Combines features from both the RAG and MasarX implementations:
- In-memory caching with TTL (from RAG)
- Task sync with retry (from MasarX)
- Health check (from MasarX)
- Service JWT generation (both)

Authentication: short-lived service JWT signed with the shared JWT_SECRET.
Caching: user profiles and project details cached 5 min; tasks are NOT cached.
"""

import asyncio
import logging
import time
from typing import Any, List, Optional

import httpx
import jwt

logger = logging.getLogger(__name__)

_CACHE_TTL_STABLE = 300
_CACHE_TTL_VOLATILE = 0
_REQUEST_TIMEOUT = 10.0
_MAX_RETRIES = 2


class BackendApiClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
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
        self._client = httpx.AsyncClient(timeout=self._timeout)

    async def close(self) -> None:
        await self._client.aclose()

    # -- Internal helpers --

    def _make_service_token(self) -> Optional[str]:
        if not self._jwt_secret:
            return None
        if self._service_user_id is None:
            logger.warning("SERVICE_USER_ID is not configured — skipping service JWT")
            return None
        try:
            return jwt.encode(
                {
                    "UID": self._service_user_id,
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
                    logger.warning("Backend 404 for %s", url)
                    return None

                logger.warning(
                    "Backend returned %s for %s — body: %s (attempt %d/%d)",
                    resp.status_code,
                    url,
                    resp.text[:300],
                    attempt + 1,
                    _MAX_RETRIES + 1,
                )
                return None

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    wait = 0.5 * (attempt + 1)
                    logger.warning(
                        "Network error calling %s (attempt %d/%d), retrying in %.1fs: %s",
                        url,
                        attempt + 1,
                        _MAX_RETRIES + 1,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)

        logger.error(
            "All %d attempts failed for %s: %s",
            _MAX_RETRIES + 1,
            url,
            last_error,
        )
        return None

    async def _post(
        self,
        path: str,
        json_body: Any,
        max_retries: int = 3,
    ) -> bool:
        url = f"{self.base_url}{path}"
        for attempt in range(max_retries):
            try:
                resp = await self._client.post(
                    url, json=json_body, headers=self._headers()
                )
                if resp.status_code in (200, 201):
                    return True
                if attempt < max_retries - 1:
                    wait = 2**attempt
                    logger.warning(
                        "POST %s returned %s, retrying in %ds (attempt %d/%d)",
                        url,
                        resp.status_code,
                        wait,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error("POST %s failed (%s): %s", url, resp.status_code, resp.text)
                    return False
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2**attempt
                    logger.warning(
                        "POST %s network error (attempt %d/%d), retrying in %ds: %s",
                        url,
                        attempt + 1,
                        max_retries,
                        wait,
                        e,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error("POST %s failed after %d attempts: %s", url, max_retries, e)
                    return False
        return False

    # -- Public API --

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get(f"{self.base_url}/health", timeout=5.0)
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Backend health check failed: %s", e)
            return False

    async def get_user(self, user_id: int) -> Optional[dict]:
        return await self._get(
            f"/api/users/{user_id}",
            cache_key=f"user:{user_id}",
            cache_ttl=_CACHE_TTL_STABLE,
        )

    async def get_project(self, project_id: int) -> Optional[dict]:
        return await self._get(
            f"/api/projects/{project_id}",
            cache_key=f"project:{project_id}",
            cache_ttl=_CACHE_TTL_STABLE,
        )

    async def get_project_members(self, project_id: int) -> Optional[list]:
        return await self._get(
            f"/api/projects/{project_id}/members",
            cache_key=f"members:{project_id}",
            cache_ttl=_CACHE_TTL_STABLE,
        )

    async def get_project_tasks(self, project_id: int) -> Optional[list]:
        return await self._get(
            f"/api/tasks/project/{project_id}",
            cache_key=None,
            cache_ttl=_CACHE_TTL_VOLATILE,
        )

    async def get_rich_context(self, user_id: int, project_id: int) -> dict[str, Any]:
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

    async def sync_tasks(self, project_id: int, tasks: List[dict]) -> bool:
        return await self._post(
            "/api/tasks/bulk",
            json_body={"project_id": project_id, "tasks": tasks},
        )

    def invalidate_project_cache(self, project_id: int) -> None:
        for key in [f"project:{project_id}", f"members:{project_id}"]:
            self._cache.pop(key, None)

    def invalidate_user_cache(self, user_id: int) -> None:
        self._cache.pop(f"user:{user_id}", None)
