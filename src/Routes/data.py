from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request, Form
from fastapi.responses import JSONResponse
import os
import asyncio
from typing import Optional
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


async def _process_and_index(
    db_client, generation_client, embedding_client, vectordb_client, template_parser,
    project_id: int, asset_id: int, file_id: str,
    chunk_size: int, overlap_size: int, do_reset: int = 0
) -> int:
    """Process a file into chunks, persist to PostgreSQL, then index into vector DB.
    Returns the number of chunks indexed. This is the synchronous (awaited) version.
    """
    try:
        logger.info(f"[_process_and_index] Starting: project={project_id}, asset={asset_id}")

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
            logger.error(f"[_process_and_index] Cannot read file {file_id}: {e}")
            return 0

        file_chunks = process_controller.process_file_content(
            file_content=file_content,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
        )

        if not file_chunks:
            logger.warning(f"[_process_and_index] No chunks from file {file_id}")
            return 0

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
            logger.error(f"[_process_and_index] No saved chunks found for asset={asset_id}")
            return 0

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

        logger.info(f"[_process_and_index] Done: project={project_id}, indexed={len(saved_chunks)} chunks")
        return len(saved_chunks)
    except Exception as e:
        logger.error(f"[_process_and_index] Failed: project={project_id}, error={e}")
        return 0


async def _background_index(
    db_client, generation_client, embedding_client, vectordb_client, template_parser,
    project_id: int, asset_id: int, file_id: str,
    chunk_size: int, overlap_size: int, do_reset: int
):
    """Fire-and-forget wrapper around _process_and_index."""
    await _process_and_index(
        db_client, generation_client, embedding_client, vectordb_client, template_parser,
        project_id, asset_id, file_id, chunk_size, overlap_size, do_reset,
    )


data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
    # Document upload and processing endpoints are called by the main backend
    # or by an authorized admin — never by an unauthenticated user directly.
    dependencies=[Depends(verify_api_key)],
)

@data_router.post("/upload/{project_id}")
async def upload_data(request: Request, project_id : int, file: UploadFile,
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


@data_router.post("/upload-and-query/{project_id}")
async def upload_and_query(
    request: Request,
    project_id: int,
    file: UploadFile,
    query: str = Form(..., min_length=1, max_length=5000),
    user_id: int = Form(...),
    persona: str = Form("student"),
    session_id: Optional[int] = Form(None),
    limit: int = Form(5),
    model_tier: str = Form("auto"),
    language: Optional[str] = Form(None),
    chunk_size: int = Form(100),
    overlap_size: int = Form(20),
    app_settings: Settings = Depends(get_settings),
):
    """Upload a file, index it into the knowledge base, and immediately answer a
    question about its content — all in a single request.

    This endpoint replaces the fire-and-forget pattern with a synchronous
    flow: ingest → embed → search → generate, so the caller gets a meaningful
    answer instead of just a "file received" acknowledgment.
    """
    logger.info(
        f"[UPLOAD-QUERY] ▶ received file='{file.filename}' type='{file.content_type}' "
        f"project={project_id} user={user_id} query='{query[:60]}'"
    )

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    # 1. Validate file
    data_controller = DataController()
    is_valid, result_signal = data_controller.validate_uploaded_file(file=file)
    if not is_valid:
        logger.warning(
            f"[UPLOAD-QUERY] ✗ REJECTED file='{file.filename}' type='{file.content_type}' "
            f"signal={result_signal} — check FILE_ALLOWED_TYPES in .env"
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": result_signal},
        )
    logger.info(f"[UPLOAD-QUERY] ✓ validation OK: {file.filename}")

    # 2. Save file to disk
    file_path, file_id = data_controller.generate_unique_filepath(
        orig_file_name=file.filename,
        project_id=project_id,
    )
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:
        logger.error(f"[upload_and_query] Write error: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.FILE_UPLOAD_FAILED.value},
        )

    # 3. Create asset record
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    asset_resource = Asset(
        asset_project_id=project.project_id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_name=file_id,
        asset_size=os.path.getsize(file_path),
    )
    asset_record = await asset_model.create_asset(asset=asset_resource)
    logger.info(
        f"[UPLOAD-QUERY] ✓ saved to disk + asset created: asset_id={asset_record.asset_id} "
        f"name={file_id} size={os.path.getsize(file_path)}B"
    )

    # 4. Read only an excerpt for the immediate answer. Parsing the whole file
    #    here (e.g. an 8 MB PDF) just to keep the first 8000 chars was the main
    #    cause of the request blocking past the caller's timeout — get_file_excerpt
    #    reads lazily (page-by-page) and stops early.
    process_controller = ProcessController(project_id=project_id)
    try:
        excerpt = process_controller.get_file_excerpt(file_id=file_id, max_chars=8000)
        extra_context = f"[Uploaded Document '{file.filename}']:\n{excerpt}"
        logger.info(f"[UPLOAD-QUERY] ✓ excerpt read for immediate answer: {len(excerpt)} chars")
    except Exception as e:
        logger.warning(f"[UPLOAD-QUERY] ✗ could not read file content: {e}")
        extra_context = None

    # 5. Offload full indexing (parse + chunk + embed) to a Celery worker so it
    #    never blocks this web event loop. Reuses the same workflow the
    #    fire-and-forget /upload-and-process endpoint uses; file_id here is the
    #    on-disk asset name the task looks up. Falls back to the in-process task
    #    only if dispatch fails (e.g. broker unreachable).
    try:
        workflow_res = process_and_push_workflow.delay(
            project_id, file_id, chunk_size, overlap_size, 0
        )
        logger.info(
            f"[UPLOAD-QUERY] ✓ indexing dispatched to Celery: task_id={workflow_res.id} "
            f"— watch the celery WORKER logs for [INDEX] (parse/chunk) and [EMBED] (vector DB)"
        )
    except Exception as e:
        logger.warning(f"[UPLOAD-QUERY] ✗ Celery dispatch failed, indexing inline instead: {e}")
        asyncio.create_task(
            _process_and_index(
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
            )
        )

    # 6. Answer the user's question using the file content as direct context
    chat_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        utility_client=request.app.utility_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
        settings=getattr(request.app, "settings", None),
        db_client=getattr(request.app, "db_client", None),
        reranker=getattr(request.app, "reranker", None),
        backend_client=getattr(request.app, "backend_client", None),
        masarx_client=getattr(request.app, "masarx_client", None),
    )
    try:
        result = await chat_controller.answer_agent_chat(
            user_id=user_id,
            project_id=project_id,
            query=query,
            persona=persona,
            session_id=session_id,
            limit=limit,
            model_tier="generation",  # skip utility model — go straight to 70B
            language=language,
            extra_context=extra_context,
        )
    except Exception as e:
        logger.error(f"[upload_and_query] Chat failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "chat_failed",
                "file_id": str(asset_record.asset_id),
                "error": "An internal error occurred while generating a response.",
            },
        )

    _ans = result.get("answer", "") if isinstance(result, dict) else ""
    _srcs = result.get("sources", []) if isinstance(result, dict) else []
    logger.info(
        f"[UPLOAD-QUERY] ✓ answer generated: {len(str(_ans))} chars, {len(_srcs)} source(s) "
        f"— indexing continues in background"
    )

    # 7. Return the answer (indexing continues in background)
    return JSONResponse(
        content={
            "status": "completed",
            "file_id": str(asset_record.asset_id),
            "chunks_indexed": "background",
            **result,
        }
    )


@data_router.get("/assets/{project_id}")
async def get_project_assets(request: Request, project_id: int):
    """List all indexed files for a project (called by the Node.js backend)."""
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    assets = await asset_model.get_all_project_assets(
        asset_project_id=project_id,
        asset_type=AssetTypeEnum.FILE.value,
    )
    return {
        "success": True,
        "assets": [
            {
                "asset_id": a.asset_id,
                "asset_name": a.asset_name,
                "asset_size": a.asset_size,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assets
        ],
    }


@data_router.delete("/assets/{asset_id}")
async def delete_project_asset(request: Request, asset_id: int):
    """
    Fully remove an asset: delete its SQL record, chunks, physical file,
    and the corresponding PGVector rows.
    Called by the Node.js backend after the team leader triggers deletion.
    """
    from sqlalchemy.sql import text as sql_text

    db_client = request.app.db_client
    asset_model = await AssetModel.create_instance(db_client=db_client)
    chunk_model = await ChunkModel.create_instance(db_client=db_client)

    # 1. Fetch asset details
    async with db_client() as session:
        result = await session.execute(
            select(Asset).where(Asset.asset_id == asset_id)
        )
        asset = result.scalar_one_or_none()

    if not asset:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Asset not found"},
        )

    project_id = asset.asset_project_id
    file_id = asset.asset_name

    # 2. Get associated chunk IDs
    chunks = await chunk_model.get_chunks_by_asset_id(asset_id=asset_id)
    chunk_ids = [c.chunk_id for c in chunks]

    # 3. Remove matching rows from the dynamic PGVector collection table
    if chunk_ids:
        nlp_controller = NLPController(
            vectordb_client=request.app.vectordb_client,
            generation_client=request.app.generation_client,
            embedding_client=request.app.embedding_client,
            template_parser=request.app.template_parser,
        )
        collection_name = nlp_controller.create_collection_name(project_id=project_id)
        if await request.app.vectordb_client.is_collection_existed(collection_name):
            try:
                async with db_client() as session:
                    async with session.begin():
                        # Validate collection_name to prevent SQL injection:
                        # it must match the pattern collection_{size}_{pid}
                        import re as _re
                        if not _re.fullmatch(r'collection_\d+_\d+', collection_name):
                            raise ValueError(f"Invalid collection name: {collection_name}")
                        await session.execute(
                            sql_text(
                                f'DELETE FROM "{collection_name}" WHERE chunk_id = ANY(:ids)'
                            ),
                            {"ids": chunk_ids},
                        )
            except Exception as q_err:
                logger.error(f"[RAG] Failed to delete PGVector rows: {q_err}")

    # 4. Remove the physical file from disk
    project_path = ProjectController().get_project_path(project_id=project_id)
    file_path = os.path.join(project_path, file_id)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as f_err:
            logger.error(f"[RAG] Physical file removal failed: {f_err}")

    # 5. Drop SQL chunk records then asset record
    await chunk_model.delete_chunks_by_asset_id(asset_id=asset_id)
    await asset_model.delete_asset_by_id(asset_id=asset_id)

    return {"success": True, "message": "Asset and vectors deleted successfully"}