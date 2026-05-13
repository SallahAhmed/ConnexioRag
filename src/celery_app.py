import logging as _logging
import ssl as _ssl
_celery_logger = _logging.getLogger("uvicorn.error")

try:
    from celery import Celery
except ImportError:
    Celery = None  # type: ignore

from helpers.config import get_settings

from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from stores.llm.templates.template_parser import TemplateParser
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

settings = get_settings()

async def get_setup_utils():
    settings = get_settings()

    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"

    db_engine = create_async_engine(postgres_conn, connect_args={"ssl": True})
    db_client = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    llm_provider_factory = LLMProviderFactory(settings)
    vectordb_provider_factory = VectorDBProviderFactory(config=settings, db_client=db_client)

    # generation client
    generation_client = llm_provider_factory.create(
        provider=settings.GENERATION_BACKEND,
        api_url=settings.OPENAI_GENERATION_API_URL
    )
    generation_client.set_generation_model(model_id = settings.GENERATION_MODEL_ID)

    # utility client
    utility_client = llm_provider_factory.create(
        provider=settings.GENERATION_BACKEND,
        api_url=settings.OPENAI_GENERATION_API_URL
    )
    utility_client.set_generation_model(model_id=settings.UTILITY_MODEL_ID)

    # embedding client
    embedding_client = llm_provider_factory.create(
        provider=settings.EMBEDDING_BACKEND,
        api_url=settings.OPENAI_EMBEDDING_API_URL
    )
    embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID,
                                             embedding_size=settings.EMBEDDING_MODEL_SIZE)
    
    # vector db client
    vectordb_client = vectordb_provider_factory.create(
        provider=settings.VECTOR_DB_BACKEND
    )
    await vectordb_client.connect()

    template_parser = TemplateParser(
        language=settings.PRIMARY_LANG,
        default_language=settings.DEFAULT_LANG,
    )

    return (db_engine, db_client, llm_provider_factory, vectordb_provider_factory,
            generation_client, utility_client, embedding_client, vectordb_client, template_parser)

try:
    celery_app = Celery(
        "connexio",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            "tasks.file_processing",
            "tasks.data_indexing",
            "tasks.process_workflow",
            "tasks.maintenance"
        ]
    )
except Exception as _e:
    _celery_logger.warning(f"[Celery] Failed to initialize Celery app: {_e}. Background tasks disabled.")
    celery_app = None  # type: ignore

if celery_app is not None:
    _ssl_opts = {"ssl_cert_reqs": _ssl.CERT_NONE}
    celery_app.conf.update(
    broker_use_ssl=_ssl_opts,
    redis_backend_use_ssl=_ssl_opts,
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=[
        settings.CELERY_TASK_SERIALIZER
    ],

    # Task safety - Late acknowledgment prevents task loss on worker crash
    task_acks_late=settings.CELERY_TASK_ACKS_LATE,

    # Time limits - Prevent hanging tasks
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,

    # Result backend - Store results for status tracking
    task_ignore_result=False,
    result_expires=3600,

    # Worker settings
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    worker_prefetch_multiplier=1,

    # Connection settings for better reliability
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_heartbeat=None, # Disable heartbeats to prevent timeouts during long blocking tasks
    worker_cancel_long_running_tasks_on_connection_loss=True,

    # Enable remote control but disable events to save Redis commands (not needed without Flower)
    worker_enable_remote_control=True,
    worker_send_task_events=False,

    # Upstash/Redis optimization: increase polling interval to reduce 'GET' commands
    broker_transport_options={
        'visibility_timeout': 3600,
        'polling_interval': 20.0, # Check for tasks every 20 seconds (Sweet spot for free tier)
    },

    task_routes={
        "tasks.file_processing.process_project_files": {"queue": "file_processing"},
        "tasks.data_indexing.index_data_content": {"queue": "data_indexing"},
        "tasks.process_workflow.process_and_push_workflow": {"queue": "file_processing"},
        "tasks.maintenance.clean_celery_executions_table": {"queue": "default"},
     },

    beat_schedule={
        'cleanup-old-task-records': {
            'task': "tasks.maintenance.clean_celery_executions_table",
            'schedule': 86400, #1 day
            'args': ()
        }
    },

    timezone='UTC',
)

    celery_app.conf.task_default_queue = "default"