"""transactions: fixed and repeats — the user's flags on the row

Revision ID: 5c2d7e9f1b34
Revises: 4b1c9e7d2a10
Create Date: 2026-09-04

'fixed' was a tag set by the import and flipped by nobody. It becomes two
boolean columns the user flips: fixed (never spendable) and repeats (goes again
next month). The tagged rows become fixed + repeats and lose the tag.
spec/in-progress/fixed-costs.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '5c2d7e9f1b34'
down_revision: str | Sequence[str] | None = '4b1c9e7d2a10'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('transactions', sa.Column('fixed', sa.Boolean(), server_default='false', nullable=False))  # noqa: E501
    op.add_column('transactions', sa.Column('repeats', sa.Boolean(), server_default='false', nullable=False))  # noqa: E501
    op.execute(
        "UPDATE transactions SET fixed = true, repeats = true, tags = array_remove(tags, 'fixed') "
        "WHERE 'fixed' = ANY(tags)"
    )


def downgrade() -> None:
    op.execute("UPDATE transactions SET tags = array_append(tags, 'fixed') WHERE fixed AND NOT ('fixed' = ANY(tags))")  # noqa: E501
    op.drop_column('transactions', 'repeats')
    op.drop_column('transactions', 'fixed')
