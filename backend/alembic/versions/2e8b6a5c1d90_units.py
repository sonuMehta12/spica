"""foods.unit — grams, millilitres or pieces

Revision ID: 2e8b6a5c1d90
Revises: 9f4d1c8ba207
Create Date: 2026-09-04

Eggs come by the dozen, milk in millilitres, atta in grams. Storing everything
as grams meant the prompt asked for grams even for eggs, and a made-up weight
per egg would sit in the ledger as if it had been observed.

So the ledger stores **what you actually count**, and the food says which unit
that is. The columns lose their `_g` suffix because they are no longer always
grams. `grams_per_unit` is there for macro maths later — macros are per 100 g —
and is nullable, because an unknown weight is not a zero one.

A dozen is not a unit: it is twelve pieces, and the input accepts it as
shorthand. Storing dozens would make six eggs 0.5 of something.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '2e8b6a5c1d90'
down_revision: str | Sequence[str] | None = '9f4d1c8ba207'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The imported foods whose natural unit is not grams.
UNITS = {
    'piece': {'Eggs': 50, 'Banana': 100, 'Apple': 180, 'Mango': 200},
    'ml': {'Milk': 1.03, 'Cooking oil': 0.92},
}


def upgrade() -> None:
    op.add_column('foods', sa.Column('unit', sa.String(length=8), server_default='g', nullable=False))  # noqa: E501
    op.add_column('foods', sa.Column('grams_per_unit', sa.Numeric(precision=8, scale=2), nullable=True))  # noqa: E501
    op.create_check_constraint('ck_foods_unit', 'foods', "unit IN ('g','ml','piece')")

    op.alter_column('pantry_moves', 'quantity_g', new_column_name='quantity')
    op.alter_column('dish_items', 'grams', new_column_name='quantity')
    op.alter_column('meal_items', 'grams', new_column_name='quantity')

    conn = op.get_bind()
    for unit, foods in UNITS.items():
        for name, grams in foods.items():
            conn.execute(
                sa.text("UPDATE foods SET unit = :u, grams_per_unit = :g WHERE name = :n"),
                {"u": unit, "g": grams, "n": name},
            )
    # The imported quantities were grams. Convert the ones whose unit changed,
    # so 600 g of eggs reads as 12 eggs rather than 600 of them.
    conn.execute(sa.text("""
        UPDATE pantry_moves m SET quantity = round(m.quantity / f.grams_per_unit)
        FROM foods f WHERE f.id = m.food_id AND f.unit <> 'g' AND f.grams_per_unit > 0
    """))
    for table in ('dish_items', 'meal_items'):
        conn.execute(sa.text(f"""
            UPDATE {table} t SET quantity = greatest(1, round(t.quantity / f.grams_per_unit))
            FROM foods f WHERE f.id = t.food_id AND f.unit <> 'g' AND f.grams_per_unit > 0
              AND t.quantity IS NOT NULL
        """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE pantry_moves m SET quantity = round(m.quantity * f.grams_per_unit)
        FROM foods f WHERE f.id = m.food_id AND f.unit <> 'g' AND f.grams_per_unit > 0
    """))
    op.alter_column('meal_items', 'quantity', new_column_name='grams')
    op.alter_column('dish_items', 'quantity', new_column_name='grams')
    op.alter_column('pantry_moves', 'quantity', new_column_name='quantity_g')
    op.drop_constraint('ck_foods_unit', 'foods')
    op.drop_column('foods', 'grams_per_unit')
    op.drop_column('foods', 'unit')
