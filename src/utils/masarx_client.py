import logging
from typing import List

logger = logging.getLogger(__name__)


class MasarxApiClient:
    """
    Reads MasarX-owned tables (task, masarx_notifications) directly from the
    shared Neon PostgreSQL instance using RAG's existing async session_maker.
    This avoids HTTP calls between services and uses the shared DB connection pool.

    Column names use PostgreSQL's quoted form because SQLAlchemy creates MasarX's
    mixed-case columns as case-sensitive identifiers ("TaskId", "PID", etc.).
    """

    def __init__(self, db_client=None):
        self.db_client = db_client  # async session_maker from RAG's app.db_client

    async def get_tasks(self, project_id: int, limit: int = 20) -> List[dict]:
        if not self.db_client:
            return []
        try:
            from sqlalchemy import text as sql_text
            async with self.db_client() as session:
                stmt = sql_text(
                    'SELECT t."TaskId", t."TaskName", t."TaskDesc", '
                    't.status, t.priority, t.story_points, t.deadline, '
                    't."UID", u.name AS assignee_name '
                    'FROM task t '
                    'LEFT JOIN "user" u ON t."UID" = u."UID" '
                    'WHERE t."PID" = :pid '
                    'ORDER BY t.created_at DESC LIMIT :lim'
                )
                result = await session.execute(stmt, {"pid": project_id, "lim": limit})
                rows = result.fetchall()
                return [
                    {
                        "task_id": r[0],
                        "title": r[1],
                        "description": r[2],
                        "status": r[3],
                        "priority": r[4],
                        "story_points": r[5],
                        "deadline": str(r[6]) if r[6] else None,
                        "assignee_id": r[7],
                        "assignee_name": r[8],
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"MasarxApiClient.get_tasks error: {e}")
            return []

    async def get_notifications(self, user_id: int, limit: int = 10) -> List[dict]:
        if not self.db_client:
            return []
        try:
            from sqlalchemy import text as sql_text
            async with self.db_client() as session:
                stmt = sql_text(
                    "SELECT id, title, body, channel, is_read, created_at "
                    "FROM masarx_notifications "
                    "WHERE user_id = :uid "
                    "ORDER BY created_at DESC LIMIT :lim"
                )
                result = await session.execute(stmt, {"uid": user_id, "lim": limit})
                rows = result.fetchall()
                return [
                    {
                        "id": str(r[0]),
                        "title": r[1],
                        "body": r[2],
                        "channel": r[3],
                        "is_read": r[4],
                        "created_at": str(r[5]) if r[5] else None,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"MasarxApiClient.get_notifications error: {e}")
            return []
