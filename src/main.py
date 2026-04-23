# --- Framework & Core Imports ---
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio

# --- Application Routes ---
from Routes import base, data, nlp, agent

# --- Configuration & Factories ---
from helpers.config import get_settings
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from stores.llm.templates.template_parser import TemplateParser

# --- Models & Utils ---
from models.db_schemas.connexio.schemas import SQLAlchemyBase
from utils.metrics import setup_metrics

# --- App Initialization ---
app = FastAPI()
setup_metrics(app)

async def startup_span():
    settings = get_settings()
    app.settings = settings

    # --- Database Initialization (Postgres) ---
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    app.db_engine = create_async_engine(postgres_conn)
    
    # Ensure tables are created (with a safety timeout to prevent hanging the whole server)
    try:
        async with app.db_engine.begin() as conn:
            print("[AGENT] Initializing database tables...")
            await asyncio.wait_for(conn.run_sync(SQLAlchemyBase.metadata.create_all), timeout=5.0)
            print("[AGENT] Database tables initialized or already exist.")
    except Exception as e:
        print(f"[AGENT] Skipping database auto-initialization: {str(e)}")
        print("[AGENT] (The server will still start, but some database features might fail until fixed).")

    app.db_client = sessionmaker(
        app.db_engine, class_=AsyncSession, expire_on_commit=False
    )

    # --- AI & Provider Factories ---
    llm_provider_factory = LLMProviderFactory(settings)
    vectordb_provider_factory = VectorDBProviderFactory(config=settings, db_client=app.db_client)

    # --- Generation Client Setup ---
    app.generation_client = llm_provider_factory.create(
        provider=settings.GENERATION_BACKEND,
        api_url=settings.OPENAI_GENERATION_API_URL
    )
    app.generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

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
    await app.vectordb_client.connect()
    
    # --- Template Parser Setup ---
    app.template_parser = TemplateParser(
        language=settings.PRIMARY_LANG,
        default_language=settings.DEFAULT_LANG,
    )

async def shutdown_span():
    await app.db_engine.dispose()
    await app.vectordb_client.disconnect()

# --- Register Lifecycle Events ---
app.on_event("startup")(startup_span)
app.on_event("shutdown")(shutdown_span)

# --- Include Routers ---
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
app.include_router(agent.agent_router)