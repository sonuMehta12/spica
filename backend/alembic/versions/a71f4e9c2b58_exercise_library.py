"""exercises: one owned library row, with how-to, source and a tried count

Revision ID: a71f4e9c2b58
Revises: f6c94d2e8a13
Create Date: 2026-09-07

The table existed since the diet model and never had the fields a suggestion is
made from. spec/done/workouts.md.

Three shape changes worth naming:

* **Owned, not pooled.** `visibility` / `created_by_id` / `forked_from_id` go;
  `user_id` arrives NOT NULL. Dishes keeps the pool because the app ships one;
  one person's exercise library does not need it, and owning every row removes
  the `COALESCE(created_by_id = :u, false)` NULL trap that 500'd this endpoint.

* **`tried` is stored.** Every other count in Cortex is a query over a ledger.
  Exercises have no ledger — a workout is a habit tick — so "I have done this
  three times" is a declaration, and declarations are stored. It also replaces
  `exercise_saves`, which is dropped: the library *is* the bookmark, and
  `tried = 0` versus `tried > 0` is the only distinction a star was making.

* **`kind` splits off `muscle_group`.** The seed filed cardio as a muscle group,
  which is wrong. Incline walk is `kind: cardio` with no muscle group, so "leg
  lagana hai" returns leg work and not a treadmill.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a71f4e9c2b58'
down_revision: str | Sequence[str] | None = 'f6c94d2e8a13'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CARDIO = ('Incline walk', 'Treadmill run', 'Cycling', 'Skipping', 'Stair climber')


def upgrade() -> None:
    op.drop_table('exercise_saves')

    op.add_column('exercises', sa.Column('user_id', sa.Text(), nullable=True))
    op.add_column('exercises', sa.Column('kind', sa.Text(), nullable=True))
    op.add_column('exercises', sa.Column('steps', sa.Text(), nullable=True))
    op.add_column('exercises', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('exercises', sa.Column('image_url', sa.Text(), nullable=True))
    op.add_column('exercises', sa.Column('source', sa.Text(), nullable=True))
    op.add_column('exercises', sa.Column('note', sa.Text(), nullable=True))
    op.add_column('exercises',
                  sa.Column('tried', sa.Integer(), server_default='0', nullable=False))
    op.add_column('exercises', sa.Column('last_tried', sa.Date(), nullable=True))

    conn = op.get_bind()
    # The seeded rows were public with no author; they belong to the one user.
    sole = conn.execute(sa.text("SELECT id FROM users ORDER BY created_at LIMIT 1")).scalar()
    if sole is not None:
        conn.execute(sa.text("UPDATE exercises SET user_id = :u WHERE user_id IS NULL"),
                     {"u": sole})
    conn.execute(sa.text("UPDATE exercises SET source = 'seed' WHERE source IS NULL"))
    # Cardio is not a muscle. Split it onto `kind` and clear the group.
    conn.execute(
        sa.text("UPDATE exercises SET kind = 'cardio', muscle_group = NULL "
                "WHERE name = ANY(:names)"),
        {"names": list(CARDIO)},
    )
    conn.execute(sa.text("UPDATE exercises SET kind = 'strength' WHERE kind IS NULL"))

    op.alter_column('exercises', 'user_id', nullable=False)
    op.alter_column('exercises', 'source', nullable=False)
    op.create_foreign_key('fk_exercises_user', 'exercises', 'users', ['user_id'], ['id'])
    op.create_check_constraint(
        'ck_exercises_kind', 'exercises',
        "kind IS NULL OR kind IN ('strength','cardio','mobility','stretch')")
    op.create_check_constraint(
        'ck_exercises_source', 'exercises',
        "source IN ('seed','chat','link','manual')")
    op.create_check_constraint('ck_exercises_tried', 'exercises', 'tried >= 0')
    op.create_index('ix_exercises_user_group', 'exercises', ['user_id', 'muscle_group'])

    op.drop_constraint('ck_exercises_visibility', 'exercises', type_='check')
    op.drop_column('exercises', 'forked_from_id')
    op.drop_column('exercises', 'visibility')
    op.drop_column('exercises', 'created_by_id')


def downgrade() -> None:
    op.add_column('exercises', sa.Column('created_by_id', sa.Text(), nullable=True))
    op.add_column('exercises', sa.Column('visibility', sa.String(length=8),
                                         server_default='private', nullable=False))
    op.add_column('exercises', sa.Column('forked_from_id', sa.String(length=26), nullable=True))
    op.create_check_constraint("ck_exercises_visibility", "exercises",
                               "visibility IN ('private','public')")
    op.drop_index('ix_exercises_user_group', table_name='exercises')
    for name in ('ck_exercises_tried', 'ck_exercises_source', 'ck_exercises_kind'):
        op.drop_constraint(name, 'exercises', type_='check')
    op.drop_constraint('fk_exercises_user', 'exercises', type_='foreignkey')
    for col in ('last_tried', 'tried', 'note', 'source', 'image_url',
                'source_url', 'steps', 'kind', 'user_id'):
        op.drop_column('exercises', col)
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
