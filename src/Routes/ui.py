import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from helpers.config import get_settings
from utils.security import verify_api_key_or_standalone

from .agent import get_nlp_controller
from controllers.NLPController import SHORTCUT_COMMANDS

logger = logging.getLogger(__name__)

ui_router = APIRouter()

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_CHAT_HTML = _STATIC_DIR / "chat.html"

PERSONAS = ["student", "early_career", "educator", "company"]
MODEL_TIERS = ["auto", "utility", "generation"]
LANGUAGES = ["auto", "en", "ar"]

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@ui_router.get("/")
async def playground():
    """Serve the standalone chat playground at the root.

    When STANDALONE_MODE is off this keeps the original JSON status payload so
    existing health checks and uptime monitors are unaffected.
    """
    settings = get_settings()

    if not settings.STANDALONE_MODE:
        return JSONResponse(
            content={
                "status": "Connexios RAG is running",
                "standalone": False,
                "health": "/api/v1/health",
                "docs": "/docs",
            }
        )

    if not _CHAT_HTML.is_file():
        logger.error("Playground HTML missing at %s", _CHAT_HTML)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "playground_assets_missing", "path": str(_CHAT_HTML)},
        )

    return FileResponse(_CHAT_HTML, media_type="text/html; charset=utf-8")


@ui_router.get("/ui/config")
async def ui_config():
    """Expose non-secret playground defaults so the page can populate its controls."""
    settings = get_settings()
    return {
        "standalone": settings.STANDALONE_MODE,
        "user_id": settings.UI_DEFAULT_USER_ID,
        "project_id": settings.UI_DEFAULT_PROJECT_ID,
        "persona": settings.UI_DEFAULT_PERSONA,
        "language": settings.UI_DEFAULT_LANGUAGE,
        "limit": 5,
        "backend_sync": settings.ENABLE_BACKEND_SYNC,
        "masarx_sync": settings.ENABLE_MASARX_SYNC,
        "personas": PERSONAS,
        "model_tiers": MODEL_TIERS,
        "languages": LANGUAGES,
        "slash_commands": sorted(SHORTCUT_COMMANDS),
    }


@ui_router.get(
    "/ui/chat/stream",
    dependencies=[Depends(verify_api_key_or_standalone)],
)
async def ui_chat_stream(
    request: Request,
    query: str,
    user_id: Optional[int] = None,
    project_id: Optional[int] = None,
    persona: Optional[str] = None,
    session_id: Optional[int] = None,
    limit: Optional[int] = 5,
    model_tier: Optional[str] = None,
    language: Optional[str] = None,
    source: Optional[str] = None,
):
    """Stream a chat answer to the playground.

    Calls the controller in-process rather than looping back through the public
    API, so the browser never needs the internal X-API-Key.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"signal": "BAD_REQUEST", "error": "query must not be empty"},
        )

    settings = get_settings()
    effective_project_id = None if project_id == 0 else project_id
    controller = get_nlp_controller(request)

    logger.info(
        "Playground stream user=%s project=%s tier=%s persona=%s",
        user_id if user_id is not None else settings.UI_DEFAULT_USER_ID,
        effective_project_id,
        model_tier or "auto",
        persona or settings.UI_DEFAULT_PERSONA,
    )

    return StreamingResponse(
        controller.answer_agent_chat_stream(
            user_id=settings.UI_DEFAULT_USER_ID if user_id is None else user_id,
            project_id=effective_project_id,
            query=cleaned,
            persona=persona or settings.UI_DEFAULT_PERSONA,
            session_id=session_id,
            limit=5 if limit is None else max(1, min(int(limit), 25)),
            model_tier=model_tier or "auto",
            language=language,
            source=source or "playground",
            max_output_tokens=settings.PLAYGROUND_MAX_OUTPUT_TOKENS,
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@ui_router.post(
    "/ui/session/new",
    dependencies=[Depends(verify_api_key_or_standalone)],
)
async def ui_new_session(request: Request, payload: Optional[dict] = Body(None)):
    """Start a fresh chat session so the playground can reset its history."""
    settings = get_settings()
    body = payload or {}

    try:
        user_id = int(body.get("user_id") or settings.UI_DEFAULT_USER_ID)
    except (TypeError, ValueError):
        user_id = settings.UI_DEFAULT_USER_ID

    try:
        raw_project = int(body.get("project_id") or settings.UI_DEFAULT_PROJECT_ID)
    except (TypeError, ValueError):
        raw_project = settings.UI_DEFAULT_PROJECT_ID

    language = body.get("language") or "en"
    if language == "auto":
        language = "en"

    controller = get_nlp_controller(request)
    record = await controller.session_model.create_session(
        user_id=user_id,
        project_id=None if raw_project == 0 else raw_project,
        persona=body.get("persona") or settings.UI_DEFAULT_PERSONA,
        language=language,
    )

    logger.info("Playground new session id=%s user=%s", record.session_id, user_id)
    return {"session_id": record.session_id}