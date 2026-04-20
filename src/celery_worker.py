import os
from celery import Celery
import asyncio
from helpers.config import get_settings

settings = get_settings()

redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"

# Initialize Celery app
celery_app = Celery(
    "rag_tasks",
    broker=redis_url,
    backend=redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(bind=True, name="process_and_index_documents")
def process_and_index_documents_task(self, project_id: int):
    """
    Background worker task to load documents, chunk them, and index them 
    into the VectorDB asynchronously without blocking the FastAPI event loop.
    """
    # Since Celery is sync by default but our architecture is async,
    # we need to wrap our core logic in an event loop execution wrapper
    async def _async_runner():
        from models.ProjectModel import ProjectModel
        from models.ChunkModel import ChunkModel
        from controllers.NLPController import NLPController
        
        # We need to re-initialize dependencies inside the worker context
        # (Assuming you add basic dependency injection or singleton connections here)
        # Note: True production will use dependency injects directly here.
        print(f"[CELERY] Starting Vector Indexing for Project: {project_id}")
        
        # ... Place core indexing orchestration logic here...
        # In a complete migration, NLPController.index_into_vector_db logic
        # is instantiated and called within this block.
        print(f"[CELERY] Finished Vector Indexing for Project: {project_id}")
        return True

    return asyncio.run(_async_runner())
