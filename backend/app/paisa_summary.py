"""
The month's numbers, computed once, on the server.

Until 2026-09-12 the daily spend limit lived in the frontend hook
(`dailySpendLimit()`), and the agent needed the same number. Two computations of
one figure is how the screen and the agent start disagreeing, so the maths moved
here: **one function, two callers** — `GET /paisa/summary` for the deck and the
report, and the `paisa_report` tool for the agent, in-process.

`/deck` stays rows-only (spec/done/deck-api.md § rows, never aggregates); this
is the derived set, asked for by name. Every field is exactly what the Paisa
card already showed, with the same rule for each:

    pool   = income + repaid + borrowed − committed − spent − lent − paid_back
    locked = what this month's commitments still owe (`app/commitments.py`)
           + borrowings from earlier months still owed
    limit  = (pool − locked − savings_target) ÷ days_left     may be negative

A payment linked to a commitment is *committed*, not *spent*. With no income yet
this month, a limit that would be negative is unknown, not overspending.

spec/done/commitments.md · spec/in-progress/agent-tools.md.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import commitments as K
from app.models.paisa import Counterparty, Transaction
from app.models.users import User

FIELDS = frozenset({
    "spent", "income", "daily_avg", "days_in_range", "within_limit", "limit_today",
    "balance", "commitments", "udhaar", "fixed", "by_day", "by_category",
    "by_counterparty", "rows", "to_review",
})
ROWS_CAP = 30


def month_start(d: date) -> date:
    return d.replace(day=1)


def prev_month(d: date) -> tuple[date, date]:
    first = month_start(d)
    last_prev = first - timedelta(days=1)
    return month_start(last_prev), last_prev


async def _live(session: AsyncSession, user: str, lo: date | None, hi: date) -> list[Transaction]:
    clauses = [Transaction.user_id == user, Transaction.deleted_at.is_(None),
               Transaction.local_day <= hi]
    if lo is not None:
        clauses.append(Transaction.local_day >= lo)
    return list((await session.scalars(
        select(Transaction).where(*clauses).order_by(Transaction.local_day, Transaction.id)
    )).all())


def _sum(rows, pred) -> int:
    return sum(t.amount_paise for t in rows if pred(t))


def committed(t: Transaction) -> bool:
    """A payment that pays an obligation — not discretionary spend."""
    return t.commitment_id is not None


def limit_as_of(month_rows: list[Transaction], all_rows: list[Transaction],
                lines: list[K.Line], savings_target: int, on: date) -> dict:
    """The Paisa card's limit for `on`, from the month's rows up to that day.

    `all_rows` is everything up to `on` (for repayments settling older
    borrowings); `lines` is this month's commitments, paid as of `on`.
    """
    income = _sum(month_rows, lambda t: t.kind == "income")
    fixed_paid = _sum(month_rows, lambda t: t.kind == "expense" and committed(t))
    spent = _sum(month_rows, lambda t: t.kind == "expense" and not committed(t))
    lent = _sum(month_rows, lambda t: t.kind == "lent")
    borrowed = _sum(month_rows, lambda t: t.kind == "borrowed")
    repaid = _sum(month_rows, lambda t: t.kind == "repayment" and t.direction == "credit")
    paid_back = _sum(month_rows, lambda t: t.kind == "repayment" and t.direction == "debit")
    pool = income + repaid + borrowed - fixed_paid - spent - lent - paid_back

    # Locked, part 1: what this month's commitments still owe.
    owed_commitments = K.owed_total(lines)
    # Locked, part 2: a borrowing from an earlier month still owed is a cost of
    # this one.
    settled: dict[str, int] = defaultdict(int)
    for t in all_rows:
        if t.kind == "repayment" and t.settles_id:
            settled[t.settles_id] += t.amount_paise
    owed_older = sum(
        max(0, t.amount_paise - settled[t.id])
        for t in all_rows
        if t.kind == "borrowed" and t.local_day < month_start(on)
    )
    locked = owed_commitments + owed_older

    days_left = calendar.monthrange(on.year, on.month)[1] - on.day + 1
    raw = round((pool - locked - savings_target) / days_left)
    # Before the month's first income the pool is just what the commitments are
    # waiting for: a negative limit there reads as overspending when nothing has
    # been spent. Unknown, not zero.
    limit = None if (income == 0 and raw < 0) else raw
    spent_today = _sum(month_rows, lambda t: t.kind == "expense" and not committed(t)
                       and t.local_day == on)
    return {
        "limit_paise": limit, "spent_today_paise": spent_today,
        "left_paise": None if limit is None else limit - spent_today,
        "pool_paise": pool, "locked_paise": locked,
        "fixed_paid_paise": fixed_paid, "days_left": days_left,
        "savings_target_paise": savings_target,
    }


async def paisa_summary(session: AsyncSession, user: str, frm: date, to: date,
                        fields: set[str], *, category: str | None = None,
                        counterparty_id: str | None = None, rows_limit: int = ROWS_CAP,
                        after: str | None = None) -> dict:
    """Only the keys asked for. A field the caller did not name is absent, so
    nothing can be read off it by accident."""
    unknown = fields - FIELDS
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")

    rows = await _live(session, user, frm, to)
    if category:
        # Case-insensitive on purpose: a model that writes "transport" for
        # "Transport" should get the answer, not a confident zero. The prompt
        # lists the real names; this is the belt to that's braces.
        needle = category.strip().lower()
        rows = [t for t in rows if t.category.lower() == needle]
    if counterparty_id:
        rows = [t for t in rows if t.counterparty_id == counterparty_id]
    out: dict = {"from": frm, "to": to}
    days_in_range = (to - frm).days + 1
    spent = _sum(rows, lambda t: t.kind == "expense" and not committed(t))

    if "spent" in fields:
        out["spent_paise"] = spent
    if "income" in fields:
        out["income_paise"] = _sum(rows, lambda t: t.kind == "income")
    if "days_in_range" in fields:
        out["days_in_range"] = days_in_range
    if "daily_avg" in fields:
        out["daily_avg_paise"] = round(spent / days_in_range)
    if "fixed" in fields:
        repeating = {c.id for c in await K._all(session, user) if c.repeats}
        out["fixed"] = {
            "fixed_paise": _sum(rows, lambda t: t.kind == "expense" and committed(t)),
            "repeats_paise": _sum(rows, lambda t: t.kind == "expense" and committed(t)
                                  and t.commitment_id in repeating),
        }
    if "by_day" in fields:
        by_day: dict[date, int] = defaultdict(int)
        for t in rows:
            if t.kind == "expense" and not committed(t):
                by_day[t.local_day] += t.amount_paise
        out["by_day"] = [{"local_day": d, "spent_paise": v} for d, v in sorted(by_day.items())]
    if "by_category" in fields:
        by_cat: dict[str, int] = defaultdict(int)
        for t in rows:
            if t.kind == "expense" and not committed(t):
                by_cat[t.category] += t.amount_paise
        out["by_category"] = [
            {"category": c, "paise": v, "share": (v / spent) if spent else 0.0}
            for c, v in sorted(by_cat.items(), key=lambda kv: -kv[1])
        ]
    if "by_counterparty" in fields:
        by_cp: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for t in rows:
            if t.counterparty_id and t.direction == "debit":
                by_cp[t.counterparty_id][0] += t.amount_paise
                by_cp[t.counterparty_id][1] += 1
        names = {}
        if by_cp:
            names = dict((await session.execute(
                select(Counterparty.id, Counterparty.raw_name)
                .where(Counterparty.id.in_(list(by_cp))))).all())
        out["by_counterparty"] = [
            {"counterparty_id": cid, "name": names.get(cid), "paise": v[0], "n": v[1]}
            for cid, v in sorted(by_cp.items(), key=lambda kv: -kv[1][0])[:20]
        ]

    needs_month = fields & {"limit_today", "within_limit", "udhaar", "balance",
                            "commitments"}
    if needs_month:
        all_rows = await _live(session, user, None, to)
        month_rows = [t for t in all_rows if t.local_day >= month_start(to)]
        target = await session.scalar(select(User.savings_target_paise).where(User.id == user))
        month_lines = await K.commitments_for_limit(session, user, to, all_rows)
        lim = limit_as_of(month_rows, all_rows, month_lines, int(target or 0), to)
        if "limit_today" in fields:
            out["limit_today"] = lim
        if "commitments" in fields:
            # What is owed this month, line by line — commitments the user owns,
            # then borrowings worked out live from the udhaar ledger. The lines
            # add up to `locked_paise` exactly: a breakdown that disagreed with
            # the card would be the same bug again. `fixed` is what has already
            # been PAID, the opposite set — see the prompt.
            items = []
            for ln in sorted(month_lines, key=lambda x: (x.skipped, x.settled,
                                                          x.c.due_day or 99, -x.c.amount_paise)):
                c = ln.c
                items.append({
                    "id": c.id, "name": c.name, "source": "commitment",
                    "origin": ln.kind, "category": c.category,
                    "expected_paise": c.amount_paise, "paid_paise": ln.paid_paise,
                    "owed_paise": ln.owed_paise, "over_paise": ln.over_paise,
                    "settled": ln.settled, "skipped": ln.skipped,
                    "due_day": c.due_day, "repeats": c.repeats,
                    "amount_source": c.amount_source,
                    "inferred_links": ln.inferred_links,
                    "carried_from_month": ln.carried_from_month,
                })
            settled_ids: dict[str, int] = defaultdict(int)
            for t in all_rows:
                if t.kind == "repayment" and t.settles_id:
                    settled_ids[t.settles_id] += t.amount_paise
            for t in all_rows:
                if t.kind == "borrowed" and t.local_day < month_start(to):
                    owed = max(0, t.amount_paise - settled_ids[t.id])
                    if owed:
                        items.append({
                            "id": t.id, "name": t.counterparty_name or t.description,
                            "source": "borrowing", "origin": "borrowing",
                            "category": t.category,
                            "expected_paise": t.amount_paise,
                            "paid_paise": settled_ids[t.id],
                            "owed_paise": owed, "over_paise": 0,
                            "settled": False, "skipped": False, "due_day": None,
                            "repeats": False, "amount_source": "stated",
                            "inferred_links": 0, "carried_from_month": None,
                        })
            out["commitments"] = {
                "month": month_start(to),
                "owed_paise": sum(i["owed_paise"] for i in items),
                "settled_paise": sum(i["paid_paise"] for i in items if i["settled"]),
                "items": items,
            }
        if "balance" in fields:
            # "How much do I have left?" as one answer, already worked out.
            #
            # Asked this, the agent used to fetch `spent` and `income` and
            # subtract — and `spent` is discretionary expenses only, so fixed
            # costs, lendings and repayments all vanished from its arithmetic.
            # It reported ₹1,29,149 against a true ₹59,149. A number the user
            # asks for in one sentence must not be assembled from parts whose
            # exclusions are not in their names.
            in_ = _sum(month_rows, lambda t: t.kind == "income")
            back = _sum(month_rows, lambda t: t.kind == "repayment"
                        and t.direction == "credit")
            borrowed = _sum(month_rows, lambda t: t.kind == "borrowed")
            out_ = _sum(month_rows, lambda t: t.kind == "expense")
            lent = _sum(month_rows, lambda t: t.kind == "lent")
            paid_back = _sum(month_rows, lambda t: t.kind == "repayment"
                             and t.direction == "debit")
            out["balance"] = {
                # Everything the month has, minus everything that has gone.
                "left_paise": lim["pool_paise"],
                # Of which this much is already promised elsewhere, so it is
                # not free even though it is present.
                "committed_paise": lim["locked_paise"],
                "savings_target_paise": lim["savings_target_paise"],
                "free_paise": (lim["pool_paise"] - lim["locked_paise"]
                               - lim["savings_target_paise"]),
                # The parts, so a reply can show its working.
                "came_in_paise": in_ + back + borrowed,
                "went_out_paise": out_ + lent + paid_back,
                "of_which_fixed_paise": lim["fixed_paid_paise"],
                "of_which_lent_paise": lent,
                "days_left": lim["days_left"],
            }
        if "within_limit" in fields:
            # The report's number: expenses that landed while their day was
            # still inside the limit. Cumulative per day, in ledger order.
            running: dict[date, int] = defaultdict(int)
            n = of = 0
            for t in rows:
                if t.kind == "expense" and not committed(t):
                    running[t.local_day] += t.amount_paise
                    of += 1
                    if running[t.local_day] <= lim["limit_paise"]:
                        n += 1
            out["within_limit"] = {"n": n, "of": of}
        if "udhaar" in fields:
            settled: dict[str, int] = defaultdict(int)
            for t in all_rows:
                if t.kind == "repayment" and t.settles_id:
                    settled[t.settles_id] += t.amount_paise
            opens = [(t, max(0, t.amount_paise - settled[t.id])) for t in all_rows
                     if t.kind in ("lent", "borrowed")]
            out["udhaar"] = {
                "out_paise": sum(r for t, r in opens if t.kind == "lent"),
                "owe_paise": sum(r for t, r in opens if t.kind == "borrowed"),
                "open_lendings": sum(1 for t, r in opens if t.kind == "lent" and r > 0),
                "open_borrowings": sum(1 for t, r in opens if t.kind == "borrowed" and r > 0),
                # Each open row with its **id**, because a repayment has to name
                # the lending it settles and there was nowhere to read that
                # from: `people` has names and no ids, and a `rows` page is
                # date-scoped so an August lending is invisible in September.
                # With no source, the model supplied one from memory, the id
                # pointed at a deleted row, and the write died on a foreign key.
                "open": [
                    {"id": t.id, "kind": t.kind,
                     "name": t.counterparty_name or t.description,
                     "amount_paise": t.amount_paise, "remaining_paise": r,
                     "local_day": t.local_day}
                    for t, r in sorted(opens, key=lambda x: x[0].local_day) if r > 0
                ],
            }

    if "to_review" in fields:
        # Open proposals from the nightly batch — asked, not yet answered.
        # Not date-scoped, like udhaar's `open`: a question from last month
        # is still a question. spec/in-progress/categorise.md § Review.
        from app.agent.categorise import to_review
        out["to_review"] = await to_review(session, user)

    if "rows" in fields:
        cap = max(1, min(rows_limit, ROWS_CAP))
        ordered = sorted(rows, key=lambda t: (t.local_day, t.id), reverse=True)
        if after:
            # The cursor is the last row's sort key, `YYYY-MM-DD|id`, so the
            # next page starts strictly after it in the same order.
            a_day, _, a_id = after.partition("|")
            ordered = [t for t in ordered if (t.local_day.isoformat(), t.id) < (a_day, a_id)]
        page = ordered[:cap]
        out["rows"] = page
        out["total_matching"] = len(rows)
        out["next_after"] = (f"{page[-1].local_day.isoformat()}|{page[-1].id}"
                             if len(ordered) > cap else None)
    return out
