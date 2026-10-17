"""project colours from the Work hue, not the pre-Jamun palette

Every project's stored colour on the old palette moves to the new one at the
same position, so projects keep their order of colour; the default project's
green-grey becomes the Jamun-leaning neutral. A colour someone picked by hand
(not on the old palette) is theirs and stays.

Revision ID: a1c3e5f7b9d2
Revises: 20d535354209
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'a1c3e5f7b9d2'
down_revision: str | Sequence[str] | None = '20d535354209'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ("#16604A", "#C98A16", "#A6412E", "#8A5E0B", "#1D7A5E", "#5A6158", "#7A8578")
NEW = ("#286CAB", "#3A95CD", "#285388", "#1785AF", "#6588B6", "#2E6386", "#5E93CA")
OLD_GREY, NEW_GREY = "#7A8578", "#747073"


def _move(pairs) -> None:
    for old, new in pairs:
        op.execute(sa.text("UPDATE projects SET color = :new WHERE upper(color) = upper(:old)")
                   .bindparams(old=old, new=new))


def upgrade() -> None:
    # The default project first: its grey is also the old palette's last colour.
    op.execute(sa.text("UPDATE projects SET color = :new WHERE is_default AND upper(color) = upper(:old)")
               .bindparams(old=OLD_GREY, new=NEW_GREY))
    _move(zip(OLD, NEW))


def downgrade() -> None:
    op.execute(sa.text("UPDATE projects SET color = :old WHERE is_default AND upper(color) = upper(:new)")
               .bindparams(old=OLD_GREY, new=NEW_GREY))
    _move(zip(NEW, OLD))
