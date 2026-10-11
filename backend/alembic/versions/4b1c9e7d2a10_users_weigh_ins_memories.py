"""users, weigh_ins, memories — and a real id for the one user

Revision ID: 4b1c9e7d2a10
Revises: 37da19062c2f
Create Date: 2026-09-04

`profile` becomes `users`. The single row gets a ULID, every `user_id` and
`created_by_id` that said 'me' is rewritten to it, and those columns become
real foreign keys. The lock (login) is a separate decision; this is the table.
spec/in-progress/users-profile.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from ulid import ULID

from alembic import op

revision: str = '4b1c9e7d2a10'
down_revision: str | Sequence[str] | None = '37da19062c2f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every column that names a person.
OWNER_COLS = [
    ("balance_checks", "user_id"),
    ("counterparties", "user_id"),
    ("days", "user_id"),
    ("exercises", "created_by_id"),
    ("habit_logs", "user_id"),
    ("habits", "user_id"),
    ("meal_logs", "user_id"),
    ("measures", "created_by_id"),
    ("pantry", "user_id"),
    ("pantry_moves", "user_id"),
    ("places", "user_id"),
    ("predictions", "user_id"),
    ("projects", "user_id"),
    ("recipes", "created_by_id"),
    ("tasks", "user_id"),
    ("transactions", "user_id"),
]
HAD_DEFAULT = ["counterparties", "places", "transactions", "predictions", "balance_checks"]


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('dob', sa.Date(), nullable=True),
        sa.Column('height_cm', sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column('city', sa.Text(), nullable=True),
        sa.Column('timezone', sa.Text(), server_default='Asia/Kolkata', nullable=False),
        sa.Column('savings_target_paise', sa.BigInteger(), nullable=True),
        sa.Column('kcal_target', sa.Integer(), nullable=True),
        sa.Column('protein_g_target', sa.Numeric(precision=6, scale=1), nullable=True),
        sa.Column('carbs_g_target', sa.Numeric(precision=6, scale=1), nullable=True),
        sa.Column('fat_g_target', sa.Numeric(precision=6, scale=1), nullable=True),
        sa.Column('fibre_g_target', sa.Numeric(precision=6, scale=1), nullable=True),
        sa.Column('weight_target_kg', sa.Numeric(precision=5, scale=1), nullable=True),
        sa.Column('sleep_target_min', sa.Integer(), nullable=True),
        sa.Column('step_target', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.PrimaryKeyConstraint('id'),
    )

    # The one person. Carry the profile row over if there is one; otherwise a
    # fresh database still gets its single user, so the seam has a row to return.
    uid = str(ULID())
    conn = op.get_bind()
    prof = conn.execute(sa.text("SELECT savings_target_paise, timezone FROM profile LIMIT 1")).first()  # noqa: E501
    conn.execute(
        sa.text(
            "INSERT INTO users (id, display_name, timezone, savings_target_paise) "
            "VALUES (:id, :name, :tz, :goal)"
        ),
        {"id": uid, "name": "Sonu", "tz": prof.timezone if prof else "Asia/Kolkata",
         "goal": prof.savings_target_paise if prof else None},
    )

    for table, col in OWNER_COLS:
        conn.execute(sa.text(f"UPDATE {table} SET {col} = :id WHERE {col} = 'me'"), {"id": uid})
        op.create_foreign_key(f"fk_{table}_{col}", table, "users", [col], ["id"])
    for table in HAD_DEFAULT:
        op.alter_column(table, "user_id", server_default=None)

    op.drop_table('profile')

    op.create_table(
        'weigh_ins',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('local_day', sa.Date(), nullable=False),
        sa.Column('weight_kg', sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('dedupe_key', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_weigh_ins_user_day', 'weigh_ins', ['user_id', 'local_day'], unique=True,
                    postgresql_where=sa.text('deleted_at IS NULL'))

    op.create_table(
        'memories',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('slug', sa.Text(), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=11), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('identity','preference','style','interest','project','reference')", name='ck_memories_kind'),  # noqa: E501
        sa.CheckConstraint("source IN ('user','claude-code','claude','chatgpt','gemini','cortex')", name='ck_memories_source'),  # noqa: E501
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_memories_user_slug', 'memories', ['user_id', 'slug'], unique=True,
                    postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('ix_memories_user_kind', 'memories', ['user_id', 'kind'])


def downgrade() -> None:
    op.drop_table('memories')
    op.drop_table('weigh_ins')

    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id, savings_target_paise, timezone FROM users ORDER BY created_at LIMIT 1")
    ).first()
    op.create_table(
        'profile',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('savings_target_paise', sa.BigInteger(), nullable=True),
        sa.Column('timezone', sa.Text(), server_default='Asia/Kolkata', nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    if row:
        conn.execute(
            sa.text(
                "INSERT INTO profile (id, savings_target_paise, timezone) "
                "VALUES ('me', :goal, :tz)"
            ),
            {"goal": row.savings_target_paise, "tz": row.timezone},
        )
    for table in HAD_DEFAULT:
        op.alter_column(table, "user_id", server_default="me")
    for table, col in OWNER_COLS:
        op.drop_constraint(f"fk_{table}_{col}", table, type_="foreignkey")
        if row:
            conn.execute(
                sa.text(f"UPDATE {table} SET {col} = 'me' WHERE {col} = :id"), {"id": row.id}
            )
    op.drop_table('users')
