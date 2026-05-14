from .connexio_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, DateTime, func, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Index
import uuid


class ChatSession(SQLAlchemyBase):
    """
    Stores persistent chat session data for the RAG agent.
    Tracks persona, language, workflow node, and conversation history
    across turns for adaptive session tracking.
    """

    __tablename__ = "rag_chat_sessions"

    session_id = Column(Integer, primary_key=True, autoincrement=True)
    session_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)

    # Links to the backend user (from the Connexio backend DB)
    user_id = Column(Integer, nullable=False)

    # Links to the RAG project context
    project_id = Column(Integer, nullable=True)

    # Adaptive tracking fields
    persona = Column(Text, nullable=False, default="student")
    language = Column(String(10), nullable=False, default="en")
    last_workflow_node = Column(String(50), nullable=True, default="general")
    current_phase = Column(String(100), nullable=True)

    # Chat history stored as a JSONB array of message objects
    # Each entry: {"role": "user"|"assistant", "content": "...", "node": "...", "timestamp": "..."}
    chat_history = Column(JSONB, nullable=False, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        Index('ix_session_user_id', user_id),
        Index('ix_session_project_id', project_id),
    )
