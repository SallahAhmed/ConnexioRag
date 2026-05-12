from .connexio_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, DateTime, func


class ProjectIDMap(SQLAlchemyBase):
    """Maps MySQL project IDs (PID) to PostgreSQL project IDs.
    Prevents silent divergence if sequences drift between the two databases.
    """

    __tablename__ = "project_id_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mysql_pid = Column(Integer, nullable=False, unique=True)
    pg_pid = Column(Integer, nullable=False, unique=True)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
