from .BaseDataModel import BaseDataModel
from .db_schemas import ChatSession
from sqlalchemy import select, update
from datetime import datetime, timezone
import json


class SessionModel(BaseDataModel):
    """
    CRUD operations for RAG chat sessions.
    Handles creation, retrieval, updates, and chat history management.
    """

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        return instance

    async def create_session(self, user_id: int, project_id: int = None,
                              persona: str = "student", language: str = "en") -> ChatSession:
        """Creates a new chat session for a user."""
        session_record = ChatSession(
            user_id=user_id,
            project_id=project_id,
            persona=persona,
            language=language,
            chat_history=[]
        )

        async with self.db_client() as session:
            async with session.begin():
                session.add(session_record)
            await session.commit()
            await session.refresh(session_record)

        return session_record

    async def get_session(self, session_id: int) -> ChatSession:
        """Retrieves a session by its ID."""
        async with self.db_client() as session:
            result = await session.execute(
                select(ChatSession).where(ChatSession.session_id == session_id)
            )
            return result.scalar_one_or_none()

    async def get_or_create_session(self, user_id: int, project_id: int = None,
                                     persona: str = "student", language: str = "en") -> ChatSession:
        """Gets the latest active session for a user+project, or creates one."""
        async with self.db_client() as session:
            query = select(ChatSession).where(
                ChatSession.user_id == user_id
            )
            if project_id:
                query = query.where(ChatSession.project_id == project_id)

            query = query.order_by(ChatSession.created_at.desc()).limit(1)
            result = await session.execute(query)
            existing = result.scalar_one_or_none()

        if existing:
            return existing

        return await self.create_session(
            user_id=user_id, project_id=project_id,
            persona=persona, language=language
        )

    async def append_message(self, session_id: int, role: str, content: str,
                              workflow_node: str = None):
        """Appends a message to the chat history JSONB array in a single transaction."""
        message = {
            "role": role,
            "content": content,
            "node": workflow_node,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        async with self.db_client() as session:
            async with session.begin():
                result = await session.execute(
                    select(ChatSession).where(ChatSession.session_id == session_id)
                )
                chat_session = result.scalar_one_or_none()
                if not chat_session:
                    return None

                current_history = list(chat_session.chat_history or [])
                current_history.append(message)
                chat_session.chat_history = current_history
                chat_session.last_workflow_node = workflow_node
            await session.commit()

        return message

    async def update_session_metadata(self, session_id: int,
                                       persona: str = None, language: str = None,
                                       current_phase: str = None):
        """Updates adaptive tracking fields on the session."""
        update_values = {}
        if persona:
            update_values["persona"] = persona
        if language:
            update_values["language"] = language
        if current_phase:
            update_values["current_phase"] = current_phase

        if not update_values:
            return

        async with self.db_client() as session:
            stmt = (
                update(ChatSession)
                .where(ChatSession.session_id == session_id)
                .values(**update_values)
            )
            await session.execute(stmt)
            await session.commit()

    async def get_recent_history(self, session_id: int, last_n: int = 50) -> list:
        """Returns the last N messages from the chat history."""
        chat_session = await self.get_session(session_id)
        if not chat_session or not chat_session.chat_history:
            return []

        return chat_session.chat_history[-last_n:]
