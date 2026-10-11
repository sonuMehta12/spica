"""Nudges: what Cortex says without being asked

Revision ID: e7b41c9d0a52
Revises: d2f7a9c41e85
Create Date: 2026-10-08

A scheduled job's output was going to be a turn in the thread
(spec/in-progress/schedules.md), and an unprompted message in the person's
conversation is the greeting's problem again: it reads as a message nobody
sent. What a run prepares is a **nudge** instead — a row the bell lists, each
opening a page where the thing gets done. spec/in-progress/nudges.md.

The row seeded here is the morning brief at 08:00, on — the first run that
nudges. Seeded the way the categoriser was, so the first thing the person sees
in Daily runs is the feature working, with its time theirs to change. Only
when the user row is already there; a fresh database seeds it in the users
migration, before this one runs.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e7b41c9d0a52'
down_revision: str | Sequence[str] | None = 'd2f7a9c41e85'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('nudges',
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('schedule_id', sa.Text(), nullable=True),
    sa.Column('local_day', sa.Date(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('line', sa.Text(), nullable=True),
    sa.Column('refs', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('done_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
              nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
              nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("kind IN ('day', 'meals', 'workout', 'dinner', 'reminder', 'review')",
                       name='ck_nudges_kind'),
    sa.ForeignKeyConstraint(['schedule_id'], ['schedules.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_nudges_user_day', 'nudges', ['user_id', 'local_day'], unique=False)
    # The morning brief, at a morning hour, with a short grace: a brief at 6pm
    # is not late, it is wrong. No row can be in the way — `/schedules`
    # refused `morning_brief` until the job existed.
    op.execute("""
        INSERT INTO schedules (id, user_id, job, at_local_time, repeat, days, params,
                               enabled, grace_hours, created_at, updated_at)
        SELECT 'sched-morning-brief', u.id, 'morning_brief', TIME '08:00', 'daily', '{}', '{}',
               true, 3, now(), now()
        FROM users u ORDER BY u.created_at LIMIT 1
    """)


def downgrade() -> None:
    op.drop_index('ix_nudges_user_day', table_name='nudges')
    op.drop_table('nudges')
    op.execute("DELETE FROM schedules WHERE id = 'sched-morning-brief'")
