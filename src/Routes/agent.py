from fastapi import APIRouter, status, Request, Depends
from typing import Optional
from fastapi.responses import JSONResponse, StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from .schemas.agent import (
    AgentChatRequest
)
from controllers import NLPController
from models import ResponseSignal
from utils.security import verify_api_key
import logging

logger = logging.getLogger('uvicorn.error')

limiter = Limiter(key_func=get_remote_address)

agent_router = APIRouter(
    prefix="/api/v1/nlp/agent",
    tags=["api_v1", "agent"],
    # Every route in this router requires a valid X-API-Key header.
    # The main Connexio backend adds this header when proxying user requests.
    dependencies=[Depends(verify_api_key)],
)

def get_nlp_controller(request: Request) -> NLPController:
    # Created once at app startup and reused across requests.
    # Avoids recreating ToolManager (with expensive SQLDatabase init) per request.
    controller = getattr(request.app, '_nlp_controller', None)
    if controller is None:
        controller = NLPController(
            vectordb_client=request.app.vectordb_client,
            generation_client=request.app.generation_client,
            utility_client=request.app.utility_client,
            embedding_client=request.app.embedding_client,
            template_parser=request.app.template_parser,
            settings=getattr(request.app, 'settings', None),
            db_client=getattr(request.app, 'db_client', None),
            reranker=getattr(request.app, 'reranker', None),
            backend_client=getattr(request.app, 'backend_client', None),
            masarx_client=getattr(request.app, 'masarx_client', None),
        )
        request.app._nlp_controller = controller
    return controller

def resolve_pid(project_id: int, request: Request) -> Optional[int]:
    """Resolve effective project ID with override via ?pid= or ?PID= query param."""
    for key in ("PID", "pid"):
        override = request.query_params.get(key)
        if override and override.isdigit() and int(override) > 0:
            return int(override)
    return None if project_id == 0 else project_id

@agent_router.post("/chat/{project_id}")
@limiter.limit("30/minute")
async def agent_chat(request: Request, project_id: int, chat_request: AgentChatRequest):
    try:
        nlp_controller = get_nlp_controller(request)
        effective_project_id = resolve_pid(project_id, request)
        result = await nlp_controller.answer_agent_chat(
            user_id=chat_request.user_id,
            project_id=effective_project_id,
            query=chat_request.query,
            persona=chat_request.persona,
            session_id=chat_request.session_id,
            limit=chat_request.limit,
            model_tier=chat_request.model_tier or "auto",
            language=chat_request.language,
        )
        return JSONResponse(
            content={
                "signal": ResponseSignal.AGENT_CHAT_SUCCESS.value,
                **result
            }
        )
    except Exception as e:
        logger.error(f"Agent Chat Error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.AGENT_CHAT_ERROR.value, "error": str(e)}
        )

@agent_router.get("/chat/stream/{project_id}")
@limiter.limit("30/minute")
async def agent_chat_stream(request: Request, project_id: int,
                            query: str, user_id: int,
                            persona: Optional[str] = "student",
                            session_id: Optional[int] = None,
                            limit: Optional[int] = 5,
                            model_tier: Optional[str] = "auto",
                            language: Optional[str] = None,
                            source: Optional[str] = None):
    try:
        nlp_controller = get_nlp_controller(request)
        effective_project_id = resolve_pid(project_id, request)
        return StreamingResponse(
            nlp_controller.answer_agent_chat_stream(
                user_id=user_id,
                project_id=effective_project_id,
                query=query,
                persona=persona,
                session_id=session_id,
                limit=limit,
                model_tier=model_tier,
                language=language,
                source=source,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    except Exception as e:
        logger.error(f"Agent Chat Stream Error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.AGENT_CHAT_ERROR.value, "error": str(e)}
        )