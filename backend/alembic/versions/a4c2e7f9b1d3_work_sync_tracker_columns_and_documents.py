"""Work sync: a tracker's view of a task, and the documents already read

Revision ID: a4c2e7f9b1d3
Revises: c7897436c144
Create Date: 2026-09-27

Two shapes of source (spec/work-sync.md § Two shapes of source):

- A **tracker item** (a Linear issue) keeps changing after Cortex first sees
  it, so it is re-read every run and matched on `(source, source_key)` — the
  issue's UUID. The unique index covers soft-deleted rows on purpose: that is
  what stops a task deleted here from being created again on the next pull.
- A **document** (a meeting) never changes, so it is read once. A task row
  cannot record that — a meeting that produced nothing leaves no task — hence
  `source_documents`, unique on live rows so a soft delete means *read again*.

`status_at` is separate from `updated_at` because a pull refreshes titles and
dates on every run; only `status_at` can say when the person ticked something,
which is what tells a tick from a move in the tracker.

Existing rows stay NULL throughout: none came from a tracker, and nothing can
say now when their status last changed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a4c2e7f9b1d3'
down_revision: str | Sequence[str] | None = 'c7897436c144'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('source_key', sa.Text(), nullable=True))
    op.add_column('tasks', sa.Column('source_status', sa.String(length=8), nullable=True))
    op.add_column('tasks', sa.Column('source_state', sa.Text(), nullable=True))
    op.add_column('tasks', sa.Column('source_state_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tasks', sa.Column('status_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('uq_tasks_user_source_key', 'tasks', ['user_id', 'source', 'source_key'],
                    unique=True, postgresql_where=sa.text('source_key IS NOT NULL'))
    op.create_check_constraint(
        'ck_tasks_source_status', 'tasks',
        "source_status IS NULL OR source_status IN ('open','done','dropped')")

    op.create_table(
        'source_documents',
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('ref', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('tasks_created', sa.Integer(), server_default='0', nullable=False),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_source_documents_user_source_ref', 'source_documents',
                    ['user_id', 'source', 'ref'], unique=True,
                    postgresql_where=sa.text('deleted_at IS NULL'))


def downgrade() -> None:
    op.drop_index('uq_source_documents_user_source_ref', table_name='source_documents',
                  postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_table('source_documents')
    op.drop_constraint('ck_tasks_source_status', 'tasks', type_='check')
    op.drop_index('uq_tasks_user_source_key', table_name='tasks',
                  postgresql_where=sa.text('source_key IS NOT NULL'))
    for col in ('status_at', 'source_state_at', 'source_state', 'source_status', 'source_key'):
        op.drop_column('tasks', col)
