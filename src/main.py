# --- Framework & Core Imports ---
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio

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

async def startup_span():
    settings = get_settings()
    app.settings = settings

    # --- Database Initialization (Postgres) ---
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    app.db_engine = create_async_engine(
        postgres_conn, 
        connect_args={"ssl": True},
        pool_pre_ping=True,
        pool_recycle=300
    )
    
    # Ensure tables are created (with a safety timeout to prevent hanging the whole server)
    try:
        async with app.db_engine.begin() as conn:
            print("[AGENT] Initializing database tables...")
            await asyncio.wait_for(
                conn.run_sync(SQLAlchemyBase.metadata.create_all), 
                timeout=30.0
            )
            print("[AGENT] Database tables initialized or already exist.")
    except Exception as e:
        print(f"[AGENT] Skipping database auto-initialization: {str(e)}")
        print(
            "[AGENT] (The server will still start, but some database features might fail until fixed)."
        )

    app.db_client = sessionmaker(
        app.db_engine, class_=AsyncSession, expire_on_commit=False
    )

    # --- AI & Provider Factories ---
    llm_provider_factory = LLMProviderFactory(settings)
    vectordb_provider_factory = VectorDBProviderFactory(config=settings, db_client=app.db_client)

    # --- Generation Client Setup ---
    gen_url = settings.GROQ_API_URL if settings.GENERATION_BACKEND == "GROQ" else settings.OPENAI_GENERATION_API_URL
    app.generation_client = llm_provider_factory.create(
        provider=settings.GENERATION_BACKEND,
        api_url=gen_url
    )
    app.generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    # --- Utility Client Setup (Fast model for agentic tasks) ---
    app.utility_client = llm_provider_factory.create(
        provider=settings.GENERATION_BACKEND,
        api_url=gen_url
    )
    app.utility_client.set_generation_model(model_id=settings.UTILITY_MODEL_ID)

    # --- Embedding Client Setup ---
    app.embedding_client = llm_provider_factory.create(
        provider=settings.EMBEDDING_BACKEND,
        api_url=settings.OPENAI_EMBEDDING_API_URL
    )
    app.embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID,
                                             embedding_size=settings.EMBEDDING_MODEL_SIZE)
    
    # --- Vector DB Client Setup ---
    app.vectordb_client = vectordb_provider_factory.create(
        provider=settings.VECTOR_DB_BACKEND
    )
    try:
        print("[AGENT] Connecting to Vector Database...")
        await asyncio.wait_for(app.vectordb_client.connect(), timeout=30.0)
        print("[AGENT] Vector Database connected.")
    except Exception as e:
        print(f"[AGENT] Skipping Vector DB connection: {str(e)}")
    

    # --- Reranker Setup (Disabled to remove sentence-transformers dependency) ---
    # from stores.vectordb.providers.SentenceTransformerReranker import SentenceTransformerReranker
    # app.reranker = SentenceTransformerReranker()
    app.reranker = None


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
 
    if settings.CONNEXIO_INTERNAL_API_KEY:
        print(
            f"[AGENT] X-API-Key authentication ENABLED. "
            f"Backend URL: {settings.MAIN_BACKEND_URL}"
        )
    else:
        print(
            "[AGENT] WARNING: CONNEXIO_INTERNAL_API_KEY is not set. "
            "X-API-Key validation is DISABLED. Set this before any shared deployment."
        )

async def shutdown_span():
    if hasattr(app, 'backend_client') and app.backend_client:
        await app.backend_client.close()
    await app.db_engine.dispose()
    if hasattr(app, 'vectordb_client') and app.vectordb_client:
        await app.vectordb_client.disconnect()

# --- Register Lifecycle Events ---
app.on_event("startup")(startup_span)
app.on_event("shutdown")(shutdown_span)

# --- Include Routers ---
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
app.include_router(agent.agent_router)
app.include_router(projects_router)

@app.get("/")
async def root():
    return {
        "status": "Connexios RAG is running",
        "health": "healthy",
        "documentation": "/docs"
    }