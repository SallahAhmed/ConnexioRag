"""add project_id_map table

Revision ID: f1a2b3c4d5e6
Revises: e76f6aa5f9c8
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e76f6aa5f9c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project_id_map',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('mysql_pid', sa.Integer(), nullable=False),
        sa.Column('pg_pid', sa.Integer(), nullable=False),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mysql_pid'),
        sa.UniqueConstraint('pg_pid'),
    )
    op.create_index('ix_project_id_map_mysql_pid', 'project_id_map', ['mysql_pid'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_project_id_map_mysql_pid', table_name='project_id_map')
    op.drop_table('project_id_map')
