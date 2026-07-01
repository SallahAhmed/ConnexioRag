from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi import status
from pydantic import BaseModel
from typing import Optional
from utils.security import verify_api_key
from models.db_schemas.connexio.schemas import Project, ProjectIDMap
from sqlalchemy.future import select
import logging

logger = logging.getLogger("uvicorn.error")


class ProjectSyncRequest(BaseModel):
    mysql_pid: int
    name: Optional[str] = None
    description: Optional[str] = None


projects_router = APIRouter(
    prefix="/api/v1/projects",
    tags=["api_v1", "projects"],
    dependencies=[Depends(verify_api_key)],
)


@projects_router.post("/sync", status_code=status.HTTP_200_OK)
async def sync_project(request: Request, body: ProjectSyncRequest):
    """Sync a MySQL project into PostgreSQL so both databases share the same PID.
    Called by the Node.js backend when a project is created.
    Idempotent: safe to call multiple times for the same project.
    """
    try:
        # 1. Get or create the project row using the MySQL PID as the PostgreSQL project_id
        async with request.app.db_client() as session:
            async with session.begin():
                result = await session.execute(
                    select(Project).where(Project.project_id == body.mysql_pid)
                )
                project = result.scalar_one_or_none()
                if project is None:
                    project = Project(project_id=body.mysql_pid, project_name=body.name)
                    session.add(project)
                elif body.name:
                    project.project_name = body.name
            await session.refresh(project)

        pg_pid = project.project_id

        # 2. Upsert into project_id_map
        async with request.app.db_client() as session:
            async with session.begin():
                result = await session.execute(
                    select(ProjectIDMap).where(ProjectIDMap.mysql_pid == body.mysql_pid)
                )
                mapping = result.scalar_one_or_none()
                if mapping is None:
                    mapping = ProjectIDMap(mysql_pid=body.mysql_pid, pg_pid=pg_pid)
                    session.add(mapping)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "synced",
                "mysql_pid": body.mysql_pid,
                "pg_pid": pg_pid,
            },
        )
    except Exception as e:
        logger.error(f"[sync_project] Error syncing project {body.mysql_pid}: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "detail": "An internal error occurred while syncing the project."},
        )
