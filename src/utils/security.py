"""
Security utilities for the Connexios RAG API.

All RAG endpoints are called exclusively by the main Connexio backend
(service-to-service). The main backend validates the user's JWT token,
then forwards requests to the RAG with a shared `X-API-Key` header.

Never trust `user_id` from the request body without a valid API key.
"""
import logging
from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)


async def verify_api_key(x_api_key: str = Header(None, alias="x-api-key")) -> str:
    """
    FastAPI dependency that validates the X-API-Key header on every request.

    Usage — apply to an entire router:
        router = APIRouter(dependencies=[Depends(verify_api_key)])

    The main Connexio backend must include in every RAG request:
        X-API-Key: <CONNEXIO_INTERNAL_API_KEY value>

    Dev mode: if CONNEXIO_INTERNAL_API_KEY is not set in .env, validation
    is skipped so local development works without extra config. Set it in
    any shared or production environment.
    """
    # Import here to avoid circular dependency at module load time
    from helpers.config import get_settings
    settings = get_settings()
    expected_key = settings.CONNEXIO_INTERNAL_API_KEY

    # Dev-mode bypass: if the key is not configured, skip validation
    if not expected_key:
        logger.warning(
            "CONNEXIO_INTERNAL_API_KEY is not set — API key validation is DISABLED. "
            "Set this variable before deploying to any shared environment."
        )
        return x_api_key or ""

    if not x_api_key or x_api_key != expected_key:
        logger.warning(
            "Rejected request: invalid or missing X-API-Key header."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "signal": "UNAUTHORIZED",
                "error": (
                    "Missing or invalid X-API-Key. "
                    "All RAG requests must originate from the main Connexio backend."
                ),
            },
        )

    return x_api_key
