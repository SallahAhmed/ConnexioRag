# --- Framework & Core Imports ---
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from fastapi import Request

# --- Application Routes ---
from Routes import base, data, nlp, agent
from Routes.projects import projects_router

# --- Configuration & Factories ---
from helpers.config import get_settings
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from stores.llm.templates.template_parser import TemplateParser

# --- Models & Utils ---
from models.db_schemas.connexio.schemas import SQLAlchemyBase
from utils.metrics import setup_metrics
from utils.backend_client import BackendApiClient

logger = logging.getLogger(__name__)

# --- Sentry Error Tracking (initialized before app creation) ---
# The [fastapi] extra auto-enables Starlette/FastAPI integrations. No-op if DSN unset.
import sentry_sdk

_sentry_settings = get_settings()
if _sentry_settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=_sentry_settings.SENTRY_DSN,
        environment=_sentry_settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=_sentry_settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
    )
    logger.info("Sentry enabled (env=%s).", _sentry_settings.SENTRY_ENVIRONMENT)

# --- App Initialization ---
app = FastAPI(
    title="Connexios RAG API",
    description=(
        "Agentic RAG system for the Connexio platform. "
        "All endpoints are protected by X-API-Key and must be called "
        "exclusively by the main Connexio backend (service-to-service)."
    ),
    version="1.0.0",
)
setup_metrics(app)

# --- Rate Limiting ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"signal": "RATE_LIMITED", "detail": str(exc)},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.settings = settings

    # --- Database Initialization (Postgres) ---
    postgres_conn = (
        f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    )
    app.db_engine = create_async_engine(
        postgres_conn,
        connect_args={"ssl": True},
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=20,
        max_overflow=10,
    )

    try:
        async with app.db_engine.begin() as conn:
            logger.info("Initializing database tables...")
            await asyncio.wait_for(
                conn.run_sync(SQLAlchemyBase.metadata.create_all),
                timeout=30.0,
            )
            logger.info("Database tables initialized.")
    except Exception as e:
        logger.error("Database initialization failed: %s", e)
        raise RuntimeError(
            f"Cannot start without database: {e}. "
            "Check POSTGRES_* variables and network connectivity."
        ) from e

    app.db_client = sessionmaker(
        app.db_engine, class_=AsyncSession, expire_on_commit=False
    )

    # --- AI & Provider Factories ---
    llm_provider_factory = LLMProviderFactory(settings)
    vectordb_provider_factory = VectorDBProviderFactory(config=settings, db_client=app.db_client)

    # --- Generation & Utility Clients Setup ---
    app.generation_client = llm_provider_factory.create_generation_client()
    app.utility_client = llm_provider_factory.create_utility_client()

    # --- Embedding Client Setup ---
    embedding_api_url = (
        settings.JINA_API_URL
        if settings.EMBEDDING_BACKEND == "OPENAI" and settings.JINA_API_KEY
        else settings.OPENAI_EMBEDDING_API_URL
    )
    app.embedding_client = llm_provider_factory.create(
        provider=settings.EMBEDDING_BACKEND,
        api_url=embedding_api_url,
    )
    app.embedding_client.set_embedding_model(
        model_id=settings.EMBEDDING_MODEL_ID,
        embedding_size=settings.EMBEDDING_MODEL_SIZE,
    )

    # --- Vector DB Client Setup ---
    app.vectordb_client = vectordb_provider_factory.create(
        provider=settings.VECTOR_DB_BACKEND,
    )
    try:
        logger.info("Connecting to Vector Database...")
        await asyncio.wait_for(app.vectordb_client.connect(), timeout=30.0)
        logger.info("Vector Database connected.")
    except Exception as e:
        logger.error("Vector DB connection failed: %s", e)
        raise RuntimeError(f"Cannot start without Vector DB: {e}") from e

    # --- Reranker Setup (Jina Multilingual) ---
    try:
        from stores.vectordb.providers.JinaReranker import JinaReranker
        if getattr(settings, "JINA_API_KEY", None):
            app.reranker = JinaReranker(api_key=settings.JINA_API_KEY)
            logger.info("Jina reranker (jina-reranker-v2-base-multilingual) initialized.")
        else:
            app.reranker = None
            logger.warning("JINA_API_KEY not set — reranking disabled.")
    except Exception as e:
        app.reranker = None
        logger.error("Failed to initialize Jina reranker: %s", e)

    # --- Template Parser Setup ---
    app.template_parser = TemplateParser(
        language=settings.PRIMARY_LANG,
        default_language=settings.DEFAULT_LANG,
    )

    app.backend_client = BackendApiClient(
        base_url=settings.MAIN_BACKEND_URL,
        api_key=settings.CONNEXIO_INTERNAL_API_KEY or "",
        jwt_secret=settings.JWT_SECRET,
        service_user_id=settings.SERVICE_USER_ID,
    )

    from utils.masarx_client import MasarxApiClient
    app.masarx_client = MasarxApiClient(db_client=app.db_client)

    if settings.CONNEXIO_INTERNAL_API_KEY:
        logger.info(
            "X-API-Key authentication enabled. Backend URL: %s",
            settings.MAIN_BACKEND_URL,
        )
    else:
        logger.error(
            "CONNEXIO_INTERNAL_API_KEY is not set — service will reject all requests."
        )

    yield

    # --- Shutdown ---
    if hasattr(app, "backend_client") and app.backend_client:
        await app.backend_client.close()
    await app.db_engine.dispose()
    if hasattr(app, "vectordb_client") and app.vectordb_client:
        await app.vectordb_client.disconnect()


app.router.lifespan_context = lifespan

# --- Include Routers ---
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
app.include_router(agent.agent_router)
app.include_router(projects_router)


# --- UTF-8 Response Middleware ---
# Ensures Arabic and other non-ASCII characters are encoded correctly
# in HTTP responses (prevents mojibake on HF Spaces).
@app.middleware("http")
async def ensure_utf8_response(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


@app.get("/")
async def root():
    return {
        "status": "Connexios RAG is running",
        "health": "healthy",
        "documentation": "/docs",
    }