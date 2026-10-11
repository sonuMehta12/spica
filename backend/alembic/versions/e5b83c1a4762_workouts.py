"""Workouts: an exercise library, and sessions as a ledger

Revision ID: e5b83c1a4762
Revises: c4a71e9b3d68
Create Date: 2026-09-06

A workout was a habit tick. A tick can say you turned up; it cannot say you
trained legs, and the five-day split makes that the question. So the same three
shapes dishes uses: `exercises` is the library, `workout_logs` is the ledger
row, `workout_items` are the lines. spec/in-progress/workouts.md.

The three existing logs become sessions and keep their original wording in
`note`, so nothing the user typed is lost to a mapping. The *Workout* habit is
soft-deleted — cigarettes and alcohol stay habits, because they have no shape;
a session has one.

No sets, reps or weight. Twenty-four days of tracking contain none of them, and
the columns are a one-line migration on the day one is actually logged.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e5b83c1a4762'
down_revision: str | Sequence[str] | None = 'c4a71e9b3d68'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# What the note said → what it was. 'Gym — haan' names no split, so it stays
# 'gym': where, not what. Inventing 'push' for it would be a fabricated number
# in prose form.
KINDS = {
    'Gym — Workout B (back)': 'back',
    'Gym — Workout A (chest/push)': 'push',
    'Gym — haan': 'gym',
}


def upgrade() -> None:
    op.add_column('exercises',
                  sa.Column('aliases', sa.ARRAY(sa.Text()), server_default='{}', nullable=False))

    op.create_table(
        'exercise_saves',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('exercise_id', sa.String(length=26), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_exercise_saves_user_exercise', 'exercise_saves',
                    ['user_id', 'exercise_id'], unique=True,
                    postgresql_where=sa.text('deleted_at IS NULL'))

    op.create_table(
        'workout_logs',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('local_day', sa.Date(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('minutes', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('dedupe_key', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("source IN ('manual','voice','agent')", name='ck_workout_logs_source'),
        sa.CheckConstraint('minutes IS NULL OR minutes > 0', name='ck_workout_logs_minutes'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workout_logs_user_day', 'workout_logs', ['user_id', 'local_day'])

    op.create_table(
        'workout_items',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('workout_log_id', sa.String(length=26), nullable=False),
        sa.Column('exercise_id', sa.String(length=26), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id']),
        sa.ForeignKeyConstraint(['workout_log_id'], ['workout_logs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workout_items_log', 'workout_items', ['workout_log_id'])
    op.create_index('ix_workout_items_exercise', 'workout_items', ['exercise_id'])
    op.create_index('uq_workout_items_log_exercise', 'workout_items',
                    ['workout_log_id', 'exercise_id'], unique=True,
                    postgresql_where=sa.text('deleted_at IS NULL'))

    # The three habit logs become sessions, keeping their own words in `note`.
    conn = op.get_bind()
    logs = conn.execute(sa.text("""
        SELECT hl.id, hl.user_id, hl.local_day, hl.occurred_at, hl.note
        FROM habit_logs hl JOIN habits h ON h.id = hl.habit_id
        WHERE h.name = 'Workout' AND hl.deleted_at IS NULL
    """)).mappings().all()
    for row in logs:
        conn.execute(sa.text("""
            INSERT INTO workout_logs
                (id, user_id, local_day, occurred_at, kind, note, source)
            VALUES (:id, :user_id, :day, :at, :kind, :note, 'manual')
        """), {
            "id": row["id"], "user_id": row["user_id"], "day": row["local_day"],
            "at": row["occurred_at"], "note": row["note"],
            "kind": KINDS.get((row["note"] or "").strip(), "gym"),
        })
        conn.execute(sa.text("UPDATE habit_logs SET deleted_at = now() WHERE id = :id"),
                     {"id": row["id"]})
    # The habit itself goes. Cigarettes and alcohol stay: they have no shape.
    conn.execute(sa.text("UPDATE habits SET deleted_at = now() "
                         "WHERE name = 'Workout' AND deleted_at IS NULL"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE habits SET deleted_at = NULL WHERE name = 'Workout'"))
    conn.execute(sa.text("""
        UPDATE habit_logs SET deleted_at = NULL
        WHERE id IN (SELECT id FROM workout_logs)
    """))
    op.drop_table('workout_items')
    op.drop_table('workout_logs')
    op.drop_table('exercise_saves')
    op.drop_column('exercises', 'aliases')
