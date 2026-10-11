"""
Import Paisa_Tracker.xlsx into the ledger.

Faithful, not complete: where the workbook does not say something the column
stays NULL. Inventing a value would test the schema against fiction.

Idempotent. Every imported row carries a `dedupe_key` derived from its position
in the workbook, so re-running inserts nothing. That is a slight widening of
what dedupe_key means — it was built for "this notification already arrived" —
but the question is the same one: has this exact source row landed already?

    uv run python scripts/import_workbook.py ~/Downloads/Paisa_Tracker.xlsx
"""

import asyncio
import re
import sys
from datetime import UTC, date, datetime

from openpyxl import load_workbook
from sqlalchemy import select

from app.db import SessionLocal
from app.models.paisa import BalanceCheck, Counterparty, Transaction
from scripts._user import pick_user

YEAR, MONTH = 2026, 8
# The Setup sheet's standing costs: fixed (never spendable) and repeating every month.
REPEATING = {"Ghar", "EMI", "Subscriptions", "Rent"}
# The one user's id, read from the users table in main(). Never a literal.
USER = ""

# The workbook records a day, never a clock time. Noon is a marker for "day
# known, time unknown" — not a guess at when it happened.
NOON = 12

# Two or more ALL-CAPS words: how UPI writes a payee. "Wi-Fi", "Mr" and
# "T-shirt" fail it, which is the point.
PAYEE = re.compile(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,})+\b")


def at(day: int) -> datetime:
    return datetime(YEAR, MONTH, day, NOON, tzinfo=UTC)


def noon(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, NOON, tzinfo=UTC)


def payee_in(text: str) -> str | None:
    m = PAYEE.search(text or "")
    return m.group(0) if m else None


def read_daily(ws):
    """Daily Log → dicts. The header row is found, not assumed: blank spacer
    rows above it shift its position and a hardcoded number reads the header
    as data."""
    header = next(
        i for i, r in enumerate(ws.iter_rows(values_only=True), start=1)
        if r and str(r[0]).strip() == "Din"
    )
    rows = []
    for i, r in enumerate(ws.iter_rows(min_row=header + 1, values_only=True), start=header + 1):
        din, what, cat, amt, method, note = (list(r) + [None] * 6)[:6]
        if din is None or amt is None:
            continue
        rows.append(
            {
                "key": f"xlsx:daily:{i}",
                "day": int(din),
                "description": str(what).strip(),
                "category": str(cat).strip(),
                "paise": int(round(float(amt) * 100)),
                "method": str(method).strip().lower() if method else None,
                "note": str(note).strip() if note else None,
            }
        )
    return rows


# The Udhaar sheet has no dates at all. These come from the user, from memory,
# and are carried at reduced confidence rather than presented as recorded fact.
UDHAAR = [
    # raw_name, paise lent, lent on, returned on (None = still out)
    ("Dost 1 (naam?)", 700000, date(2026, 8, 2), date(2026, 8, 12)),
    ("Dost (1,000 wala)", 100000, date(2026, 8, 2), date(2026, 8, 12)),
    ("Badi sister", 200000, date(2026, 8, 2), date(2026, 8, 12)),
    ("Dost 2 (naam?)", 400000, date(2026, 6, 24), None),
]
UDHAAR_CONFIDENCE = 0.5

# The Setup sheet's money — salary in, fixed costs out. The workbook kept these
# out of the ledger and called the remainder "MERE HAATH MEIN THA", which named
# a subtraction as if it were a thing you held. It is not: ghar ka paisa is
# spent, not held, and it never comes back.
#
# Dates come from the user's memory (the sheet has only one, 13 Aug), so each
# row carries the confidence its date deserves rather than pretending to know.
#
# 'fixed' WAS a tag; it is now two columns (fixed, repeats) the user flips on the
# row — spec/in-progress/fixed-costs.md. The Setup rows are both: the same
# way Rakhi spending cut across two. It keeps the daily-limit sum at 22,139
# while making the card's pale arc measurable instead of hardcoded.
SETUP = [
    # day, kind, paise, category, description, tags, confidence, note
    (2,  "income",  9500000, "Salary",        "Salary",                    [],        0.7,
     "Mahine ke shuru me — 1-2 tarikh, yaad se"),
    (13, "income",   800000, "Family",        "Papa se (rent ke liye)",    [],        1.0,
     "13 Aug ko aaya — rent pay karne ke liye"),
    (3,  "expense", 4000000, "Ghar",          "Ghar par diya (Papa ko)",   [], 0.7,
     "Paisa aane ke baad, 3-4 tarikh. Wapas nahi aata — kharcha hai"),
    (7,  "expense", 1000000, "EMI",           "EMI",                       [], 0.4,
     "'Kuch din baad' — tareekh sabse kam pakki"),
    (10, "expense",  300000, "Subscriptions", "Subscriptions",             [], 0.7,
     "10-11 tarikh ko cut hua"),
    (14, "expense",  794800, "Rent",          "Rent (Vinay Kumar)",        [], 0.9,
     "14 tarikh ko diya, papa ke 8,000 se"),
]


async def counterparty_id(session, raw_name: str, *, is_peer: bool = False) -> str:
    found = await session.scalar(select(Counterparty).where(Counterparty.raw_name == raw_name))
    if found is None:
        found = Counterparty(user_id=USER, raw_name=raw_name, is_peer=is_peer)
        session.add(found)
        await session.flush()
    elif is_peer and not found.is_peer:
        found.is_peer = True
    return found.id


async def main(path: str) -> None:
    wb = load_workbook(path, data_only=True)
    daily = read_daily(wb["Daily Log"])

    async with SessionLocal() as session:
        USER = await pick_user(session)
        seen = set(
            (await session.scalars(select(Transaction.dedupe_key).where(
                Transaction.dedupe_key.is_not(None)))).all()
        )
        added = skipped = 0

        for row in daily:
            if row["key"] in seen:
                skipped += 1
                continue
            name = payee_in(row["description"])
            note = row["note"]
            # The workbook's own provenance marker, and the only place source is
            # anything but manual.
            source = "notification" if note and "notification se" in note.lower() else "manual"
            # Rakhi spending lands in two categories; the workbook totalled it by
            # hand in a note. That is exactly the cut a category cannot make.
            tags = ["rakhi"] if "rakhi" in row["description"].lower() else []

            session.add(
                Transaction(
                    user_id=USER,
                    dedupe_key=row["key"],
                    source=source,
                    occurred_at=at(row["day"]),
                    local_day=date(YEAR, MONTH, row["day"]),
                    amount_paise=row["paise"],
                    direction="debit",
                    kind="expense",
                    category=row["category"],
                    description=row["description"],
                    note=note,
                    counterparty_name=name,
                    counterparty_id=await counterparty_id(session, name) if name else None,
                    method=row["method"],
                    tags=tags,
                )
            )
            added += 1

        for i, (raw, paise, lent_on, back_on) in enumerate(UDHAAR):
            cp = await counterparty_id(session, raw, is_peer=back_on is not None)
            lent_key = f"xlsx:udhaar:lent:{i}"
            if lent_key in seen:
                skipped += 1
                lent_id = await session.scalar(
                    select(Transaction.id).where(Transaction.dedupe_key == lent_key))
            else:
                lent = Transaction(
                    user_id=USER,
                    dedupe_key=lent_key,
                    source="manual",
                    confidence=UDHAAR_CONFIDENCE,
                    occurred_at=noon(lent_on),
                    local_day=lent_on,
                    amount_paise=paise,
                    direction="debit",
                    kind="lent",
                    category="Udhaar",
                    description=f"{raw} ko diya",
                    note="Udhaar sheet — tareekh yaad se, sheet mein nahi thi",
                    counterparty_name=raw,
                    counterparty_id=cp,
                )
                session.add(lent)
                await session.flush()
                lent_id = lent.id
                added += 1

            if back_on is None:
                continue
            repay_key = f"xlsx:udhaar:repay:{i}"
            if repay_key in seen:
                skipped += 1
                continue
            session.add(
                Transaction(
                    user_id=USER,
                    dedupe_key=repay_key,
                    source="manual",
                    confidence=UDHAAR_CONFIDENCE,
                    occurred_at=noon(back_on),
                    local_day=back_on,
                    amount_paise=paise,
                    direction="credit",
                    kind="repayment",
                    category="Udhaar",
                    description=f"{raw} se wapas aaya",
                    counterparty_name=raw,
                    counterparty_id=cp,
                    settles_id=lent_id,
                )
            )
            added += 1

        for i, (dd, kind, paise, cat, desc, tags, conf, note) in enumerate(SETUP):
            key = f"xlsx:setup:{i}"
            if key in seen:
                skipped += 1
                continue
            session.add(
                Transaction(
                    user_id=USER,
                    dedupe_key=key,
                    source="manual",
                    confidence=conf,
                    occurred_at=at(dd),
                    local_day=date(YEAR, MONTH, dd),
                    amount_paise=paise,
                    direction="credit" if kind == "income" else "debit",
                    kind=kind,
                    category=cat,
                    description=desc,
                    note=note,
                    tags=tags,
                    fixed=cat in REPEATING,
                    repeats=cat in REPEATING,
                )
            )
            added += 1

        # Setup sheet. Only the two things nothing in the ledger can produce.
        if not await session.get(BalanceCheck, "bc-xlsx-2026-08-22"):
            session.add(
                BalanceCheck(
                    user_id=USER,
                    id="bc-xlsx-2026-08-22",
                    as_of=date(2026, 8, 22),
                    amount_paise=899200,
                    note="User ne bank check karke bataya",
                )
            )
        await session.commit()
        print(f"added {added}, skipped {skipped} (already imported)")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "Paisa_Tracker.xlsx"))
