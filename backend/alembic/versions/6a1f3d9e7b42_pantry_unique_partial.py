"""pantry: the one-row-per-food rule ignores untracked rows

Revision ID: 6a1f3d9e7b42
Revises: 2e8b6a5c1d90
Create Date: 2026-09-04

Stop tracking soft-deletes the row; tracking the same food again must then be
allowed. A plain UNIQUE(user_id, food_id) refused it — Banana could not come
back after the fruit pass. Partial, like every other uniqueness in this schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6a1f3d9e7b42'
down_revision: Union[str, Sequence[str], None] = '2e8b6a5c1d90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_pantry_user_food', 'pantry', type_='unique')
    op.create_index('uq_pantry_user_food', 'pantry', ['user_id', 'food_id'], unique=True,
                    postgresql_where=sa.text('deleted_at IS NULL'))


def downgrade() -> None:
    op.drop_index('uq_pantry_user_food', table_name='pantry')
    op.create_unique_constraint('uq_pantry_user_food', 'pantry', ['user_id', 'food_id'])
