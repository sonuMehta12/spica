"""users FKs on the newer tables are TEXT, like everywhere else

Revision ID: b7e2c4a90f15
Revises: 6a1f3d9e7b42
Create Date: 2026-09-04

The four tables created in September declared user_id / created_by_id as
VARCHAR while every older table uses TEXT. Same thing to Postgres, but the
models say TEXT and `alembic check` should be quiet.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e2c4a90f15'
down_revision: Union[str, Sequence[str], None] = '6a1f3d9e7b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLS = [('dish_saves', 'user_id'), ('dishes', 'created_by_id'),
        ('memories', 'user_id'), ('weigh_ins', 'user_id')]


def upgrade() -> None:
    for table, col in COLS:
        op.alter_column(table, col, type_=sa.Text(), existing_type=sa.String())


def downgrade() -> None:
    for table, col in COLS:
        op.alter_column(table, col, type_=sa.String(), existing_type=sa.Text())
