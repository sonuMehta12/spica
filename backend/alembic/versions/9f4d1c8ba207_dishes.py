"""dishes, dish_items, meal_items, dish_saves — recipes reborn

Revision ID: 9f4d1c8ba207
Revises: 7c2ae4f10b83
Create Date: 2026-09-04

The 37 recipe rows are dropped: 23 were portions (1 roti, 1 katori dal), which
are a food plus a measure, and the rest are being rewritten as dishes from the
user's own meal logs. Nothing referenced them — meal_logs.recipe_id is empty on
every row. spec/in-progress/dishes.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '9f4d1c8ba207'
down_revision: str | Sequence[str] | None = '7c2ae4f10b83'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRAMS = sa.Numeric(precision=6, scale=1)


def upgrade() -> None:
    op.create_table(
        'dishes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('aliases', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
        sa.Column('meal_type', sa.Text(), nullable=True),
        sa.Column('serving_label', sa.Text(), nullable=False),
        sa.Column('kcal', sa.Integer(), nullable=True),
        sa.Column('protein_g', GRAMS, nullable=False),
        sa.Column('carbs_g', GRAMS, nullable=True),
        sa.Column('fat_g', GRAMS, nullable=True),
        sa.Column('fibre_g', GRAMS, nullable=True),
        sa.Column('minutes', sa.Integer(), nullable=True),
        sa.Column('needs_prep_ahead', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('steps', sa.Text(), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.String(), nullable=True),
        sa.Column('visibility', sa.String(length=8), server_default='private', nullable=False),
        sa.Column('forked_from_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("visibility IN ('private','public')", name='ck_dishes_visibility'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['forked_from_id'], ['dishes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    # The fuzzy rung of the resolution ladder (spec § How a spoken meal becomes
    # lines). Same index the counterparties table uses for payee matching.
    op.create_index('ix_dishes_name_trgm', 'dishes', ['name'],
                    postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})

    op.create_table(
        'dish_items',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('dish_id', sa.String(), nullable=False),
        sa.Column('food_id', sa.String(), nullable=True),
        sa.Column('component_dish_id', sa.String(), nullable=True),
        sa.Column('grams', sa.Integer(), nullable=True),
        sa.Column('servings', sa.Numeric(precision=4, scale=1), server_default='1', nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('(food_id IS NULL) <> (component_dish_id IS NULL)', name='ck_dish_items_one_target'),  # noqa: E501
        sa.ForeignKeyConstraint(['dish_id'], ['dishes.id']),
        sa.ForeignKeyConstraint(['food_id'], ['foods.id']),
        sa.ForeignKeyConstraint(['component_dish_id'], ['dishes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_dish_items_dish', 'dish_items', ['dish_id'])

    op.create_table(
        'meal_items',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('meal_log_id', sa.String(), nullable=False),
        sa.Column('dish_id', sa.String(), nullable=True),
        sa.Column('food_id', sa.String(), nullable=True),
        sa.Column('servings', sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column('grams', sa.Integer(), nullable=True),
        sa.Column('said', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('(dish_id IS NULL) <> (food_id IS NULL)', name='ck_meal_items_one_target'),  # noqa: E501
        sa.ForeignKeyConstraint(['meal_log_id'], ['meal_logs.id']),
        sa.ForeignKeyConstraint(['dish_id'], ['dishes.id']),
        sa.ForeignKeyConstraint(['food_id'], ['foods.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_meal_items_meal', 'meal_items', ['meal_log_id'])
    # 'How many times have I had this' is a count over these.
    op.create_index('ix_meal_items_dish', 'meal_items', ['dish_id'])

    op.create_table(
        'dish_saves',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('dish_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['dish_id'], ['dishes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_dish_saves_user_dish', 'dish_saves', ['user_id', 'dish_id'], unique=True,
                    postgresql_where=sa.text('deleted_at IS NULL'))

    # recipe_id assumed one dish per meal; a plate is three lines.
    op.drop_column('meal_logs', 'recipe_id')
    op.drop_table('recipe_items')
    op.drop_table('recipes')


def downgrade() -> None:
    raise NotImplementedError(
        "one-way: the recipes rows were portions and are not coming back")
