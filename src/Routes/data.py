from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
import os
import asyncio
from helpers.config import get_settings, Settings
from controllers import DataController, ProjectController, ProcessController
import aiofiles
from models import ResponseSignal
import logging
from .schemas.data import ProcessRequest
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
from models.AssetModel import AssetModel
from models.db_schemas import DataChunk, Asset
from models.enums.AssetTypeEnum import AssetTypeEnum
from controllers import NLPController
from tasks.file_processing import process_project_files
from tasks.process_workflow import process_and_push_workflow
from utils.security import verify_api_key
from sqlalchemy.future import select

logger = logging.getLogger('uvicorn.error')


async def _background_index(
    db_client, generation_client, embedding_client, vectordb_client, template_parser,
    project_id: int, asset_id: int, file_id: str,
    chunk_size: int, overlap_size: int, do_reset: int
):
    """Fire-and-forget: chunk a file, persist to PostgreSQL, then index into vector DB."""
    try:
        logger.info(f"[background_index] Starting: project={project_id}, asset={asset_id}")

        project_model = await ProjectModel.create_instance(db_client=db_client)
        project = await project_model.get_project_or_create_one(project_id=project_id)

        process_controller = ProcessController(project_id=project_id)
        chunk_model = await ChunkModel.create_instance(db_client=db_client)
        nlp_controller = NLPController(
            vectordb_client=vectordb_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser,
        )

        if do_reset == 1:
            collection_name = nlp_controller.create_collection_name(project_id=project.project_id)
            await vectordb_client.delete_collection(collection_name=collection_name)
            await chunk_model.delete_chunks_by_project_id(project_id=project.project_id)

        try:
            file_content = process_controller.get_file_content(file_id=file_id)
        except Exception as e:
            logger.error(f"[background_index] Cannot read file {file_id}: {e}")
            return

        file_chunks = process_controller.process_file_content(
            file_content=file_content,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
        )

        if not file_chunks:
            logger.warning(f"[background_index] No chunks from file {file_id}")
            return

        chunk_records = [
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i + 1,
                chunk_project_id=project.project_id,
                chunk_asset_id=asset_id,
            )
            for i, chunk in enumerate(file_chunks)
        ]
        await chunk_model.insert_many_chunks(chunks=chunk_records)

        # Query back the saved chunks by asset_id to get DB-assigned IDs for vector indexing
        async with db_client() as session:
            result = await session.execute(
                select(DataChunk).where(DataChunk.chunk_asset_id == asset_id)
            )
            saved_chunks = result.scalars().all()

        if not saved_chunks:
            logger.error(f"[background_index] No saved chunks found for asset={asset_id}")
            return

        collection_name = nlp_controller.create_collection_name(project_id=project.project_id)
        await vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=embedding_client.embedding_size,
            do_reset=False,
        )
        chunks_ids = [c.chunk_id for c in saved_chunks]
        await nlp_controller.index_into_vector_db(
            project=project,
            chunks=saved_chunks,
            chunks_ids=chunks_ids,
        )

        logger.info(f"[background_index] Done: project={project_id}, indexed={len(saved_chunks)} chunks")
    except Exception as e:
        logger.error(f"[background_index] Failed: project={project_id}, error={e}")


data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
    # Document upload and processing endpoints are called by the main backend
    # or by an authorized admin — never by an unauthenticated user directly.
    dependencies=[Depends(verify_api_key)],
)

@data_router.post("/upload/{project_id}")
async def Upload_data(request: Request, project_id : int, file: UploadFile,
                      app_settings: Settings = Depends(get_settings)):

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    
    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )
    
    data_controller = DataController()

    is_valid, result_signal =  data_controller.validate_uploaded_file(file=file)


    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": result_signal
            }
        )
    
    project_dir_path = ProjectController().get_project_path(project_id=project_id)

    file_path, file_id = data_controller.generate_unique_filepath(
        orig_file_name=file.filename,
        project_id=project_id
    )

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:

        logger.error(f"Error while uploading file: {e}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.FILE_UPLOAD_FAILED.value
            }
        )

    # store the assets into the database
    asset_model = await AssetModel.create_instance(
        db_client=request.app.db_client
    )

    asset_resource = Asset(
        asset_project_id=project.project_id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_name=file_id,
        asset_size=os.path.getsize(file_path)
    )

    asset_record = await asset_model.create_asset(asset=asset_resource)


    return JSONResponse(
            content={
                "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
                "file_id": str(asset_record.asset_id)
                # "project_id": str(project._id)   #this is not needed for the user
            }
        )    

@data_router.post("/process/{project_id}")
async def process_endpoint(request: Request, project_id: int, process_request: ProcessRequest):
    try:
        task = process_project_files.delay(
            project_id=project_id,
            file_id=process_request.file_id,
            chunk_size=process_request.chunk_size,
            overlap_size=process_request.overlap_size,
            do_reset=process_request.do_reset
        )
        logger.info(f"Dispatched file processing background task for project {project_id} with task id: {task.id}")
        return JSONResponse(
            content={
                "signal": ResponseSignal.PROCESSING_SUCCESS.value,
                "task_id": task.id
            }
        )
    except Exception as e:
        logger.warning(f"[Celery] Could not dispatch processing task: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"signal": "CELERY_UNAVAILABLE", "detail": "Background task queue is not available."}
        )

@data_router.post("/process-and-push/{project_id}")
async def process_and_push_endpoint(request: Request, project_id: int, process_request: ProcessRequest):
    try:
        workflow_task = process_and_push_workflow.delay(
            project_id=project_id,
            file_id=process_request.file_id,
            chunk_size=process_request.chunk_size,
            overlap_size=process_request.overlap_size,
            do_reset=process_request.do_reset,
        )
        return JSONResponse(
            content={
                "signal": ResponseSignal.PROCESS_AND_PUSH_WORKFLOW_READY.value,
                "workflow_task_id": workflow_task.id
            }
        )
    except Exception as e:
        logger.warning(f"[Celery] Could not dispatch process-and-push task: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"signal": "CELERY_UNAVAILABLE", "detail": "Background task queue is not available."}
        )


@data_router.post("/upload-and-process/{project_id}", status_code=status.HTTP_202_ACCEPTED)
async def upload_and_process(
    request: Request,
    project_id: int,
    file: UploadFile,
    chunk_size: int = 100,
    overlap_size: int = 20,
    do_reset: int = 0,
    app_settings: Settings = Depends(get_settings),
):
    """Upload a file and immediately kick off background chunking + vector indexing.
    Returns 202 with the asset ID; indexing completes asynchronously.
    Called by the Node.js backend after a project file upload.
    """
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    data_controller = DataController()
    is_valid, result_signal = data_controller.validate_uploaded_file(file=file)
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": result_signal}
        )

    file_path, file_id = data_controller.generate_unique_filepath(
        orig_file_name=file.filename,
        project_id=project_id,
    )

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:
        logger.error(f"[upload_and_process] Write error: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.FILE_UPLOAD_FAILED.value}
        )

    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    asset_resource = Asset(
        asset_project_id=project.project_id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_name=file_id,
        asset_size=os.path.getsize(file_path),
    )
    asset_record = await asset_model.create_asset(asset=asset_resource)

    asyncio.create_task(
        _background_index(
            db_client=request.app.db_client,
            generation_client=request.app.generation_client,
            embedding_client=request.app.embedding_client,
            vectordb_client=request.app.vectordb_client,
            template_parser=request.app.template_parser,
            project_id=project_id,
            asset_id=asset_record.asset_id,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
            do_reset=do_reset,
        )
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "accepted",
            "file_id": str(asset_record.asset_id),
        },
    )