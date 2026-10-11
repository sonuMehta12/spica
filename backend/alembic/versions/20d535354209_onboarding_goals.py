"""Onboarding, goals first: gender and diet on the person, an estimated weigh-in

Revision ID: 20d535354209
Revises: f3a8c5d21b69
Create Date: 2026-10-11

The first run now asks a few questions, and the answers go where the app
already keeps them (spec/done/onboarding-goals.md § Data). Two are categories the
app computes with — diet limits what Home's meal plan suggests, gender sizes
it — so they are columns on `users`, nullable: a skipped answer is absent,
never a default. *Around 72* is the one answer people routinely guess, so a
weigh-in can say it was approximate; an exact reading the same day clears it.

Each answer is one model call through `POST /onboarding/turn`, capped at forty
a day per account. The turns are not written to the chat thread, so nothing
already counts them: two columns on the person hold today's count and the day
it is for.

`onboarding_done_at` now means *finished or skipped the first run*. Every
account that already has a row anywhere is past its first run, so the backfill
sets it for them — deleted rows count, because someone who logged and deleted
has still been here. Not undone on downgrade: the flag predates this revision.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '20d535354209'
down_revision: str | Sequence[str] | None = 'f3a8c5d21b69'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Any row in one of these, soft-deleted or not, means the account has been used.
LIVED_IN = ("transactions", "meal_logs", "tasks", "habits", "commitments", "weigh_ins",
            "memories", "messages")


def backfill(conn) -> None:
    """Mark every account that already holds a row as past its first run.

    Importable: the tests run it against seeded accounts, because a fresh test
    database has nothing to migrate.
    """
    used = " OR ".join(f"EXISTS (SELECT 1 FROM {t} WHERE {t}.user_id = users.id)"
                       for t in LIVED_IN)
    conn.execute(sa.text(
        f"UPDATE users SET onboarding_done_at = now() "
        f"WHERE onboarding_done_at IS NULL AND ({used})"))


def upgrade() -> None:
    op.add_column('users', sa.Column('gender', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('diet', sa.Text(), nullable=True))
    op.create_check_constraint('ck_users_gender', 'users',
                               "gender IS NULL OR gender IN ('female', 'male', 'other')")
    op.create_check_constraint(
        'ck_users_diet', 'users',
        "diet IS NULL OR diet IN ('veg', 'nonveg', 'eggetarian', 'any')")
    op.add_column('weigh_ins', sa.Column('estimated', sa.Boolean(), server_default='false',
                                         nullable=False))
    op.add_column('users', sa.Column('onboarding_turns', sa.Integer(), server_default='0',
                                     nullable=False))
    op.add_column('users', sa.Column('onboarding_turns_day', sa.Date(), nullable=True))
    backfill(op.get_bind())


def downgrade() -> None:
    op.drop_column('users', 'onboarding_turns_day')
    op.drop_column('users', 'onboarding_turns')
    op.drop_column('weigh_ins', 'estimated')
    op.drop_constraint('ck_users_diet', 'users', type_='check')
    op.drop_constraint('ck_users_gender', 'users', type_='check')
    op.drop_column('users', 'diet')
    op.drop_column('users', 'gender')
