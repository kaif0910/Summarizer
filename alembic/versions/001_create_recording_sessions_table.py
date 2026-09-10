"""create recording sessions table

Revision ID: 001_create_recording_sessions
Revises: 
Create Date: 2026-09-11 01:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_create_recording_sessions'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create items table
    op.create_table(
        'items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_items_id'), 'items', ['id'], unique=False)
    op.create_index(op.f('ix_items_title'), 'items', ['title'], unique=False)

    # Create recording_sessions table
    op.create_table(
        'recording_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='idle'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('audio_file_path', sa.String(length=512), nullable=True),
        sa.Column('transcript', sa.Text(), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recording_sessions_id'), 'recording_sessions', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_recording_sessions_id'), table_name='recording_sessions')
    op.drop_table('recording_sessions')
    op.drop_index(op.f('ix_items_title'), table_name='items')
    op.drop_index(op.f('ix_items_id'), table_name='items')
    op.drop_table('items')
