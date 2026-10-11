"""Habits: a name can be retired and used again

Revision ID: b82e4f19c7a3
Revises: a71c3d05e9f4
Create Date: 2026-09-15

`uq_habits_user_name` is a plain unique constraint, so a soft-deleted habit
keeps holding its name: retire *Meditation* and you can never add it back.
Every other table in this schema guards uniqueness with a partial index on
`deleted_at IS NULL`, and habits were the exception.

It becomes case-insensitive at the same time. `log_day` matches a habit by the
name the user said, so *workout* and *Workout* are one habit to them and were
two to the database. spec/in-progress/habits.md § rules.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b82e4f19c7a3'
down_revision: str | Sequence[str] | None = 'a71c3d05e9f4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_habits_user_name", "habits", type_="unique")
    op.execute(sa.text(
        "CREATE UNIQUE INDEX uq_habits_user_name ON habits (user_id, lower(name)) "
        "WHERE deleted_at IS NULL"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_habits_user_name"))
    op.create_unique_constraint("uq_habits_user_name", "habits", ["user_id", "name"])
