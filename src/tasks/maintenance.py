from celery_app import celery_app, get_setup_utils
from helpers.config import get_settings
import asyncio
from utils.idempotency_manager import IdempotencyManager

import logging
logger = logging.getLogger(__name__)

@celery_app.task(
                 bind=True, name="tasks.maintenance.clean_celery_executions_table",
                 autoretry_for=(Exception,),
                 retry_kwargs={'max_retries': 3, 'countdown': 60}
                )
def clean_celery_executions_table(self):

    return asyncio.run(
        _clean_celery_executions_table(self)
    )

async def _clean_celery_executions_table(task_instance):

    db_engine, vectordb_client = None, None
    
    try:

        (db_engine, db_client, llm_provider_factory,
        vectordb_provider_factory,
        generation_client, utility_client, embedding_client,
        vectordb_client, template_parser) = await get_setup_utils()

        # Create idempotency manager
        idempotency_manager = IdempotencyManager(db_client, db_engine)

        logger.warning(f"cleaning !!!")
        _ = await idempotency_manager.cleanup_old_tasks(86400)

        return True

    except Exception as e:
        logger.error(f"Task failed: {str(e)}")
        raise
    finally:
        try:
            if db_engine:
                await db_engine.dispose()
            
            if vectordb_client:
                await vectordb_client.disconnect()
        except Exception as e:
            logger.error(f"Task failed while cleaning: {str(e)}")


@celery_app.task(
    bind=True, name="tasks.maintenance.clean_stale_sessions",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 60}
)
def clean_stale_sessions(self):
    return asyncio.run(_clean_stale_sessions(self))

async def _clean_stale_sessions(task_instance):
    from sqlalchemy import text as sql_text
    from models.db_schemas.connexio.schemas.chat_session import ChatSession
    db_engine = None
    try:
        (db_engine, db_client, llm_provider_factory,
         vectordb_provider_factory,
         generation_client, utility_client, embedding_client,
         vectordb_client, template_parser) = await get_setup_utils()

        cutoff_days = task_instance.app.conf.get("SESSION_TTL_DAYS", 30) if hasattr(task_instance, "app") else 30
        async with db_client() as session:
            async with session.begin():
                stmt = sql_text(
                    f"DELETE FROM rag_chat_sessions "
                    f"WHERE updated_at < NOW() - INTERVAL '{cutoff_days} days' "
                    f"OR (updated_at IS NULL AND created_at < NOW() - INTERVAL '{cutoff_days} days')"
                )
                result = await session.execute(stmt)
                deleted = result.rowcount
                await session.commit()
        logger.warning(f"Cleaned {deleted} stale sessions older than {cutoff_days} days")
        return deleted
    except Exception as e:
        logger.error(f"Session cleanup task failed: {str(e)}")
        return 0
    finally:
        if db_engine:
            await db_engine.dispose()