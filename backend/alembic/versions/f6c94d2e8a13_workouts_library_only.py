"""Workouts: the library only — a workout stays a habit

Revision ID: f6c94d2e8a13
Revises: e5b83c1a4762
Create Date: 2026-09-07

`e5b83c1a4762` built a session ledger — `workout_logs` and `workout_items` —
and retired the *Workout* habit into it. That was wrong, and the reason is
worth keeping: **the user never records which exercises he did.** He logs that
he trained, yes or no, the same way he logs a cigarette. A ledger of lines
modelled someone else.

What was actually wanted is the half that stays: `exercises` as a **library**,
exactly as `dishes` is one. Not to record from — to suggest out of. *"Aaj leg
lagana hai"* is answered by reading the library; anything it does not hold, the
agent finds elsewhere.

So: the habit and its three logs come back untouched, and the two tables go.
`exercises.aliases` and `exercise_saves` stay — they are library, not ledger.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f6c94d2e8a13'
down_revision: str | Sequence[str] | None = 'e5b83c1a4762'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    # The sessions were inserted carrying their habit log's own id, so the logs
    # they replaced are exactly the rows to bring back.
    conn.execute(sa.text("""
        UPDATE habit_logs SET deleted_at = NULL
        WHERE id IN (SELECT id FROM workout_logs)
    """))
    conn.execute(sa.text("UPDATE habits SET deleted_at = NULL WHERE name = 'Workout'"))
    op.drop_table('workout_items')
    op.drop_table('workout_logs')


def downgrade() -> None:
    """Deliberately not reversible. Re-running e5b83c1a4762's tables would
    recreate a shape that was built against an imagined user; if sessions are
    ever wanted, they get a fresh migration and a fresh argument."""
    raise NotImplementedError("the session ledger is not coming back this way")
