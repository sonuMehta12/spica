"""dishes and exercises: a picture's credit, and when one was looked for

Revision ID: d2f7a9c41e85
Revises: c3e9a1f7d2b4
Create Date: 2026-10-08 13:10:00

spec/in-progress/today-plan.md. `image_url` has existed on both tables since
they were made and nothing ever filled it. A picture now comes from Wikimedia
Commons under a free licence, and showing one means showing whose it is:
`image_credit`. `image_looked_at` is when a lookup last ran, so a name Commons
has nothing for is not searched again on every open.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd2f7a9c41e85'
down_revision: Union[str, Sequence[str], None] = 'c3e9a1f7d2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ('dishes', 'exercises'):
        op.add_column(table, sa.Column('image_credit', sa.Text(), nullable=True))
        op.add_column(table, sa.Column('image_looked_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in ('dishes', 'exercises'):
        op.drop_column(table, 'image_looked_at')
        op.drop_column(table, 'image_credit')
