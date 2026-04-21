from fastapi import APIRouter, status, Request
from typing import Optional
from fastapi.responses import JSONResponse, StreamingResponse
from .schemas.agent import (
    AgentChatRequest, PortfolioRequest, DocGenRequest, 
    TaskArchitectRequest
)
from controllers import NLPController
from models import ResponseSignal
import logging

logger = logging.getLogger('uvicorn.error')

agent_router = APIRouter(
    prefix="/api/v1/nlp/agent",
    tags=["api_v1", "agent"],
)

def get_nlp_controller(request: Request):
    return NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
        settings=getattr(request.app, 'settings', None),
        db_client=getattr(request.app, 'db_client', None),
        reranker=getattr(request.app, 'reranker', None)
    )

@agent_router.post("/chat/{project_id}")
async def agent_chat(request: Request, project_id: int, chat_request: AgentChatRequest):
    try:
        nlp_controller = get_nlp_controller(request)
        result = await nlp_controller.answer_agent_chat(
            user_id=chat_request.user_id,
            project_id=project_id,
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
        return StreamingResponse(
            nlp_controller.answer_agent_chat_stream(
                user_id=user_id,
                project_id=project_id,
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

@agent_router.post("/portfolio/{project_id}")
async def generate_portfolio(request: Request, project_id: int, port_request: PortfolioRequest):
    try:
        nlp_controller = get_nlp_controller(request)
        portfolio = await nlp_controller.get_user_portfolio(user_id=port_request.user_id)
        return JSONResponse(
            content={
                "signal": ResponseSignal.AGENT_PORTFOLIO_SUCCESS.value,
                "portfolio": portfolio
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.AGENT_PORTFOLIO_ERROR.value}
        )

@agent_router.get("/supervisor/risks/{project_id}")
async def supervisor_risks(request: Request, project_id: int, supervisor_id: Optional[int] = None):
    try:
        nlp_controller = get_nlp_controller(request)
        risks = await nlp_controller.get_supervisor_risks(project_id=project_id)
        return JSONResponse(
            content={
                "signal": ResponseSignal.AGENT_SUPERVISOR_SUCCESS.value,
                "risks": risks
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.AGENT_SUPERVISOR_ERROR.value}
        )

@agent_router.get("/coach/path/{project_id}")
async def coach_path(request: Request, project_id: int, user_id: int):
    try:
        nlp_controller = get_nlp_controller(request)
        path = await nlp_controller.get_coach_path(user_id=user_id, project_id=project_id)
        return JSONResponse(
            content={
                "signal": ResponseSignal.AGENT_COACH_SUCCESS.value,
                "recommendations": path
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.AGENT_COACH_ERROR.value}
        )

@agent_router.post("/doc-gen/{project_id}")
async def document_generation(request: Request, project_id: int, doc_request: DocGenRequest):
    try:
        nlp_controller = get_nlp_controller(request)
        docs = await nlp_controller.get_doc_gen(
            project_id=project_id, 
            doc_type=doc_request.doc_type
        )
        return JSONResponse(
            content={
                "signal": ResponseSignal.AGENT_DOCGEN_SUCCESS.value,
                "document": docs
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.AGENT_DOCGEN_ERROR.value}
        )

@agent_router.post("/task-architect/plan/{project_id}")
async def task_architect_plan(request: Request, project_id: int, task_request: TaskArchitectRequest):
    try:
        nlp_controller = get_nlp_controller(request)
        plan = await nlp_controller.get_task_architect_plan(
            query=task_request.query,
            user_id=task_request.user_id,
            project_id=project_id
        )
        return JSONResponse(
            content={
                "signal": ResponseSignal.AGENT_ARCHITECT_SUCCESS.value,
                "plan": plan
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.AGENT_ARCHITECT_ERROR.value}
        )
