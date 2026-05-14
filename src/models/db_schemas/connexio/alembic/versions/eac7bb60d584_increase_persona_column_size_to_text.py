"""Increase persona column size to Text

Revision ID: eac7bb60d584
Revises: f1a2b3c4d5e6
Create Date: 2026-05-14 20:49:10.016080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'eac7bb60d584'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('rag_chat_sessions', 'persona',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.Text(),
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('rag_chat_sessions', 'persona',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=50),
               existing_nullable=False)
