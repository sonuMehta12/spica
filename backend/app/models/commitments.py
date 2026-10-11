"""
What you still owe this month. spec/done/commitments.md.

A commitment is an obligation — rent, an EMI, a loan — and a row the user owns:
made, changed, skipped, repeated and deleted from the page, from chat and from
a payment's tray. It replaces the `fixed` / `repeats` flags on a payment, which
reserved money in a future month that nobody could see or change.

**Paid is never stored.** A payment links to a commitment
(`transactions.commitment_id`) and *paid* and *owed* are worked out when they
are read, so a deleted payment gives the debt back and an edited amount is in
the limit at once.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Envelope

AMOUNT_SOURCES = ("stated", "rolled")


class Commitment(Envelope, Base):
    __tablename__ = "commitments"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    #: The ledger category its payment is filed under — what an automatic link
    #: reads, and nothing else does.
    category: Mapped[str] = mapped_column(Text, nullable=False)
    #: Expected this month. Editable.
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: `stated` — the user set it — or `rolled`, copied from last month, which
    #: is an inferred figure and wears the amber dot until it is stated or paid.
    amount_source: Mapped[str] = mapped_column(Text, nullable=False, server_default="stated")
    #: The first of the month it is owed in.
    local_month: Mapped[date] = mapped_column(Date, nullable=False)
    #: Orders the list and says *due Friday*. It never moves the limit.
    due_day: Mapped[int | None] = mapped_column(SmallInteger)
    #: Comes back next month. On by default: a commitment the user set is
    #: expected again until they say it is not one any more.
    repeats: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    #: *Not this month.* The row stays, owed is 0, and it is not carried.
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: The repeating line this was copied from — unique, so reading the month
    #: twice rolls it once.
    rolled_from_id: Mapped[str | None] = mapped_column(Text, ForeignKey("commitments.id"))
    #: The line whose unpaid remainder this is.
    carried_from_id: Mapped[str | None] = mapped_column(Text, ForeignKey("commitments.id"))

    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="ck_commitments_amount_positive"),
        CheckConstraint("due_day IS NULL OR due_day BETWEEN 1 AND 31",
                        name="ck_commitments_due_day"),
        CheckConstraint("amount_source IN ('stated', 'rolled')",
                        name="ck_commitments_amount_source"),
        Index("ix_commitments_user_month", "user_id", "local_month"),
        # Not scoped to live rows: a line the user deleted must not roll back
        # into the month the next time it is read.
        Index("uq_commitments_rolled", "rolled_from_id", unique=True,
              postgresql_where=text("rolled_from_id IS NOT NULL")),
        Index("uq_commitments_carried", "carried_from_id", unique=True,
              postgresql_where=text("carried_from_id IS NOT NULL")),
    )
