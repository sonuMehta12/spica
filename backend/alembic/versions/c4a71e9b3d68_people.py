"""counterparties: kind, relation, note — and whether we were told or guessed

Revision ID: c4a71e9b3d68
Revises: b7e2c4a90f15
Create Date: 2026-09-05

A counterparty was a key: a name to match the next payment against. It is also
the only place a fact about a *person* can live once — put `relation` on
`transactions` and twelve payments to one friend hold twelve copies that can
disagree. spec/in-progress/people.md.

`source` and `confirmed_at` are the pair `memories` already carries, with the
same meaning: inferred is marked, confirmed is not. Both are nullable, because
a counterparty is born from a payment and nobody has said anything about it yet
— a default of 'user' would have thirteen rows claiming the user wrote
something they never wrote.

The one inference made here: money that came back means a person. Shops do not
repay. Written as `source = 'agent'` and left unconfirmed, so it shows on screen
as a guess until the user taps it.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c4a71e9b3d68'
down_revision: str | Sequence[str] | None = 'b7e2c4a90f15'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('counterparties', sa.Column('kind', sa.Text(), nullable=True))
    op.add_column('counterparties', sa.Column('relation', sa.Text(), nullable=True))
    op.add_column('counterparties', sa.Column('note', sa.Text(), nullable=True))
    op.add_column('counterparties', sa.Column('source', sa.Text(), nullable=True))
    op.add_column('counterparties',
                  sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        'ck_counterparties_kind', 'counterparties',
        "kind IS NULL OR kind IN ('person','shop','service')")
    op.create_check_constraint(
        'ck_counterparties_source', 'counterparties',
        "source IS NULL OR source IN ('user','agent','contacts')")

    # The only signal that is never wrong. Everything else — the payee name
    # above all — a notification renders the same for a sister and a paan shop.
    op.get_bind().execute(sa.text("""
        UPDATE counterparties SET kind = 'person', source = 'agent'
        WHERE is_peer = true AND deleted_at IS NULL AND kind IS NULL
    """))


def downgrade() -> None:
    op.drop_constraint('ck_counterparties_source', 'counterparties', type_='check')
    op.drop_constraint('ck_counterparties_kind', 'counterparties', type_='check')
    for col in ('confirmed_at', 'source', 'note', 'relation', 'kind'):
        op.drop_column('counterparties', col)
