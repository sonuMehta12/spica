"""conversations and messages — one thread, kept forever

Revision ID: c93a1e4b7d20
Revises: b8d35f27ca91
Create Date: 2026-09-12

There is no "new chat": one conversation per user, every turn appended. The
model reads the last twenty turns plus a rolling summary of what came before;
the user reads all of it. spec/agent.md.

Tool traffic is deliberately not stored as replayable messages — an old tool
result is a stale number, and replaying it is how a model comes to quote
yesterday's spend as today's. `tool_trace` keeps it for debugging only.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c93a1e4b7d20'
down_revision: str | Sequence[str] | None = 'b8d35f27ca91'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('summary_through_seq', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_conversations_user', 'conversations', ['user_id'], unique=True,
                    postgresql_where=sa.text('deleted_at IS NULL'))

    op.create_table(
        'messages',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('conversation_id', sa.String(length=26), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('seq', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(length=9), nullable=False),
        sa.Column('text', sa.Text(), server_default='', nullable=False),
        sa.Column('cards', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tool_trace', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tokens_in', sa.Integer(), nullable=True),
        sa.Column('tokens_out', sa.Integer(), nullable=True),
        sa.Column('model', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('user','agent')", name='ck_messages_role'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_messages_conv_seq', 'messages', ['conversation_id', 'seq'], unique=True)


def downgrade() -> None:
    op.drop_table('messages')
    op.drop_table('conversations')
