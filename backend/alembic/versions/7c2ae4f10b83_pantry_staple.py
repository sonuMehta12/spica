"""pantry.staple — always in the house, or something you count

Revision ID: 7c2ae4f10b83
Revises: 4b1c9e7d2a10
Create Date: 2026-09-04

Which foods are staples cannot be derived: a food with no purchase might be the
family's atta, or eggs you simply have not logged yet. Only the user knows, so
the flag is theirs. spec/done/pantry-view.md.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7c2ae4f10b83'
down_revision: Union[str, Sequence[str], None] = '5c2d7e9f1b34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The imported set, classified by the user (2026-09-04). Everything else keeps
# the old derivation: no purchase ever logged meant "always here".
TRACKED_ANYWAY = (
    "Carrot", "Eggs / chicken (bahar)", "Whey protein", "Mango",
    "Baingan / seasonal sabzi", "Green vegetable (1-2)",
)


def upgrade() -> None:
    op.add_column('pantry', sa.Column('staple', sa.Boolean(), server_default='false', nullable=False))
    conn = op.get_bind()
    # Start from the behaviour the app already had: nothing ever bought = staple.
    conn.execute(sa.text("""
        UPDATE pantry p SET staple = true
        WHERE NOT EXISTS (
            SELECT 1 FROM pantry_moves m
            WHERE m.food_id = p.food_id AND m.user_id = p.user_id
              AND m.deleted_at IS NULL AND m.kind IN ('purchase','opening')
        )
    """))
    # Then the user's corrections: these cycle, they are just unlogged.
    conn.execute(
        sa.text("UPDATE pantry SET staple = false WHERE food_id IN "
                "(SELECT id FROM foods WHERE name = ANY(:names))"),
        {"names": list(TRACKED_ANYWAY)},
    )


def downgrade() -> None:
    op.drop_column('pantry', 'staple')
