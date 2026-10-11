"""places: what a pin is, and where a payment's fix lives

Revision ID: b8d35f27ca91
Revises: a71f4e9c2b58
Create Date: 2026-09-07

`places` has existed since the paisa data model with eleven columns and no
rows, because it waited for a location source. Five more columns and a way to
drop a pin by hand give it a first row. spec/in-progress/places.md.

The other half reverses an earlier decision. A payment's raw coordinates were
to live in `predictions.signals`; `predictions` is the agent's guess-log, so a
payment it never guessed about has no row and its fix has nowhere to go — and a
payment at an unknown spot is exactly what discovers a place by repeating. The
fix belongs on the transaction, which is where *what happened* lives, and a
wrong match stays redoable because `place_id` can be cleared and recomputed
from the coordinates sitting beside it.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b8d35f27ca91'
down_revision: str | Sequence[str] | None = 'a71f4e9c2b58'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = ('home', 'office', 'shop', 'eat', 'hangout', 'pickup', 'gym', 'other')


def upgrade() -> None:
    op.add_column('places', sa.Column('kind', sa.Text(), nullable=True))
    op.add_column('places', sa.Column('counterparty_id', sa.String(length=26), nullable=True))
    op.add_column('places', sa.Column('note', sa.Text(), nullable=True))
    op.add_column('places',
                  sa.Column('source', sa.Text(), server_default='manual', nullable=False))
    op.add_column('places', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('fk_places_counterparty', 'places', 'counterparties',
                          ['counterparty_id'], ['id'])
    op.create_check_constraint(
        'ck_places_kind', 'places',
        "kind IS NULL OR kind IN ({})".format(", ".join(f"'{k}'" for k in KINDS)))
    op.create_check_constraint(
        'ck_places_source', 'places', "source IN ('manual','search','detected')")

    # Where the phone was when money moved. Not a guess — an observation, which
    # is what the ledger is for.
    op.add_column('transactions', sa.Column('lat', sa.Float(), nullable=True))
    op.add_column('transactions', sa.Column('lng', sa.Float(), nullable=True))
    op.add_column('transactions', sa.Column('fix_accuracy_m', sa.Float(), nullable=True))
    op.create_check_constraint(
        'ck_transactions_fix', 'transactions',
        # Both or neither: half a coordinate is not a location.
        '(lat IS NULL) = (lng IS NULL) AND (fix_accuracy_m IS NULL OR fix_accuracy_m > 0)')


def downgrade() -> None:
    op.drop_constraint('ck_transactions_fix', 'transactions', type_='check')
    for col in ('fix_accuracy_m', 'lng', 'lat'):
        op.drop_column('transactions', col)
    op.drop_constraint('ck_places_source', 'places', type_='check')
    op.drop_constraint('ck_places_kind', 'places', type_='check')
    op.drop_constraint('fk_places_counterparty', 'places', type_='foreignkey')
    for col in ('confirmed_at', 'source', 'note', 'counterparty_id', 'kind'):
        op.drop_column('places', col)
