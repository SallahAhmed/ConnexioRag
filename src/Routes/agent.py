from fastapi import APIRouter, status, Request, Depends
from typing import Optional
from fastapi.responses import JSONResponse, StreamingResponse
from .schemas.agent import (
    AgentChatRequest
)
from controllers import NLPController
from models import ResponseSignal
from utils.security import verify_api_key
import logging

logger = logging.getLogger('uvicorn.error')

agent_router = APIRouter(
    prefix="/api/v1/nlp/agent",
    tags=["api_v1", "agent"],
    # Every route in this router requires a valid X-API-Key header.
    # The main Connexio backend adds this header when proxying user requests.
    dependencies=[Depends(verify_api_key)],
)

def get_nlp_controller(request: Request) -> NLPController:
    return NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        utility_client=request.app.utility_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
        settings=getattr(request.app, 'settings', None),
        db_client=getattr(request.app, 'db_client', None),
        reranker=getattr(request.app, 'reranker', None),
        # Single BackendApiClient instance created at startup — shared across
        # requests so its in-memory cache is effective.
        backend_client=getattr(request.app, 'backend_client', None),
    )

@agent_router.post("/chat/{project_id}")
async def agent_chat(request: Request, project_id: int, chat_request: AgentChatRequest):
    try:
        nlp_controller = get_nlp_controller(request)
        # project_id=0 is the convention for individual (no-project) chatbot rooms
        effective_project_id = None if project_id == 0 else project_id
        result = await nlp_controller.answer_agent_chat(
            user_id=chat_request.user_id,
            project_id=effective_project_id,
            query=chat_request.query,
            persona=chat_request.persona,
            session_id=chat_request.session_id,
            limit=chat_request.limit
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
async def agent_chat_stream(request: Request, project_id: int,
                            query: str, user_id: int,
                            persona: Optional[str] = "student",
                            session_id: Optional[int] = None,
                            limit: Optional[int] = 5):
    try:
        nlp_controller = get_nlp_controller(request)
        effective_project_id = None if project_id == 0 else project_id
        return StreamingResponse(
            nlp_controller.answer_agent_chat_stream(
                user_id=user_id,
                project_id=effective_project_id,
                query=query,
                persona=persona,
                session_id=session_id,
                limit=limit
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Agent Chat Stream Error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.AGENT_CHAT_ERROR.value, "error": str(e)}
        )




