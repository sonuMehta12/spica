"""Chat: a marker for what the user has cleared from view

Revision ID: a71c3d05e9f4
Revises: c93a1e4b7d20
Create Date: 2026-09-13

The thread is deliberately permanent — there is one conversation and no "new
chat". Permanent in the database and permanent on screen are different
promises though, and only the first one was ever decided.

`cleared_through_seq` is the second: everything at or below it is hidden from
the client's default read, and nothing is deleted. Pressing clear also folds
those messages into the summary, so the screen starts fresh while the agent
keeps the gist. spec/done/chat-history.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a71c3d05e9f4'
down_revision: str | Sequence[str] | None = 'c93a1e4b7d20'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column(
        "cleared_through_seq", sa.BigInteger(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("conversations", "cleared_through_seq")
