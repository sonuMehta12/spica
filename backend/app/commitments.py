"""
What you still owe, worked out. spec/done/commitments.md.

One module so the page, the limit, the agent and the morning brief cannot
disagree about a number: they all read `lines()` / `compute()`.

    paid   = Σ payments linked to the commitment
    owed   = 0                          when skipped
           = max(0, amount − paid)      otherwise
           — and for a carried line, no more than what its source still owes,
             so paying last month's rent late clears the carry too

Nothing about *paid* or *owed* is stored: a deleted payment gives the debt
back, an edited amount is in the limit at once.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import new_id
from app.models.commitments import Commitment
from app.models.paisa import Transaction

IST = ZoneInfo("Asia/Kolkata")


def today_local() -> date:
    return datetime.now(IST).date()


def month_of(d: date) -> date:
    return d.replace(day=1)


def prev_month_of(d: date) -> date:
    return month_of(month_of(d) - timedelta(days=1))


def due_date(month: date, due_day: int | None) -> date | None:
    """The day it falls due; the 31st in February is the 28th (29th)."""
    if due_day is None:
        return None
    last = calendar.monthrange(month.year, month.month)[1]
    return month.replace(day=min(due_day, last))


@dataclass
class Line:
    """One commitment, with what has been paid against it."""

    c: Commitment
    paid_paise: int
    owed_paise: int
    #: Payments linked to it that were only guessed from the category.
    inferred_links: int = 0
    #: For a carried line, the month it is the remainder of.
    carried_from_month: date | None = None

    @property
    def skipped(self) -> bool:
        return self.c.skipped_at is not None

    @property
    def settled(self) -> bool:
        return not self.skipped and self.owed_paise == 0

    @property
    def over_paise(self) -> int:
        return max(0, self.paid_paise - self.c.amount_paise)

    @property
    def kind(self) -> str:
        """Where the line came from: `carried`, `rolled`, or `manual` — made by
        the user, or by a payment's tray."""
        if self.c.carried_from_id:
            return "carried"
        if self.c.rolled_from_id:
            return "rolled"
        return "manual"


def compute(commitments: list[Commitment], payments: list[Transaction]) -> dict[str, Line]:
    """Every commitment with its paid and owed, from the rows given.

    `payments` is whatever is in scope — the caller passes the live rows up to
    the day being asked about, so a limit worked out *as of* a day does not see
    a payment made after it. Oldest month first, so a carried line can read its
    source's owed.
    """
    paid: dict[str, int] = {}
    guessed: dict[str, int] = {}
    for t in payments:
        if t.commitment_id and t.deleted_at is None and t.kind == "expense":
            paid[t.commitment_id] = paid.get(t.commitment_id, 0) + t.amount_paise
            if t.commitment_inferred:
                guessed[t.commitment_id] = guessed.get(t.commitment_id, 0) + 1

    months = {c.id: c.local_month for c in commitments}
    out: dict[str, Line] = {}
    for c in sorted(commitments, key=lambda c: (c.local_month, c.created_at, c.id)):
        if c.deleted_at is not None:
            continue
        p = paid.get(c.id, 0)
        owed = 0 if c.skipped_at is not None else max(0, c.amount_paise - p)
        if c.carried_from_id:
            src = out.get(c.carried_from_id)
            # A carry follows what its source still owes; a source that is gone
            # (deleted) or was never loaded owes nothing.
            owed = min(owed, src.owed_paise if src else 0)
        out[c.id] = Line(c, p, owed, guessed.get(c.id, 0),
                         months.get(c.carried_from_id) if c.carried_from_id else None)
    return out


async def _all(session: AsyncSession, user: str) -> list[Commitment]:
    return list((await session.scalars(
        select(Commitment).where(Commitment.user_id == user, Commitment.deleted_at.is_(None))
        .order_by(Commitment.local_month, Commitment.created_at)
    )).all())


async def _linked(session: AsyncSession, user: str, upto: date | None = None) -> list[Transaction]:
    q = select(Transaction).where(
        Transaction.user_id == user, Transaction.deleted_at.is_(None),
        Transaction.commitment_id.is_not(None))
    if upto is not None:
        q = q.where(Transaction.local_day <= upto)
    return list((await session.scalars(q)).all())


async def roll_month(session: AsyncSession, user: str, month: date) -> None:
    """Bring last month forward, once — the first time the current month is
    read. Past and future months are never touched.

    A line that repeats is copied with what was paid (else what was expected),
    marked `rolled`. What last month left unpaid comes forward as its own line,
    for the remainder only. Both are keyed on the row they came from, so two
    reads, or two devices, roll once; a line the user deleted stays deleted.
    """
    if month != month_of(today_local()):
        return
    prev = prev_month_of(month)
    every = await _all(session, user)
    lines = compute(every, await _linked(session, user))
    # Everything ever rolled or carried from, deleted or not — a deleted line
    # must not come back.
    seen_rolled = set((await session.scalars(
        select(Commitment.rolled_from_id).where(Commitment.user_id == user,
                                                Commitment.rolled_from_id.is_not(None)))).all())
    seen_carried = set((await session.scalars(
        select(Commitment.carried_from_id).where(Commitment.user_id == user,
                                                 Commitment.carried_from_id.is_not(None)))).all())
    for ln in lines.values():
        c = ln.c
        if c.local_month != prev:
            continue
        if c.repeats and c.id not in seen_rolled:
            amount = ln.paid_paise if ln.paid_paise > 0 else c.amount_paise
            await _insert_once(session, dict(
                id=new_id(), user_id=user, name=c.name, category=c.category,
                amount_paise=amount, amount_source="rolled", local_month=month,
                due_day=c.due_day, repeats=True, rolled_from_id=c.id))
        if not ln.skipped and ln.owed_paise > 0 and c.id not in seen_carried:
            await _insert_once(session, dict(
                id=new_id(), user_id=user, name=c.name, category=c.category,
                amount_paise=ln.owed_paise, amount_source="stated", local_month=month,
                due_day=None, repeats=False, carried_from_id=c.id))
    await session.flush()


async def _insert_once(session: AsyncSession, values: dict) -> None:
    """Insert, or do nothing if another reader got there first."""
    key = "rolled_from_id" if values.get("rolled_from_id") else "carried_from_id"
    stmt = pg_insert(Commitment).values(**values).on_conflict_do_nothing(
        index_elements=[key], index_where=Commitment.__table__.c[key].is_not(None))
    await session.execute(stmt)


async def lines(session: AsyncSession, user: str, month: date) -> list[Line]:
    """One month's commitments, for the page — rolling the current month first.
    Skipped last, settled after owed, by due day within each."""
    month = month_of(month)
    await roll_month(session, user, month)
    every = await _all(session, user)
    computed = compute(every, await _linked(session, user))
    mine = [computed[c.id] for c in every if c.local_month == month]
    mine.sort(key=lambda ln: (ln.skipped, ln.settled, ln.c.due_day or 99,
                              -ln.c.amount_paise, ln.c.id))
    return mine


async def commitments_for_limit(session: AsyncSession, user: str, on: date,
                                payments_upto: list[Transaction]) -> list[Line]:
    """The month's lines, as of `on`, for the limit: paid counts only payments
    up to that day."""
    month = month_of(on)
    await roll_month(session, user, month)
    every = await _all(session, user)
    computed = compute(every, [t for t in payments_upto if t.commitment_id])
    return [computed[c.id] for c in every if c.local_month == month]


def owed_total(ls: list[Line]) -> int:
    return sum(ln.owed_paise for ln in ls)


# ─── linking a payment ───────────────────────────────────────────────────────

async def candidates(session: AsyncSession, user: str, row: Transaction) -> list[Line]:
    """The open commitments in the payment's own month and category, the way
    FIFO would take them: a carried line before this month's own, then the
    earlier due day. Open means owed above 0 and not skipped."""
    month = month_of(row.local_day)
    every = await _all(session, user)
    computed = compute(every, await _linked(session, user))
    cat = row.category.strip().lower()
    mine = [computed[c.id] for c in every
            if c.local_month == month and c.category.strip().lower() == cat
            and computed[c.id].owed_paise > 0 and not computed[c.id].skipped]
    mine.sort(key=lambda ln: (ln.c.carried_from_id is None, ln.c.due_day or 99,
                              ln.c.created_at, ln.c.id))
    return mine


async def auto_link(session: AsyncSession, user: str, row: Transaction) -> Commitment | None:
    """Link a new expense to the commitment it most likely pays, marking the
    link as a guess. A payment whose own words name one commitment goes to that
    one; otherwise the first open one in its category. None when there is none —
    it stays ordinary spending."""
    if row.kind != "expense" or row.commitment_id:
        return None
    await session.flush()
    options = await candidates(session, user, row)
    if not options:
        return None
    words = f"{row.description} {row.counterparty_name or ''}".lower()
    named = [ln for ln in options if ln.c.name.strip().lower() in words]
    chosen = (named or options)[0].c
    row.commitment_id = chosen.id
    row.commitment_inferred = True
    return chosen


async def unlink_payments(session: AsyncSession, commitment_id: str) -> int:
    """A commitment was deleted: its payments become ordinary spending again."""
    res = await session.execute(
        update(Transaction).where(Transaction.commitment_id == commitment_id)
        .values(commitment_id=None, commitment_inferred=False))
    return res.rowcount or 0


# ─── what is due soon ────────────────────────────────────────────────────────

async def due_soon(session: AsyncSession, user: str, today: date, days: int = 3) -> list[Line]:
    """Lines with a due day inside the next `days` days, still owed, not
    skipped — for Your day. A line the person never dated is not announced."""
    ls = await lines(session, user, month_of(today))
    out = []
    for ln in ls:
        d = due_date(ln.c.local_month, ln.c.due_day)
        if d is None or ln.skipped or ln.owed_paise <= 0:
            continue
        if today <= d <= today + timedelta(days=days):
            out.append(ln)
    out.sort(key=lambda ln: due_date(ln.c.local_month, ln.c.due_day))
    return out
