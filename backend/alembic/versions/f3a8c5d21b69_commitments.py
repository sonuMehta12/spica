"""Commitments: what you still owe, as rows you own

Revision ID: f3a8c5d21b69
Revises: e7b41c9d0a52
Create Date: 2026-10-10

`fixed` and `repeats` were one boolean pair doing two jobs: a label on a
payment, and a forecast that quietly reserved money in a future month with no
way to see it, change it or take it back. A commitment is now a row —
spec/done/commitments.md.

The backfill keeps every number where it was. Every flagged payment is linked
to a commitment: a category that repeated becomes one line per month, a plain
fixed payment becomes a settled one-off, and this month's lines for last
month's repeating categories are rolled forward. The one deliberate difference
is that a part payment now leaves its remainder owed. `fixed` and `repeats`
are no longer read, and stay for one release before they drop.
"""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta

import sqlalchemy as sa
from ulid import ULID

from alembic import op

revision: str = 'f3a8c5d21b69'
down_revision: str | Sequence[str] | None = 'e7b41c9d0a52'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def backfill(conn, today: date) -> None:
    """Link every flagged payment to a commitment, and roll this month's lines.

    Importable: the tests run it against a seeded ledger, because a fresh test
    database has nothing to migrate.
    """
    this_month = today.replace(day=1)
    last_month = (this_month - timedelta(days=1)).replace(day=1)

    rows = conn.execute(sa.text(
        "SELECT id, user_id, local_day, category, description, amount_paise, repeats "
        "FROM transactions WHERE kind = 'expense' AND fixed AND deleted_at IS NULL "
        "ORDER BY local_day, id"
    )).mappings().all()

    groups: dict[tuple[str, date, str], list] = defaultdict(list)
    for r in rows:
        groups[(r["user_id"], r["local_day"].replace(day=1), r["category"])].append(r)

    made: dict[tuple[str, date, str], tuple[str, int, bool]] = {}   # key -> (id, amount, repeats)

    def insert(user, month, name, category, amount, repeats, source="stated", rolled_from=None):
        cid = str(ULID())
        conn.execute(sa.text(
            "INSERT INTO commitments (id, user_id, name, category, amount_paise, "
            "amount_source, local_month, repeats, rolled_from_id) "
            "VALUES (:id, :u, :name, :cat, :amt, :src, :m, :rep, :rf)"),
            {"id": cid, "u": user, "name": name[:80], "cat": category, "amt": amount,
             "src": source, "m": month, "rep": repeats, "rf": rolled_from})
        return cid

    def link(tx_ids, cid):
        conn.execute(sa.text(
            "UPDATE transactions SET commitment_id = :c WHERE id = ANY(:ids)"),
            {"c": cid, "ids": list(tx_ids)})

    for key in sorted(groups, key=lambda k: (k[1], k[0], k[2])):
        user, month, category = key
        grp = groups[key]
        repeating = [r for r in grp if r["repeats"]]
        prev_key = (user, last_month, category)
        if month == this_month and prev_key in made and made[prev_key][2]:
            # Last month repeated this category: this month's line is the one
            # rolled from it, with last month's amount, and the payments
            # already made settle it — a part payment leaves the remainder.
            prev_id, prev_amount, _ = made[prev_key]
            cid = insert(user, month, category, category, prev_amount, True,
                         source="rolled", rolled_from=prev_id)
            made[key] = (cid, prev_amount, True)
            link([r["id"] for r in grp], cid)
        elif repeating:
            amount = sum(r["amount_paise"] for r in repeating)
            cid = insert(user, month, category, category, amount, True)
            made[key] = (cid, amount, True)
            link([r["id"] for r in grp], cid)
        else:
            for r in grp:
                cid = insert(user, month, r["description"] or category, category,
                             r["amount_paise"], False)
                link([r["id"]], cid)
            made[key] = ("", 0, False)

    # This month's lines for last month's repeating categories with no payment
    # yet — the ones that were LOCKED.
    for (user, month, category), (pid, amount, repeats) in list(made.items()):
        if month != last_month or not repeats:
            continue
        if (user, this_month, category) in made:
            continue
        cid = insert(user, this_month, category, category, amount, True,
                     source="rolled", rolled_from=pid)
        made[(user, this_month, category)] = (cid, amount, True)


def upgrade() -> None:
    op.create_table(
        'commitments',
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('amount_paise', sa.BigInteger(), nullable=False),
        sa.Column('amount_source', sa.Text(), server_default='stated', nullable=False),
        sa.Column('local_month', sa.Date(), nullable=False),
        sa.Column('due_day', sa.SmallInteger(), nullable=True),
        sa.Column('repeats', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('skipped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rolled_from_id', sa.Text(), nullable=True),
        sa.Column('carried_from_id', sa.Text(), nullable=True),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('amount_paise > 0', name='ck_commitments_amount_positive'),
        sa.CheckConstraint('due_day IS NULL OR due_day BETWEEN 1 AND 31',
                           name='ck_commitments_due_day'),
        sa.CheckConstraint("amount_source IN ('stated', 'rolled')",
                           name='ck_commitments_amount_source'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['rolled_from_id'], ['commitments.id']),
        sa.ForeignKeyConstraint(['carried_from_id'], ['commitments.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_commitments_user_month', 'commitments', ['user_id', 'local_month'])
    op.create_index('uq_commitments_rolled', 'commitments', ['rolled_from_id'], unique=True,
                    postgresql_where=sa.text('rolled_from_id IS NOT NULL'))
    op.create_index('uq_commitments_carried', 'commitments', ['carried_from_id'], unique=True,
                    postgresql_where=sa.text('carried_from_id IS NOT NULL'))
    op.add_column('transactions', sa.Column('commitment_id', sa.Text(), nullable=True))
    op.add_column('transactions', sa.Column('commitment_inferred', sa.Boolean(),
                                            server_default='false', nullable=False))
    op.create_foreign_key('fk_transactions_commitment', 'transactions', 'commitments',
                          ['commitment_id'], ['id'])
    op.create_index('ix_transactions_commitment_id', 'transactions', ['commitment_id'])
    from datetime import datetime
    from zoneinfo import ZoneInfo
    backfill(op.get_bind(), datetime.now(ZoneInfo("Asia/Kolkata")).date())


def downgrade() -> None:
    op.drop_index('ix_transactions_commitment_id', table_name='transactions')
    op.drop_constraint('fk_transactions_commitment', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'commitment_inferred')
    op.drop_column('transactions', 'commitment_id')
    op.drop_index('uq_commitments_carried', table_name='commitments')
    op.drop_index('uq_commitments_rolled', table_name='commitments')
    op.drop_index('ix_commitments_user_month', table_name='commitments')
    op.drop_table('commitments')
