"""
Every function the model may call. spec/agent-tools.md.

Each tool is a name, a one-line purpose the model reads, a JSON schema, and a
handler. **The handlers call the routes that already exist** — so replays,
derived fields, `settle()`'s guards, the pantry walk and their tests come with
them, and there is no second write path to drift from the first.

Two departures from the spec, both deliberate:

* **The server mints ids, not the model.** The spec has the agent supply a
  ULID for replay safety. A language model inventing a 26-character identifier
  is a worse idea than it sounds; within one turn the runner already refuses a
  repeated call, and capture's retry safety is a different path.
* **`today` is not a tool.** It is in the prompt — a fact every turn needs and
  no turn changes.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, Response
from sqlalchemy import func, inspect, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import commitments as K
from app.agent.estimate import ESTIMATED, price, resolve_ingredients
from app.agent.ladder import resolve
from app.diet_summary import FIELDS as DIET_FIELDS
from app.diet_summary import diet_summary
from app.models.base import new_id
from app.models.diet import Dish, Exercise, Food, Habit, MealLog, PantryItem
from app.models.paisa import Transaction
from app.paisa_summary import FIELDS as PAISA_FIELDS
from app.paisa_summary import paisa_summary
from app.routes import dishes as dishes_route
from app.routes import people as people_route
from app.routes import places as places_route
from app.routes import workouts as workouts_route
from app.routes import writes
from app.schemas.dishes import DishIn
from app.schemas.people import CounterpartyIn, CounterpartyPatch
from app.schemas.places import PlaceIn, PlacePatch
from app.schemas.users import MemoryIn
from app.schemas.workouts import ExerciseIn
from app.schemas.writes import (
    DayIn,
    MealIn,
    MealItemIn,
    MealPatch,
    PantryMoveIn,
    TransactionIn,
    TransactionPatch,
)

IST = "+05:30"


def _at(day: date, hhmm: str = "12:00:00") -> datetime:
    """A timestamp for a day the user named but did not put a clock on."""
    return datetime.fromisoformat(f"{day.isoformat()}T{hhmm}{IST}")


def _d(v) -> Any:
    """JSON-safe: dates as ISO strings, Decimals as floats, rows as dicts.

    Routes hand back either an ORM row or the Pydantic model they declare as
    their response — both have to come out as plain data, because what the
    model reads next is JSON.
    """
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _d(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_d(x) for x in v]
    if hasattr(v, "model_dump"):
        return _d(v.model_dump())
    if hasattr(v, "__table__"):
        # Skip columns the session has not loaded. A row just INSERTed has its
        # server defaults unset on the Python object, and reading one fires a
        # SELECT — from inside a comprehension, where there is no greenlet to
        # await on. `_d` must never do IO; callers that want everything
        # `await session.refresh(row)` first.
        unloaded = inspect(v).unloaded
        return {c.name: _d(getattr(v, c.name))
                for c in v.__table__.columns if c.name not in unloaded}
    return v


# ─── paisa ───────────────────────────────────────────────────────────────────

#: A lending, a borrowing and the repayment that settles either are filed under
#: one category, whatever the model passes: the kind is what the row means, and
#: a lent ₹4,000 filed as "income" (seen 2026-10-01) read as money that came in.
LOAN_KINDS = frozenset({"lent", "borrowed", "repayment"})
LOAN_CATEGORY = "Udhaar"

#: Words that name a ride and nothing else. A description made of one of these,
#: logged without a category the user named, is a Transport guess — the model
#: filed "auto 80" as food (2026-10-01) because the ledger it was shown had no
#: Transport in it yet. Still a guess: the card keeps its dot until confirmed.
_RIDE_WORDS = frozenset({
    "auto", "autorickshaw", "rickshaw", "riksha", "cab", "taxi", "ola", "uber",
    "rapido", "metro", "bus", "train", "local", "petrol", "diesel", "fuel", "cng",
    "parking", "toll", "fastag",
})


def _rides(description: str) -> bool:
    words = [w for w in "".join(c if c.isalnum() else " " for c in description.casefold()).split()
             if not w.isdigit()]
    return bool(words) and all(w in _RIDE_WORDS or w in {"ride", "fare", "ka", "ki", "se"}
                               for w in words) and any(w in _RIDE_WORDS for w in words)


def _category_for(kind: str, direction: str, category: str, description: str,
                  stated: bool) -> tuple[str, float | None]:
    """The category to write, and the confidence to force (None keeps the
    caller's). The kind decides a loan's; a debit is never income; a ride the
    user did not categorise is Transport."""
    if kind in LOAN_KINDS:
        return LOAN_CATEGORY, 1.0
    if stated:
        return category, None
    if direction == "debit" and category.strip().casefold() == "income":
        category = "Other"
    if direction == "debit" and _rides(description):
        return "Transport", None
    return category, None


async def t_paisa_report(session, user, *, to: str, fields: list[str],
                         **kw) -> dict:
    hi = date.fromisoformat(to)
    lo = date.fromisoformat(kw["from"]) if kw.get("from") else hi.replace(day=1)
    out = _d(await paisa_summary(session, user, lo, hi, set(fields),
                                 category=kw.get("category"),
                                 counterparty_id=kw.get("counterparty_id"),
                                 rows_limit=kw.get("rows_limit", 30), after=kw.get("after")))
    # Said, not left to be inferred. Left out, `from` is the 1st of the month,
    # and "aaj kitna kharcha hua?" was answered with October's total and the
    # claim that today had no data (2026-10-09). And a period before the first
    # row is not ₹0 spent — it is nothing recorded: unknown is not zero.
    out["period"] = {"from": lo.isoformat(), "to": hi.isoformat()}
    first = await session.scalar(select(func.min(Transaction.local_day)).where(
        Transaction.user_id == user, Transaction.deleted_at.is_(None)))
    if first is None or hi < first:
        out["no_records"] = ("nothing is recorded for this period"
                             + (f" — the ledger starts on {first.isoformat()}" if first else "")
                             + ". Say there is no data; never ₹0.")
    elif lo < first:
        out["ledger_starts"] = first.isoformat()
    return out


async def _only_open_loan(session, user, name: str, kind: str) -> str | None:
    """The one open lending (or borrowing) with this person, or None when there
    is none or more than one — then the agent must ask which."""
    from sqlalchemy.orm import aliased
    paid = aliased(Transaction)
    settled = (select(func.coalesce(func.sum(paid.amount_paise), 0))
               .where(paid.settles_id == Transaction.id, paid.deleted_at.is_(None))
               .scalar_subquery())
    rows = list((await session.scalars(
        select(Transaction.id).where(
            Transaction.user_id == user, Transaction.deleted_at.is_(None),
            Transaction.kind == kind,
            func.lower(Transaction.counterparty_name) == name.strip().lower(),
            Transaction.amount_paise > settled))).all())
    return rows[0] if len(rows) == 1 else None


async def t_log_payment(session, user, *, amount_paise: int, direction: str, kind: str,
                        category: str, description: str, local_day: str, **kw) -> dict:
    if kind == "repayment" and not kw.get("settles_id") and kw.get("counterparty_name"):
        # "Amit ne 1500 wapas kar diye" came back "needs settles_id" and the
        # agent gave up rather than look the lending up (2026-10-10). When the
        # person has exactly one open loan in that direction, that is the one.
        kw["settles_id"] = await _only_open_loan(
            session, user, kw["counterparty_name"],
            "lent" if direction == "credit" else "borrowed")
    if not amount_paise or amount_paise <= 0:
        # The model filled a missing amount with 0 rather than ask
        # ("grocery pe kharcha kiya", 2026-10-09). The refusal says the next step.
        return {"error": "the amount is missing — ask how much it was; never log 0 or a guess"}
    day = date.fromisoformat(local_day)
    stated = bool(kw.get("category_stated"))
    if not stated and kind == "expense":
        # What they filed the same thing under before. A cigarette went to
        # Health/Diet once and Other the next time; their ledger says Other.
        # Still a guess — the card keeps its dot until they confirm it.
        usual = await session.scalar(
            select(Transaction.category).where(
                Transaction.user_id == user, Transaction.deleted_at.is_(None),
                Transaction.kind == "expense",
                func.lower(Transaction.description) == description.strip().lower())
            .order_by(Transaction.created_at.desc()).limit(1))
        if usual:
            category = usual
    category, forced = _category_for(kind, direction, category, description, stated)
    body = TransactionIn(
        id=new_id(), amount_paise=amount_paise, direction=direction, kind=kind,
        category=category, description=description, local_day=day,
        occurred_at=_at(day, kw.get("time", "12:00:00")), source="manual",
        # A category the user did not name is the agent's guess, and the row
        # says so; `Confirm` on the card raises it to 1. spec/chat-cards.md.
        # A loan's category is decided by its kind, so it is never a guess.
        confidence=forced if forced is not None else (1.0 if stated else 0.7),
        counterparty_name=kw.get("counterparty_name"), method=kw.get("method"),
        note=kw.get("note"), settles_id=kw.get("settles_id"),
    )
    row = await writes.create_transaction(body, session, user, Response())
    await session.refresh(row)
    return _d(row)


def _move_day(patch: dict, row) -> dict:
    """A row moved to another day takes its clock with it.

    `local_day` and `occurred_at` are two views of one moment. Setting only the
    first leaves a row that claims Sunday and happened on Friday, which every
    later query on `occurred_at` then reads wrong.

    It shifts by the number of days moved rather than overwriting the date.
    `occurred_at` is stored in UTC and `local_day` is the user's, so the two
    disagree either side of midnight IST: an 00:30 chai is the 21st locally and
    the 20th in UTC, and stamping the local date onto the UTC value would move
    that row a day too far. A delta cannot: the clock time survives untouched.
    """
    if patch.get("local_day") and not patch.get("occurred_at"):
        moved = date.fromisoformat(patch["local_day"]) - row.local_day
        patch["occurred_at"] = row.occurred_at + timedelta(days=moved.days)
    return patch


def _distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


async def _row_id(session, model, row_id: str, user: str) -> str:
    """The id as given, or the one recent row it was plainly meant to be.

    A 26-character id copied out of the conversation came back one character
    short and the correction died on "no such row" (2026-10-10). Within two
    edits of exactly one of the person's recent rows, it is that row; anything
    looser stays a refusal — a guessed row is worse than none.
    """
    if await session.get(model, row_id) is not None:
        return row_id
    recent = list((await session.scalars(
        select(model.id).where(model.user_id == user, model.deleted_at.is_(None))
        .order_by(model.created_at.desc()).limit(200))).all())
    close = [r for r in recent if _distance(r, row_id) <= 2]
    return close[0] if len(close) == 1 else row_id


async def t_correct_payment(session, user, *, transaction_id: str, **patch) -> dict:
    transaction_id = await _row_id(session, Transaction, transaction_id, user)
    live = await writes.live_or_404(session, Transaction, transaction_id, user)
    # A category the user names — a correction, or "haan" to the guess — is no
    # longer a guess. Left at the logged 0.7, the card kept asking "Food, I
    # guessed · Right" after the user had already answered it (2026-10-01).
    if patch.get("category"):
        if live.kind in LOAN_KINDS:
            patch["category"] = LOAN_CATEGORY
        patch.setdefault("confidence", 1.0)
    row = await writes.patch_transaction(
        transaction_id, TransactionPatch(**_move_day(patch, live)), session, user)
    await session.refresh(row)
    return _d(row)


async def t_categorise_now(session, user, **kw) -> dict:
    """The nightly batch, on demand. spec/in-progress/categorise.md — one
    function, two doors; this is the agent's.

    The report carries `to_review`: **everything still waiting on an answer**,
    not only what this run proposed. Asked "aaj ke doubtful payments dekh lo"
    the model ran the batch, read `examined: 0` — nothing new since last night
    — and answered "koi doubtful payment nahi mila" while fourteen questions
    sat open. A question the user asks in one sentence needs one field whose
    name is that question.
    """
    from app.agent.categorise import categorise, to_review
    day = date.fromisoformat(kw["local_day"]) if kw.get("local_day") else None
    out = await categorise(session, user, day)
    out["to_review"] = await to_review(session, user)
    return _d(out)


async def t_delete_payment(session, user, *, transaction_id: str) -> dict:
    """Soft delete, and the row is read first so the card can show what went.

    The route refuses a lending that has repayments; that refusal reaches the
    model as data and it explains rather than retrying.
    """
    transaction_id = await _row_id(session, Transaction, transaction_id, user)
    row = await writes.live_or_404(session, Transaction, transaction_id, user)
    gone = {"id": row.id, "amount_paise": row.amount_paise, "description": row.description,
            "category": row.category, "local_day": row.local_day, "kind": row.kind}
    await writes.delete_transaction(transaction_id, session, user)
    return {**_d(gone), "deleted": True}



# ─── commitments (spec/done/commitments.md) ───────────────────

async def _commitments_now(session, user) -> list[dict]:
    """This month's lines, short — what a refusal names so the reply has
    somewhere to go."""
    return [{"id": ln.c.id, "name": ln.c.name, "category": ln.c.category,
             "amount": _rupees(ln.c.amount_paise), "owed": _rupees(ln.owed_paise),
             "skipped": ln.skipped}
            for ln in await K.lines(session, user, K.today_local())]


async def _one_commitment(session, user, ref: str):
    """(line, error). An id, or the name as the user says it — a name that fits
    none or two is data the model reads, never a guess."""
    month = K.today_local()
    ls = await K.lines(session, user, month)
    by_id = [ln for ln in ls if ln.c.id == ref]
    if by_id:
        return by_id[0], None
    needle = ref.strip().lower()
    exact = [ln for ln in ls if ln.c.name.strip().lower() == needle]
    hits = exact or [ln for ln in ls if needle in ln.c.name.lower() or
                     ln.c.name.lower() in needle]
    if not hits:
        return None, {"error": f"no commitment called {ref!r} this month",
                      "commitments": await _commitments_now(session, user)}
    if len(hits) > 1:
        return None, {"error": f"{ref!r} could be {len(hits)} commitments — ask which",
                      "commitments": [{"id": h.c.id, "name": h.c.name,
                                       "amount": _rupees(h.c.amount_paise)} for h in hits]}
    return hits[0], None


def _commitment_out(item, action: str, **extra) -> dict:
    return {"commitment_id": item.id, "name": item.name, "category": item.category,
            "amount_paise": item.expected_paise, "paid_paise": item.paid_paise,
            "owed_paise": item.owed_paise, "due_day": item.due_day,
            "repeats": item.repeats, "skipped": item.skipped, "action": action, **extra}


#: Categories of everyday spending. A commitment is an obligation — rent, an
#: EMI, a loan, a subscription — and these are never one by themselves.
EVERYDAY = frozenset({"transport", "khana/grocery", "dost & bahar", "health/diet",
                      "shopping", "other"})


async def t_manage_commitment(session, user, *, commitment: str | None = None, **kw) -> dict:
    """Make, change, skip, link a payment to, or delete an obligation. The one
    way to change what is owed: `correct_payment` edits a payment, never a
    commitment. spec/done/commitments.md § Chat."""
    from app.routes import commitments as route
    from app.schemas.commitments import CommitmentIn, CommitmentPatch

    ln = None
    if commitment:
        ln, err = await _one_commitment(session, user, commitment)
        if err:
            return err
    if kw.get("delete"):
        if ln is None:
            return {"error": "name the commitment to delete",
                    "commitments": await _commitments_now(session, user)}
        n = (await session.execute(
            select(func.count()).select_from(Transaction).where(
                Transaction.commitment_id == ln.c.id,
                Transaction.deleted_at.is_(None)))).scalar_one()
        await route.delete_commitment(ln.c.id, session, user)
        return {"commitment_id": ln.c.id, "name": ln.c.name, "deleted": True,
                "payments_now_ordinary_spending": n, "action": "deleted"}
    if ln is None:
        # Making one.
        if not kw.get("name"):
            return {"error": "name the commitment to make — or which one to change",
                    "commitments": await _commitments_now(session, user)}
        if not kw.get("amount_paise") or kw["amount_paise"] <= 0:
            return {"error": "the amount is missing — ask how much it is each month"}
        if not kw.get("category"):
            return {"error": "which category is it paid under? (Rent, EMI, Subscriptions…) — ask"}
        if kw["category"].strip().casefold() in EVERYDAY:
            # "health 2000 har mahine commitment add karo" reserved ₹2,000 a month
            # in a category that is everyday spending — the very mistake the
            # migration found on the live ledger (2026-10-10). Not overridable
            # from chat: a model handed a flag set it without asking (tried
            # 2026-10-10). The Commitments page can still add anything.
            return {"error": f"{kw['category']} is everyday spending, not something owed each "
                             "month, so it is not a commitment. Say that, and ask what the "
                             "obligation really is — rent, an EMI, a subscription, a bill — "
                             "and file it under that category (Rent, EMI, Subscriptions, "
                             "Bills/Recharge, Ghar, Udhaar). Do not make this one."}
        same = [x for x in await K.lines(session, user, K.today_local())
                if x.c.name.strip().lower() == kw["name"].strip().lower()]
        if same and not kw.get("another"):
            # "EMI 8000 add karo" with an EMI already there made a second one
            # beside the real ₹10,000 line. Ask first: change it, or add another.
            return {"error": f"there is already a commitment called {same[0].c.name!r} "
                             f"({_rupees(same[0].c.amount_paise)}) — ask whether to change that "
                             "one, or add a second, separate one (then pass another=true)",
                    "commitments": [{"id": x.c.id, "name": x.c.name,
                                     "amount": _rupees(x.c.amount_paise)} for x in same]}
        item = await route.create_commitment(CommitmentIn(
            id=new_id(), name=kw["name"], category=kw["category"],
            amount_paise=kw["amount_paise"], due_day=kw.get("due_day"),
            repeats=True if kw.get("repeats") is None else bool(kw["repeats"])),
            session, user, Response())
        return _commitment_out(item, "made", repeats_stated=kw.get("repeats") is not None,
                               category_stated=bool(kw.get("category_stated")))
    # Changing one.
    item = None
    if kw.get("pay_with"):
        tx_id = await _row_id(session, Transaction, kw["pay_with"], user)
        await writes.patch_transaction(
            tx_id, TransactionPatch(commitment_id=ln.c.id), session, user)
        item = await route._item(session, user, ln.c.id)
        action = "linked"
    patch = {}
    for k in ("name", "category", "amount_paise", "due_day", "repeats"):
        if kw.get(k) is not None:
            patch[k] = kw[k]
    if kw.get("skip") is not None:
        patch["skipped"] = bool(kw["skip"])
    if patch:
        item = await route.patch_commitment(ln.c.id, CommitmentPatch(**patch), session, user)
        action = ("skipped" if patch.get("skipped") is True else
                  "unskipped" if patch.get("skipped") is False else "changed")
    if item is None:
        return {"error": "nothing to change — name what to change (amount, due day, "
                         "skip, repeat, delete)",
                "commitments": await _commitments_now(session, user)}
    return _commitment_out(item, action)

# ─── diet ────────────────────────────────────────────────────────────────────

async def t_diet_report(session, user, *, to: str, fields: list[str], **kw) -> dict:
    hi = date.fromisoformat(to)
    lo = date.fromisoformat(kw["from"]) if kw.get("from") else hi
    out = await diet_summary(session, user, lo, hi, set(fields),
                             meal_type=kw.get("meal_type"),
                             rows_limit=kw.get("rows_limit", 30), after=kw.get("after"))
    return _d(out)


async def _macros(session, lines: list[dict]) -> tuple[int, float, float | None,
                                                        float | None, bool]:
    """Add up what the resolved lines are worth, and say whether anything was
    actually known.

    A line that resolved to nothing contributes nothing. So does a food with no
    nutrition on file — and the difference between *zero calories* and *nobody
    knows* is the whole of the honesty rule, so the caller is told which.
    """
    kcal = 0
    p = c = f = 0.0
    known_c = known_f = known_any = False
    for line in lines:
        if line.get("dish_id"):
            d = await session.get(Dish, line["dish_id"])
            if d:
                n = float(line.get("servings") or 1)
                known_any = known_any or d.kcal is not None or d.protein_g is not None
                kcal += int((d.kcal or 0) * n)
                p += float(d.protein_g or 0) * n
                if d.carbs_g is not None:
                    c += float(d.carbs_g) * n
                    known_c = True
                if d.fat_g is not None:
                    f += float(d.fat_g) * n
                    known_f = True
        elif line.get("food_id"):
            fd = await session.get(Food, line["food_id"])
            if fd:
                grams = float(line.get("quantity") or 0)
                if grams and fd.unit != "g" and fd.grams_per_unit:
                    grams *= float(fd.grams_per_unit)
                share = grams / 100.0
                known_any = known_any or (
                    grams > 0 and (fd.kcal_100g is not None or fd.protein_g_100g is not None))
                kcal += int((fd.kcal_100g or 0) * share)
                p += float(fd.protein_g_100g or 0) * share
                if fd.carbs_g_100g is not None:
                    c += float(fd.carbs_g_100g) * share
                    known_c = True
                if fd.fat_g_100g is not None:
                    f += float(fd.fat_g_100g) * share
                    known_f = True
    return (kcal, round(p, 1), (round(c, 1) if known_c else None),
            (round(f, 1) if known_f else None), known_any)


async def t_log_meal(session, user, *, text_said: str, meal_type: str,
                     local_day: str, **kw) -> dict:
    """Resolve, then write. Both halves in one tool because the ladder runs on
    the way to the write — and nothing is blocked on one uncertain word."""
    day = date.fromisoformat(local_day)
    if kw.get("dish_id"):
        # The UI already knows the dish — a tap on a card. No ladder, nothing
        # to guess: the line is the dish, by id, at the servings given.
        dish = await session.get(Dish, kw["dish_id"])
        if dish is None or dish.deleted_at is not None:
            return {"error": f"no dish with id {kw['dish_id']!r}"}
        lines = [{"said": text_said, "matched": True, "name": dish.name, "dish_id": dish.id,
                  "food_id": None, "confidence": 1.0, "rung": "id",
                  "servings": float(kw.get("servings") or 1), "quantity": None,
                  "needs_quantity": False}]
    else:
        lines = await resolve(session, user, text_said)

    # The ladder has said WHAT this is; the model says what it is WORTH. The
    # library informs that and no longer decides it — a plate it has never
    # seen used to be logged at 0 kcal, and its numbers carry no provenance
    # anyway. spec/in-progress/meal-estimates.md.
    #
    # Except on a tap: `dish_id` means the user picked that row from their own
    # library at a stated serving, so its macros apply exactly and estimating
    # over them would put an amber dot on a number nobody guessed.
    est = (None if kw.get("dish_id")
           else await price(session, user, text_said, meal_type, lines))
    if est is not None:
        kcal, protein, carbs, fat, fibre = (est.kcal, est.protein_g, est.carbs_g,
                                            est.fat_g, est.fibre_g)
        known = True
    else:
        # The model failed or answered with nothing usable. The library is the
        # fallback, not the source — better a partial number than no log.
        kcal, protein, carbs, fat, known = await _macros(session, lines)
        fibre = None
    # What the meal actually takes out of the house. The model's ingredients
    # when it gave usable ones — it knows a roti is ~40 g of atta and the
    # ladder rightly refuses to guess — otherwise the ladder's own lines.
    # **One source, never both**, or a plate would be subtracted twice.
    spent_lines = [
        MealItemIn(dish_id=line["dish_id"], food_id=line["food_id"],
                   servings=Decimal(str(line["servings"])) if line["servings"] else None,
                   quantity=line["quantity"], said=line["said"], rung=line.get("rung"))
        for line in lines if line["dish_id"] or line["food_id"]
    ]
    made_of: list = []
    if est is not None and est.raw_ingredients:
        made_of = await resolve_ingredients(session, user, est.raw_ingredients)
        if made_of:
            # A dish line already carries its own recipe, so it keeps spending
            # through `dish_quantities`; only the loose foods are replaced.
            spent_lines = [x for x in spent_lines if x.dish_id] + [
                MealItemIn(food_id=i.food_id, quantity=i.quantity,
                           said=i.said, rung=i.rung) for i in made_of
            ]

    body = MealIn(
        id=new_id(), local_day=day, occurred_at=_at(day, kw.get("time", "12:00:00")),
        meal_type=meal_type, dish=text_said.strip()[:120], kcal=kcal,
        protein_g=Decimal(str(protein)),
        carbs_g=Decimal(str(carbs)) if carbs is not None else None,
        fat_g=Decimal(str(fat)) if fat is not None else None,
        fibre_g=Decimal(str(fibre)) if fibre is not None else None,
        source="manual", note=kw.get("note"),
        # Frozen: what the model said before the user touched it. The gap
        # between this and the settled value is the error, and it cannot be
        # recovered later — so it is written now or never.
        estimated_kcal=est.kcal if est else None,
        estimated_protein_g=Decimal(str(est.protein_g)) if est else None,
        estimated_carbs_g=Decimal(str(est.carbs_g)) if est else None,
        estimated_fat_g=Decimal(str(est.fat_g)) if est else None,
        estimated_fibre_g=Decimal(str(est.fibre_g)) if est else None,
        # An estimate is a guess and the card says so with the amber dot.
        # Only a tap on Confirm, or the user's own number, makes it certain.
        confidence=ESTIMATED if est is not None else (
            1.0 if all(x["matched"] and not x.get("needs_quantity")
                       for x in lines) else 0.6),
        # The route writes these and then spends the pantry against them.
        items=spent_lines,
    )
    written = await writes.create_meal(body, session, user, Response())
    return {"meal": _d(written.meal), "lines": lines,
            "spent_from_pantry": [{"food_id": m.food_id, "quantity": m.quantity}
                                  for m in written.pantry_moves],
            # False when nothing in the plate had nutrition on file. The stored
            # row must carry a number (the column is NOT NULL), so it carries
            # zero — the card must not read that as "zero calories".
            "nutrition_known": known,
            # What it had to decide that the user did not say, in their words,
            # so the reply can state it in one line and be disagreed with.
            "assumption": est.assumption if est else "",
            "why": est.why if est else "",
            # What the plate took out of the house, by name — so the reply can
            # say "2 roti ka atta nikal diya" rather than leaving it silent.
            "ingredients": [{"food": i.name, "quantity": i.quantity, "said": i.said}
                            for i in made_of],
            "unresolved": [x["said"] for x in lines if not x["matched"]],
            # Matched, but with no weight — their macros are NOT in the total.
            # Ask how much, or leave it; never assume a portion.
            "needs_quantity": [x["said"] for x in lines if x.get("needs_quantity")]}


async def t_correct_meal(session, user, *, meal_id: str, **patch) -> dict:
    meal_id = await _row_id(session, MealLog, meal_id, user)
    # A value sent as null is a value not given: kcal and protein cannot be
    # unknown on a logged meal, and a null one failed the write (2026-10-10).
    patch = {k: v for k, v in patch.items() if v is not None}
    live = await writes.live_or_404(session, MealLog, meal_id, user)
    row = await writes.patch_meal(meal_id, MealPatch(**_move_day(patch, live)), session, user)
    return _d(row)


async def t_delete_meal(session, user, *, meal_id: str) -> dict:
    """Soft delete. The route unspends the meal's lines, so whatever the plate
    took off the shelf goes back on it."""
    meal_id = await _row_id(session, MealLog, meal_id, user)
    row = await writes.live_or_404(session, MealLog, meal_id, user)
    gone = {"id": row.id, "dish": row.dish, "meal_type": row.meal_type,
            "kcal": row.kcal, "protein_g": row.protein_g, "local_day": row.local_day}
    await writes.delete_meal(meal_id, session, user)
    return {**_d(gone), "deleted": True}


async def _habit_by(session, user, ref: str):
    """A habit by name or by id. The model holds names — the user says them —
    and ids, which is what every other tool takes; no habit is ever named like
    a ULID, so one lookup can serve both and neither call has to guess."""
    return await session.scalar(select(Habit).where(
        Habit.user_id == user, Habit.deleted_at.is_(None),
        or_(func.lower(Habit.name) == ref.lower(), Habit.id == ref)))


async def _tracked(session, user) -> list[str]:
    """What is tracked right now — named so a refusal has somewhere to go."""
    return list((await session.scalars(select(Habit.name).where(
        Habit.user_id == user, Habit.deleted_at.is_(None)).order_by(Habit.name))).all())


async def t_log_day(session, user, *, local_day: str, **kw) -> dict:
    """The day's facts in one write: sleep, weight, and any habit ticks.

    A weight is also a weigh-in — the ledger the Profile page, diet_report and
    the first run's summary all read. Written only to `days`, a weight said in
    chat reached none of them. The `days` copy stays for what reads it there.
    """
    day = date.fromisoformat(local_day)
    out: dict = {}
    scalars = {k: v for k, v in kw.items()
               if k in ("sleep_hours", "weight_kg", "log_complete", "note") and v is not None}
    if scalars:
        out["day"] = _d(await writes.put_day(day, DayIn(**scalars), session, user))
    if kw.get("weight_kg") is not None:
        from app.routes import users as users_route
        from app.schemas.users import WeighInIn
        # The day's reading: a second one that day replaces it, and `estimated`
        # is written either way, so an exact reading clears a guess.
        row = await users_route.create_weigh_in(WeighInIn(
            id=new_id(), local_day=day, weight_kg=kw["weight_kg"],
            estimated=bool(kw.get("approximate"))), session, user, Response())
        out["weigh_in"] = {"id": row.id, "weight_kg": float(row.weight_kg),
                           "estimated": row.estimated}
    logged = []
    for h in kw.get("habits") or []:
        name = h["habit"] if isinstance(h, dict) else h
        # Taking the id too is what makes "start it and tick it today" work: the
        # model tends to reach for the id manage_habit just handed back.
        habit = await _habit_by(session, user, name)
        if habit is None:
            # Naming what does exist, so the reply has somewhere to go. It used
            # to return "no such habit" and stop, which left the user with a
            # refusal and no next step. spec/in-progress/habits.md.
            logged.append({"habit": name, "logged": False,
                           "why": "not tracked yet — ask before starting it",
                           "tracked": await _tracked(session, user)})
            continue
        from app.schemas.writes import HabitLogIn
        row = await writes.create_habit_log(HabitLogIn(
            # The tick's moment: a clock they said, else their message's —
            # Home's day rail places it there (spec/home-day-rail.md).
            id=new_id(), habit_id=habit.id, local_day=day, occurred_at=_at(day, kw.get("time", "12:00:00")),
            amount=(h.get("amount") if isinstance(h, dict) else None),
            note=(h.get("note") if isinstance(h, dict) else None), source="manual",
        ), session, user, Response())
        logged.append({"habit": habit.name, "logged": True, "id": row.id})
    if logged:
        out["habits"] = logged
    # A tick of nothing was the model looking for the habit list by writing
    # ("kaun si habits track ho rahi hain?", 2026-10-09). The list is in every
    # turn's context; this tool only records what they said they did.
    return out or {"error": "nothing to write — log_day records only what they said they "
                            "did. The tracked habits are listed in the turn's context."}


async def t_pantry_move(session, user, *, food_name: str, quantity: int, kind: str,
                        local_day: str) -> dict:
    """Stock arriving, a stock-take, waste or a correction.

    Buying a food the pantry does not track yet starts tracking it. Before,
    "200g paneer aur laya" was refused four times running (2026-10-01) because
    nothing had put paneer on the shelf list first — and nothing could: the
    agent had no tool for it. A purchase or a stock-take is the user saying the
    food is in the house; waste or a correction of something untracked is not."""
    from app.routes.pantry import resolve_food

    day = date.fromisoformat(local_day)
    food = await session.scalar(select(Food).where(
        Food.deleted_at.is_(None),
        or_(func.lower(Food.name) == food_name.strip().lower(),
            Food.aliases.any(food_name.strip().lower()))).limit(1))
    stocking = kind in ("purchase", "opening")
    if food is None and not stocking:
        return {"error": f"no food called {food_name!r} — track it first, or use its real name"}
    if food is None:
        # A new food, with no nutrition: unknown stays unknown, never zero.
        food = await session.get(Food, await resolve_food(session, food_name))
    tracked = await session.scalar(select(PantryItem).where(
        PantryItem.user_id == user, PantryItem.food_id == food.id,
        PantryItem.deleted_at.is_(None)))
    started = False
    if tracked is None:
        if not stocking:
            return {"error": f"{food.name} is not tracked in the pantry"}
        session.add(PantryItem(id=new_id(), user_id=user, food_id=food.id))
        await session.flush()
        started = True
    row = await writes.create_pantry_move(PantryMoveIn(
        id=new_id(), food_id=food.id, quantity=quantity, kind=kind,
        local_day=day, occurred_at=_at(day)), session, user, Response())
    out = {"food": food.name, "unit": food.unit, **_d(row)}
    if started:
        out["now_tracked"] = True
    return out


async def t_suggest_dishes(session, user, *, local_day: str, **kw) -> dict:
    """Candidates with their signals — **not** a ranking. The model ranks;
    there is no score in the database, deliberately."""
    day = date.fromisoformat(local_day)
    rows = (await session.execute(text("""
        WITH stock AS (
            SELECT p.food_id, p.staple,
                   COALESCE(SUM(m.quantity), 0)::int AS qty,
                   COUNT(*) FILTER (WHERE m.kind IN ('purchase','opening'))::int AS inbound
            FROM pantry p LEFT JOIN pantry_moves m
                 ON m.food_id = p.food_id AND m.user_id = p.user_id AND m.deleted_at IS NULL
            WHERE p.user_id = :u AND p.deleted_at IS NULL GROUP BY p.food_id, p.staple
        ), mine AS (
            SELECT i.dish_id, COUNT(*) AS times, MAX(l.local_day) AS last_day
            FROM meal_items i JOIN meal_logs l ON l.id = i.meal_log_id
            WHERE l.user_id = :u AND l.deleted_at IS NULL AND i.deleted_at IS NULL
            GROUP BY i.dish_id
        )
        SELECT d.id, d.name, d.aliases, d.image_url, d.protein_g, d.kcal, d.minutes,
               d.needs_prep_ahead, d.meal_type, d.tags,
               COALESCE(mn.times, 0)::int AS tried,
               mn.last_day,
               (s.id IS NOT NULL) AS saved,
               COALESCE(ARRAY_AGG(f.name) FILTER (
                   WHERE di.food_id IS NOT NULL AND st.food_id IS NOT NULL
                     AND NOT st.staple AND st.inbound > 0 AND st.qty <= 0), '{}') AS missing,
               COALESCE(ARRAY_AGG(f.name) FILTER (
                   WHERE di.food_id IS NOT NULL AND st.food_id IS NULL), '{}') AS untracked
        FROM dishes d
        LEFT JOIN dish_items di ON di.dish_id = d.id AND di.deleted_at IS NULL
        LEFT JOIN foods f ON f.id = di.food_id
        LEFT JOIN stock st ON st.food_id = di.food_id
        LEFT JOIN mine mn ON mn.dish_id = d.id
        LEFT JOIN dish_saves s ON s.dish_id = d.id AND s.user_id = :u AND s.deleted_at IS NULL
        WHERE d.deleted_at IS NULL AND (d.visibility = 'public' OR d.created_by_id = :u)
          -- CAST(...) rather than `:mt::text`: SQLAlchemy reads `::` as part
          -- of the bind parameter's name and leaves the whole thing literal.
          AND (CAST(:mt AS text) IS NULL OR d.meal_type = CAST(:mt AS text))
          AND (CAST(:mins AS int) IS NULL OR d.minutes IS NULL
               OR d.minutes <= CAST(:mins AS int))
        GROUP BY d.id, d.name, d.aliases, d.image_url, d.protein_g, d.kcal, d.minutes,
                 d.needs_prep_ahead, d.meal_type, d.tags, mn.times, mn.last_day, s.id
        ORDER BY d.name
    """), {"u": user, "mt": kw.get("meal_type"), "mins": kw.get("minutes")})).all()

    cands = []
    for r in rows:
        cands.append({
            "dish_id": r.id, "name": r.name, "aliases": list(r.aliases or []),
            "image_url": r.image_url, "protein_g": _d(r.protein_g), "kcal": r.kcal,
            "minutes": r.minutes, "needs_prep_ahead": r.needs_prep_ahead,
            "meal_type": r.meal_type, "tags": list(r.tags or []),
            "tried": r.tried, "saved": r.saved,
            "last_had_days_ago": (day - r.last_day).days if r.last_day else None,
            "cookable_now": not r.missing,
            "missing": list(r.missing or []),
        })
    today = await diet_summary(session, user, day, day, {"today"})
    untracked = sorted({n for r in rows for n in (r.untracked or [])})
    return {
        "candidates": cands,
        "context": {
            **_d(today["today"]),
            # What the pantry has no opinion about. The model asks rather than
            # assuming it is there — "ask, don't invent".
            "pantry_unknown": untracked[:20],
        },
    }


async def t_dishes_search(session, user, *, q: str) -> dict:
    rows = await dishes_route._rows(session, user, mine_only=False, q=q, with_items=False)
    return {"dishes": [{"id": d.id, "name": d.name, "aliases": list(d.aliases or []),
                        "meal_type": d.meal_type, "image_url": d.image_url,
                        "protein_g": _d(d.protein_g), "kcal": d.kcal, "minutes": d.minutes,
                        "tried": d.tried, "saved": d.saved} for d in rows[:20]]}


async def t_keep_dish(session, user, *, dish_id: str | None = None, **kw) -> dict:
    """The star. An id saves it; a definition creates it private and saves it."""
    if dish_id is None:
        if not kw.get("name"):
            return {"error": "give a dish_id, or a name to create one"}
        made = await dishes_route.create_dish(DishIn(
            id=new_id(), name=kw["name"],
            serving_label=kw.get("serving_label") or "1 serving",
            protein_g=Decimal(str(kw.get("protein_g") or 0)),
            kcal=kw.get("kcal"), minutes=kw.get("minutes"),
            meal_type=kw.get("meal_type"), steps=kw.get("steps"),
            source_url=kw.get("source_url"), note=kw.get("note"),
        ), session, user, Response())
        dish_id = made.id
    await dishes_route.save_dish(dish_id, session, user)
    row = await session.get(Dish, dish_id)
    return {"dish_id": dish_id, "name": row.name if row else None, "saved": True}


# ─── body ────────────────────────────────────────────────────────────────────

async def t_exercises(session, user, **kw) -> dict:
    rows = await workouts_route.exercises(
        session, user, q=kw.get("q"), kind=kw.get("kind"),
        muscle_group=kw.get("muscle_group"), equipment=kw.get("equipment"),
        minutes=kw.get("minutes"), tried=kw.get("tried"))
    return {"exercises": [{"id": e.id, "name": e.name, "aliases": list(e.aliases or []),
                           "kind": e.kind, "muscle_group": e.muscle_group,
                           "equipment": e.equipment, "typical_minutes": e.typical_minutes,
                           "tried": e.tried, "last_tried": _d(e.last_tried),
                           "image_url": e.image_url, "steps": e.steps,
                           "source_url": e.source_url}
                          for e in rows[:40]]}


async def t_log_exercise(session, user, *, exercise_id: str | None = None, **kw) -> dict:
    if exercise_id is None:
        if not kw.get("name"):
            return {"error": "give an exercise_id, or a name to add one"}
        made = await workouts_route.create_exercise(ExerciseIn(
            id=new_id(), name=kw["name"], kind=kw.get("kind"),
            muscle_group=kw.get("muscle_group"), equipment=kw.get("equipment"),
            typical_minutes=kw.get("typical_minutes"),
            steps=kw.get("steps"), source_url=kw.get("source_url"),
            source="chat",
        ), session, user, Response())
        exercise_id = made.id
    elif not kw.get("did", True):
        # An exercise already in the library, marked "not done": a write that
        # changes nothing, made to look one up (2026-10-09). The search is
        # `exercises`.
        return {"error": "that exercise is already in the library; did=false changes "
                         "nothing. Log an exercise only when they did it."}
    if kw.get("did", True):
        from app.schemas.workouts import DidIt
        row = await workouts_route.did_it(
            exercise_id, DidIt(local_day=date.fromisoformat(kw["local_day"])
                               if kw.get("local_day") else None), session, user)
        return {"exercise_id": exercise_id, "name": row.name, "tried": row.tried,
                "last_tried": _d(row.last_tried)}
    row = await session.get(Exercise, exercise_id)
    return {"exercise_id": exercise_id, "name": row.name if row else None, "tried": 0}


# ─── people · places · memory ────────────────────────────────────────────────

async def t_manage_habit(session, user, *, habit_id: str | None = None, **kw) -> dict:
    """Start tracking something, rename it, or stop. Not a tick — that is
    log_day, and one verb per tool is the rule the tool count was cut by."""
    from app.routes import habits as habits_route
    from app.schemas.habits import HabitIn, HabitPatch

    # habit_id is whatever the model has — the name the user said, or an id.
    # It never had a way to look an id up, so a rename used to dead-end here.
    found = await _habit_by(session, user, habit_id) if habit_id else None
    if habit_id and found is None:
        return {"error": f"nothing tracked called {habit_id}",
                "tracked": await _tracked(session, user)}
    if kw.get("delete"):
        if found is None:
            return {"error": "name the habit to stop tracking",
                    "tracked": await _tracked(session, user)}
        name = found.name
        await habits_route.delete_habit(found.id, session, user)
        return {"habit_id": found.id, "name": name, "deleted": True}
    already, differs = False, {}
    if found is None and kw.get("name"):
        # A name already tracked is that habit, never a refusal: "gym bhi track
        # karo" with Gym there, or the same answer sent twice, lands on the one
        # row (spec/done/onboarding-goals.md § Data).
        found = await _habit_by(session, user, kw["name"])
        already = found is not None
    if found is None:
        if not kw.get("name"):
            return {"error": "name a habit to change, or to start one"}
        row = await habits_route.create_habit(HabitIn(
            id=new_id(), name=kw["name"], direction=kw.get("direction") or "build",
            unit=kw.get("unit")), session, user, Response())
    elif already:
        # Left as it is. A name is "start one"; changing one is habit_id — so a
        # direction beside a name, the model's guess as often as their word,
        # never flips a habit already tracked ("cigarettes bhi track karo"
        # turning a break habit into build). What differed is said back.
        differs = {k: v for k, v in kw.items()
                   if k in ("direction", "unit") and v is not None and v != getattr(found, k)}
        row = (await habits_route._rows(session, user, one=found.id))[0]
    else:
        patch = {k: v for k, v in kw.items()
                 if k in ("name", "direction", "unit") and v is not None}
        if not patch:
            # Named and left as it was: a write made to look the habit up
            # ("kaun si habits track ho rahi hain?", 2026-10-10).
            return {"error": "nothing to change — the tracked habits are listed in the "
                             "turn's context; answer from there."}
        row = await habits_route.patch_habit(found.id, HabitPatch(**patch), session, user)
    out = {"habit_id": row.id, "name": row.name, "direction": row.direction,
           "unit": row.unit, "days_this_week": row.days_this_week}
    if not already:
        return out
    out["already_tracked"] = True
    if differs:
        out["unchanged"] = (f"asked {', '.join(f'{k} {v}' for k, v in differs.items())}; "
                            "it was left as it is. Changing it is habit_id with the new value "
                            "— only if they asked for the change.")
    return out


# ─── work: projects and tasks (spec/done/projects.md) ─────────────────

async def _project_summaries(session, user) -> list[dict]:
    from app import projects as P
    return [{"project": p.name, "is_default": p.is_default} for p in await P.live(session, user)
            if p.archived_at is None]


async def _one_project(session, user, ref: str):
    """(project, error). A name that fits none or two is data the model reads —
    and a missing project is a question for the person, never a silent create."""
    from app import projects as P
    hits = await P.find(session, user, ref)
    if not hits:
        # The next step for either answer, named. Only "ask" here once looped:
        # told yes, the model retried this call, read "ask" and asked again.
        return None, {"error": f"no project called {ref!r}",
                      "if_not_yet_asked": "ask whether to create it — one question",
                      "if_they_said_yes": f"call manage_project with name={ref!r} first, "
                                          "then repeat this call",
                      "projects": await _project_summaries(session, user)}
    if len(hits) > 1:
        return None, {"error": f"{ref!r} could be {len(hits)} projects — ask which",
                      "projects": [p.name for p in hits]}
    return hits[0], None


def _project_out(p, **extra) -> dict:
    return {"project_id": p.id, "name": p.name, "description": p.description,
            "icon": p.icon, "aliases": list(p.aliases), "is_default": p.is_default,
            **extra}


async def t_manage_project(session, user, *, project: str | None = None, **kw) -> dict:
    """Make a project, change one, archive or delete it. One verb per tool, as
    `manage_habit`: a name alone makes one; `project` names one to change."""
    from app.routes import projects as projects_route
    from app.schemas.projects import ProjectIn, ProjectPatch

    found = None
    if project:
        found, err = await _one_project(session, user, project)
        if err:
            return err
    # "leaf" for icon:leaf — the set's own name, said bare. Refused, the agent
    # gave up on making the project at all (2026-10-10).
    from app.projects import ICONS
    if kw.get("icon") in ICONS:
        kw["icon"] = f"icon:{kw['icon']}"
    if kw.get("delete"):
        if found is None:
            return {"error": "name the project to delete"}
        moved = (await _open_counts(session, user)).get(found.id, 0)
        await projects_route.delete_project(found.id, session, user)
        return _project_out(found, deleted=True, tasks_moved_to_default=moved)
    fields = {k: kw[k] for k in ("name", "description", "icon", "aliases")
              if kw.get(k) is not None}
    if found is None:
        if not kw.get("name"):
            return {"error": "give a name to make a project, or name one to change"}
        row = await projects_route.create_project(ProjectIn(
            id=new_id(), is_default=bool(kw.get("make_default")), **fields),
            session, user, Response())
        return _project_out(row, created=True, moved_aliases=row.moved_aliases)
    if "aliases" in fields:
        # Added to, not replaced: "isko novachan bhi kehte hain" keeps the rest.
        fields["aliases"] = [*found.aliases, *fields["aliases"]]
    if kw.get("archive") is not None:
        fields["archived"] = bool(kw["archive"])
    if kw.get("make_default"):
        fields["is_default"] = True
    row = await projects_route.patch_project(found.id, ProjectPatch(**fields), session, user)
    return _project_out(row, archived=row.archived_at is not None,
                        moved_aliases=row.moved_aliases)


async def _open_counts(session, user) -> dict[str, int]:
    from app import projects as P
    return await P.open_counts(session, user)


def _named(said: str, project) -> bool:
    """Whether the person's own words name this project — its name, a key or
    an alias, compared as letters and digits only, so *novachan me* names
    *novachan* and *NovaCart-chan* names *novacart chan*."""
    import re
    squash = lambda x: re.sub(r"[^0-9a-z]+", "", (x or "").casefold())  # noqa: E731
    heard = squash(said)
    names = [project.name, project.key, *project.aliases]
    return any(len(n) >= 3 and n in heard for n in map(squash, names))


#: Words a task title is built from that say nothing about which task it is —
#: the verb of doing work and the glue of either language.
_TASK_GLUE = frozenset({
    "work", "working", "on", "do", "doing", "to", "i", "have", "need", "must", "should",
    "kaam", "karna", "karne", "krna", "karo", "kar", "par", "pe", "per", "for", "with",
    "and", "aur", "of", "in", "at", "is", "it", "my", "mera", "meri", "mere", "hai", "tomorrow",
    "today", "kal", "aaj", "parso",
})


def _task_words(title: str) -> set[str]:
    import re
    return {w for w in re.findall(r"[0-9a-z]+", title.casefold())
            if w not in _TASK_GLUE and w not in _FILLER}


def _same_task(a: str, b: str) -> bool:
    """One task in two wordings: the same title, or exactly the same words that
    carry it, at least two of them — so "DB migration par kaam karna" matches
    "Work on DB migration", and neither matches "DB migration review"."""
    if " ".join(a.split()).casefold() == " ".join(b.split()).casefold():
        return True
    wa, wb = _task_words(a), _task_words(b)
    shared = wa & wb
    return len(shared) >= 2 and len(wa ^ wb) == 0


async def t_add_task(session, user, *, title: str, project: str | None = None,
                     guessed: bool = False, due: str | None = None,
                     priority: int | None = None, said: str | None = None) -> dict:
    """A task, placed by the one rule: the project named, or the default.

    Whether the placement was a guess is not left to the model to remember.
    When the turn's words are known, a project they do not name was the
    model's choice — marked, as every inferred value is (CLAUDE.md)."""
    from app import projects as P
    from app.models.work import Task
    from app.schemas.writes import TaskIn

    if project:
        found, err = await _one_project(session, user, project)
        if err:
            return err
        if said is not None:
            guessed = not _named(said, found)
    else:
        found, guessed = await P.default_project(session, user), False
    # The same task said twice is one task. Re-sending a sentence — or pasting
    # a reply back into the composer, as happened 2026-09-27 — added it again.
    # And the same task said in other words is one task too: asked twice for
    # "db migration" tomorrow, the model titled it "DB migration par kaam
    # karna" and then "Work on DB migration", and an exact match let the
    # second through (2026-10-01).
    when = date.fromisoformat(due) if due else None
    twin = next((t for t in (await session.scalars(select(Task).where(
        Task.user_id == user, Task.project_id == found.id, Task.deleted_at.is_(None),
        Task.archived_at.is_(None), Task.status != "done"))).all()
        if _same_task(t.title, title) and (t.due == when or t.due is None or when is None)),
        None)
    if twin is not None:
        return {"task_id": twin.id, "title": twin.title, "project": found.name,
                "project_id": found.id, "guessed": twin.project_guessed,
                "due": _d(twin.due), "priority": twin.priority, "already": True}
    row = await writes.create_task(TaskIn(
        id=new_id(), title=title.strip(), source="chat", project_id=found.id,
        due=date.fromisoformat(due) if due else None, priority=priority),
        session, user, Response())
    task = await session.get(Task, row.id)
    task.project_guessed = bool(guessed) and not found.is_default
    await session.commit()
    return {"task_id": task.id, "title": task.title, "project": found.name,
            "project_id": found.id, "guessed": task.project_guessed,
            "due": _d(task.due), "priority": task.priority}


#: Words that point at a task without describing it — dropped before matching.
_FILLER = frozenset({
    "wala", "wali", "wale", "waala", "waali", "vala", "task", "tasks", "todo", "to-do",
    "ko", "ka", "ki", "ke", "me", "mein", "se", "the", "a", "an", "that", "this",
    "one", "item", "wo", "woh", "ye", "yeh", "vo",
})


async def _one_task(session, user, ref: str):
    """(task, error). By id, then by what was said, among live tasks — open ones
    preferred over done:

    1. the exact title;
    2. the phrase inside a title;
    3. every word that carries it, once the filler that points at a task is
       dropped (*"veg filter wala task"*);
    4. the title sharing the most of those words, when one clearly leads and
       shares at least two (*"3 recipes dikhane"* — the English title says
       "show", the person said *dikhane*).

    A word that names a project narrows the search to that project rather than
    being looked for in the title: *"kestrel wala … task"* (both seen live,
    2026-09-27).
    """
    import re

    from app import projects as P
    from app.models.work import Task

    rows = list((await session.scalars(select(Task).where(
        Task.user_id == user, Task.deleted_at.is_(None)))).all())
    by_id = [t for t in rows if t.id == ref]
    if by_id:
        return by_id[0], None

    def squash(x: str) -> str:
        return re.sub(r"[^0-9a-z]+", "", (x or "").casefold())

    f = " ".join(ref.split()).casefold()

    def tokens(x: str) -> list[str]:
        return re.findall(r"[0-9a-z]+", (x or "").casefold())

    def said_in(w: str, toks: list[str]) -> bool:
        """A word is in a title as a WORD. Matching it as a substring made "3"
        find every title with a 3 in it — ACM-123, a date — and one run in
        five of the test tied (2026-09-27). Short words must match whole;
        from four letters a prefix counts, so "recipe" finds "recipes"."""
        if w in toks:
            return True
        return len(w) >= 4 and any(t.startswith(w) or (len(t) >= 4 and w.startswith(t))
                                   for t in toks)

    words = [w for w in tokens(f) if w not in _FILLER]
    names = {}
    for p in await P.live(session, user):
        for n in (p.name, p.key, *p.aliases):
            if len(squash(n)) >= 3:
                names[squash(n)] = p.id
    scoped = {names[squash(w)] for w in words if squash(w) in names}
    if scoped:
        words = [w for w in words if squash(w) not in names]
        narrowed = [t for t in rows if t.project_id in scoped]
        rows = narrowed or rows

    def pick(hits):
        open_hits = [t for t in hits if t.status != "done" and t.archived_at is None]
        return open_hits or hits

    def overlap(t) -> int:
        toks = tokens(t.title)
        return sum(1 for w in words if said_in(w, toks))

    stages = [lambda t: t.title.casefold() == f, lambda t: f in t.title.casefold(),
              lambda t: bool(words) and overlap(t) == len(words)]
    for match in stages:
        pool = pick([t for t in rows if match(t)])
        if len(pool) == 1:
            return pool[0], None
        if len(pool) > 1:
            return None, {"error": f"{ref!r} matches {len(pool)} tasks — ask which",
                          "tasks": [{"task_id": t.id, "title": t.title} for t in pool[:8]]}
    ranked = sorted(pick(rows), key=overlap, reverse=True)
    if ranked:
        best = overlap(ranked[0])
        runner_up = overlap(ranked[1]) if len(ranked) > 1 else 0
        if best >= 2 and best > runner_up:
            return ranked[0], None
    return None, {"error": f"no task like {ref!r}",
                  "tasks": [{"task_id": t.id, "title": t.title} for t in ranked[:6]]}


async def t_save_task(session, user, *, task: str | None = None, _said: str | None = None,
                      **kw) -> dict:
    """One tool for a task, the way `manage_habit` is one for a habit: no
    `task` adds one, a `task` names one to change. Two tools would have put the
    agent past the ceiling of twenty-five (spec/agent-tools.md), and a model
    picks between fewer tools more reliably."""
    if not task:
        if not kw.get("title"):
            return {"error": "give a title to add a task, or name one in `task` to change it"}
        out = await t_add_task(session, user, title=kw["title"], project=kw.get("project"),
                               guessed=bool(kw.get("guessed")), due=kw.get("due"),
                               priority=kw.get("priority"), said=_said)
        return out if "error" in out or out.get("already") else {**out, "added": True}
    kw.pop("guessed", None)
    return await _update_task(session, user, task=task, **kw)


async def _update_task(session, user, *, task: str, **kw) -> dict:
    """Tick, untick, rename, re-date, re-prioritise, archive — or move it."""
    from app import projects as P
    from app.schemas.writes import TaskPatch

    found, err = await _one_task(session, user, task)
    if err:
        return err
    patch: dict = {}
    if kw.get("done") is not None:
        patch["status"] = "done" if kw["done"] else "open"
    for k in ("title", "priority"):
        if kw.get(k) is not None:
            patch[k] = kw[k]
    if "due" in kw:
        patch["due"] = date.fromisoformat(kw["due"]) if kw["due"] else None
    if kw.get("archive") is not None:
        patch["archived"] = bool(kw["archive"])
    moved_to = None
    if kw.get("project"):
        dest, err = await _one_project(session, user, kw["project"])
        if err:
            return err
        patch["project_id"], moved_to = dest.id, dest.name
    if not patch:
        return {"error": "say what to change: done, title, due, priority, project or archive"}
    row = await writes.patch_task(found.id, TaskPatch(**patch), session, user)
    home = next((p for p in await P.live(session, user) if p.id == row.project_id), None)
    out = {"task_id": row.id, "title": row.title, "status": row.status,
           "project": home.name if home else None, "due": _d(row.due),
           "priority": row.priority, "archived": row.archived_at is not None,
           "moved_to": moved_to}
    if row.awaiting_move:
        # Ticked here, still unmoved there: the one thing to say next.
        out["move_in"] = {"source": row.source, "ref": row.source_ref,
                          "stage": row.source_state}
    return out


async def t_work_report(session, user, *, today: str | None = None,
                        project: str | None = None, status: str = "open",
                        due: str = "any", limit: int = 30,
                        show: bool = False) -> dict:
    """Tasks and projects, read: what is due, what is open where, what got done.

    Every count comes from rows. Without this the agent had no way to read a
    task, and *"aaj kya due hai?"* reached for paisa_report (2026-09-27). For
    a finished task the window is when it was finished; for an open one, when
    it is due."""
    from zoneinfo import ZoneInfo

    from app import projects as P
    from app.models.users import User
    from app.models.work import Task

    person = await session.get(User, user)
    tz = ZoneInfo(person.timezone or "Asia/Kolkata")
    day = date.fromisoformat(today) if today else datetime.now(tz).date()
    monday = day - timedelta(days=day.weekday())
    first = day.replace(day=1)
    last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    windows = {
        "overdue": (None, day - timedelta(days=1)), "today": (day, day),
        "tomorrow": (day + timedelta(days=1), day + timedelta(days=1)),
        "this_week": (monday, monday + timedelta(days=6)), "this_month": (first, last),
    }

    found = None
    if project:
        found, err = await _one_project(session, user, project)
        if err:
            return err
    projs = {p.id: p for p in await P.live(session, user)}
    q = select(Task).where(Task.user_id == user, Task.deleted_at.is_(None),
                           Task.archived_at.is_(None))
    if found is not None:
        q = q.where(Task.project_id == found.id)
    rows = list((await session.scalars(q.order_by(
        Task.due.nulls_last(), Task.priority.nulls_last(), Task.created_at))).all())

    def done_day(t) -> date | None:
        return t.done_at.astimezone(tz).date() if t.done_at else None

    def in_window(t) -> bool:
        if due == "any":
            return True
        if due == "undated":
            return t.due is None
        lo, hi = windows[due]
        when = done_day(t) if t.status == "done" else t.due
        if when is None:
            return False
        if due == "overdue":
            return t.status != "done" and when <= hi
        return lo <= when <= hi

    def wanted(t) -> bool:
        return (status == "all" or (status == "done") == (t.status == "done")) and in_window(t)

    hits = [t for t in rows if wanted(t)]
    per: dict[str, dict] = {}
    for t in rows:
        c = per.setdefault(t.project_id, {"open": 0, "overdue": 0, "due_today": 0,
                                          "done_this_week": 0})
        if t.status != "done":
            c["open"] += 1
            c["overdue"] += int(t.due is not None and t.due < day)
            c["due_today"] += int(t.due == day)
        elif (d := done_day(t)) and monday <= d <= monday + timedelta(days=6):
            c["done_this_week"] += 1
    return {
        "today": day.isoformat(),
        "count": len(hits),
        "tasks": [{"task_id": t.id, "title": t.title,
                   "project": projs[t.project_id].name if t.project_id in projs else None,
                   "status": t.status, "due": _d(t.due), "priority": t.priority,
                   "guessed": t.project_guessed, "from": t.source_ref if t.source_key else None,
                   "move_in_tracker": t.awaiting_move} for t in hits[:limit]],
        "truncated": len(hits) > limit,
        "projects": [{"project": p.name, "is_default": p.is_default, **per.get(p.id, {
            "open": 0, "overdue": 0, "due_today": 0, "done_this_week": 0})}
            for p in projs.values() if p.archived_at is None
            and (found is None or p.id == found.id)],
    }


async def t_people(session, user, **kw) -> dict:
    rows = await people_route.people(session, user, kind=kw.get("kind"))
    out = [{"counterparty_id": p.id, "name": p.display_name or p.raw_name, "kind": p.kind,
            "relation": p.relation, "sent_paise": p.sent_paise,
            "received_paise": p.received_paise, "still_out_paise": p.still_out_paise,
            "you_owe_paise": p.you_owe_paise, "typical_days": p.typical_days,
            "payments": p.tx_count, "last_day": _d(p.last_day)} for p in rows]
    if kw.get("with_money_open"):
        out = [p for p in out if p["still_out_paise"] or p["you_owe_paise"]]
    return {"people": out}


async def t_file_person(session, user, *, counterparty_id: str | None = None, **kw) -> dict:
    fields = {k: v for k, v in kw.items()
              if k in ("kind", "relation", "note", "display_name") and v is not None}
    if counterparty_id is None:
        if not kw.get("raw_name"):
            return {"error": "give a counterparty_id, or a raw_name to add someone"}
        row = await people_route.add_counterparty(CounterpartyIn(
            id=new_id(), raw_name=kw["raw_name"], **fields), session, user, Response())
    else:
        row = await people_route.patch_counterparty(
            counterparty_id, CounterpartyPatch(**fields), session, user)
    return {"counterparty_id": row.id, "name": row.display_name or row.raw_name,
            "kind": row.kind, "relation": row.relation}


async def t_places(session, user, **kw) -> dict:
    rows = await places_route.places(session, user, kind=kw.get("kind"))
    return {"places": [{"place_id": p.id, "name": p.name, "kind": p.kind,
                        "payments": p.payments, "spent_paise": p.spent_paise,
                        "last_seen": _d(p.last_seen),
                        "counterparty_name": p.counterparty_name} for p in rows]}


async def t_save_place(session, user, *, place_id: str | None = None, **kw) -> dict:
    if place_id is None:
        if not (kw.get("name") and kw.get("lat") is not None and kw.get("lng") is not None):
            return {"error": "a new place needs a name and coordinates"}
        row = await places_route.create_place(PlaceIn(
            id=new_id(), name=kw["name"], lat=kw["lat"], lng=kw["lng"],
            kind=kw.get("kind"), radius_m=kw.get("radius_m", 50),
            counterparty_id=kw.get("counterparty_id"), note=kw.get("note"),
        ), session, user, Response())
    else:
        patch = {k: v for k, v in kw.items()
                 if k in ("name", "kind", "radius_m", "counterparty_id", "note")
                 and v is not None}
        row = await places_route.patch_place(place_id, PlacePatch(**patch), session, user)
    return {"place_id": row.id, "name": row.name, "kind": row.kind,
            "payments": row.payments, "spent_paise": row.spent_paise}


#: A memory is read back into every prompt as a fact about the person. A bug
#: report is neither about them nor true for long: the app ships a fix and the
#: memory keeps asserting the old behaviour, which is exactly how "delete is
#: broken" survived the day delete started working. spec/done/agent-deletes.md.
#:
#: The rule that does the real work is in the prompt. This is a backstop for
#: the shape that already got through, so the phrases are deliberately narrow:
#: naming a part of Spica, not any noun a screen also has. "Old laptop, the
#: screen is broken" is a fact about the person and must survive. "cortex" is
#: the app's old name (CLAUDE.md), still said out of habit.
_PRODUCT = ("spica", "cortex", " the app", " this app", " the agent", " the ui", " the tool",
            "money log", "log delete", "delete log", "delete feature",
            "suggestion card", "confirm card", "meal card", "deck card")
_FAULT = ("broken", "not work", "doesn't work", "does not work", "nahi kar", "nahi ho",
          "kaam nahi", "work nahi", "fails", "crash", "glitch", "galat hai", "is wrong",
          "are wrong", "not supported", "nahi hota", "nahi hoti")


def _about_the_app(text: str) -> bool:
    low = f" {text.lower()} "
    if "bug" in low:
        return True
    return any(w in low for w in _PRODUCT) and any(w in low for w in _FAULT)


async def t_remember(session, user, *, slug: str, kind: str, text_: str,
                     _source: str = "cortex") -> dict:
    """A fact about the person, by slug. The chat's are `cortex` — the agent
    heard it, the person has not confirmed it. `_source` is the first run's
    `user`: there the question asked for it and the card showed it back
    (spec/done/onboarding-goals.md § Data). Underscored, so no model can set it."""
    if _about_the_app(text_):
        return {"error": "memory holds facts about the person, not about Spica. A bug "
                         "belongs in the repo — tell them what you cannot do instead, "
                         "and say it is worth writing down outside the app."}
    from app.routes import users as users_route
    row = await users_route.create_memory(MemoryIn(
        id=new_id(), slug=slug, kind=kind, text=text_, source=_source),
        session, user, Response())
    return {"id": row.id, "slug": row.slug, "kind": row.kind, "text": row.text}


#: What update_profile may write: the person's facts and targets, and nothing
#: the app owns — the first-run flag and the timezone are not the model's to set.
#: `age` is not a column; the server turns it into a date of birth.
PROFILE_FIELDS = ("display_name", "gender", "age", "dob", "height_cm", "city", "diet",
                  "protein_g_target", "kcal_target", "carbs_g_target", "fat_g_target",
                  "sleep_target_min", "step_target", "savings_target_paise", "weight_target_kg")


def _years(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


async def t_update_profile(session, user, *, field: str, value) -> dict:
    from zoneinfo import ZoneInfo

    from app.models.users import User
    from app.routes import users as users_route
    from app.schemas.users import UserPatch
    if field not in PROFILE_FIELDS:
        return {"error": f"{field} is not a profile field"}
    person = await session.get(User, user)
    today = datetime.now(ZoneInfo(person.timezone or "Asia/Kolkata")).date()
    if field == "age":
        # "28" is a year, not a date: 1 January of the year it gives
        # (spec/done/onboarding-goals.md § Data). Worked out here so the model never
        # does date arithmetic — a figure it never computes it cannot get wrong.
        try:
            age = float(value)
        except (TypeError, ValueError):
            age = None
        if age is None or not 13 <= age <= 100 or age != int(age):
            return {"error": "an age is whole years from 13 to 100 — nothing was written"}
        field, value = "dob", date(today.year - int(age), 1, 1)
    elif field == "dob":
        # An exact date is an age too, and held to the same check — or a date
        # in the future reads "Age → -4 years", and the age check is a field
        # away from being skipped.
        try:
            born = date.fromisoformat(str(value))
        except ValueError:
            return {"error": "a date of birth is YYYY-MM-DD — nothing was written"}
        if not 13 <= _years(born, today) <= 100:
            return {"error": "that date of birth makes them under 13 or over 100 — "
                             "nothing was written"}
        value = born
    elif field == "height_cm":
        # The column takes anything under 300; a person does not. "Five nine"
        # misread as 5.9 would be a 5.9 cm person and a BMI in the thousands.
        try:
            cm = float(value)
        except (TypeError, ValueError):
            cm = None
        if cm is None or not 50 <= cm <= 250:
            return {"error": "a height is in centimetres, 50 to 250 (5 ft 9 in is 175.3) — "
                             "nothing was written"}
    row = await users_route.patch_me(UserPatch(**{field: value}), session, user)
    if field == "dob":
        # Shown as an age wherever it is shown, never as the date.
        return {"dob": _d(row.dob), "age": _years(row.dob, today) if row.dob else None}
    return {field: _d(getattr(row, field, None))}


# ─── the table ───────────────────────────────────────────────────────────────

def _tool(name: str, desc: str, props: dict, required: list[str],
          fn: Callable) -> dict:
    return {"name": name, "description": desc, "fn": fn,
            "schema": {"type": "object", "properties": props, "required": required,
                       "additionalProperties": False}}


#: Money fields named by what they mean, where a bare name read both ways.
#: `still_out` was read as money the person owes as often as money owed to
#: them: "Amit ko ₹4,000 dene baaki hain", the debt reversed (2026-10-09).
_OWED = {"still_out": "they_owe_you", "you_owe": "you_owe_them",
         "out": "others_owe_you", "owe": "you_owe_others", "remaining": "still_to_settle"}


def _rupees(paise) -> str:
    if paise is None:
        return "no data"
    r = round(float(paise) / 100)
    return f"-₹{-r:,}" if r < 0 else f"₹{r:,}"


#: Whether a read's rows will show as a card under the reply — said in the
#: result, so the reply neither types the list out again nor points at a card
#: that is not there ("2 tasks complete kiye; list card mein hai", with no
#: card, 2026-10-10). Mirrors `cards.from_tool`.
def _card_note(name: str, args: dict, result: Any) -> str | None:
    if not isinstance(result, dict) or result.get("error"):
        return None
    shown = bool((args or {}).get("show"))
    if name == "work_report":
        if shown and (args or {}).get("status", "open") in ("open", "all"):
            return ("the To-do card under your reply lists these tasks — never type the "
                    "whole list; name the one to three that answer the question")
        return "no card shows these — answer in the sentence, naming the ones that answer"
    if name == "paisa_report" and "commitments" in ((args or {}).get("fields") or []):
        return ("the Commitments card under your reply lists every line with its ⋮ — "
                "never type the list out; say the total owed and the one or two that matter")
    if name in ("paisa_report", "diet_report") and "rows" in ((args or {}).get("fields") or []):
        if shown:
            return ("a table under your reply shows these rows — never type them all out; "
                    "name the one to three that answer the question")
        return "no card shows these rows — answer in the sentence"
    return None


def for_model(name: str, result: Any, args: dict | None = None) -> Any:
    """A tool's result as the model reads it — the cards are built from the
    raw result before this runs, so only the model's view changes.

    **Money arrives in rupees, already rounded.** The model converted paise
    itself and said ₹21,252 for 212,522 paise — ₹2,125, off by ten
    (2026-10-09). A figure it never computes is a figure it cannot get wrong.

    **A debt is named by who owes whom**, in udhaar and in people.

    **A meal's estimate says it is whole.** `unresolved` meant "not in the
    library", and the model read it as "not in the total" and called a
    complete estimate partial; with a model estimate, everything said is in it.
    """
    def walk(v, owed: bool):
        if isinstance(v, dict):
            out = {}
            for k, x in v.items():
                if ((k.endswith("_paise") or k == "paise")
                        and (x is None or isinstance(x, (int, float, Decimal)))):
                    # `by_category` sends a bare `paise`: that is an amount too.
                    base = "amount" if k == "paise" else k[: -len("_paise")]
                    key = _OWED.get(base, base) if owed else base
                    out[key if key not in v else f"{key}_rupees"] = _rupees(x)
                else:
                    out[k] = walk(x, owed or k in ("udhaar", "people"))
            if owed and v.get("kind") in ("lent", "borrowed"):
                out["who_owes"] = "they owe you" if v["kind"] == "lent" else "you owe them"
            return out
        if isinstance(v, list):
            return [walk(x, owed) for x in v]
        return v

    out = walk(result, name == "people")
    note = _card_note(name, args or {}, result)
    if note and isinstance(out, dict):
        out["card"] = note
    if (name == "log_meal" and isinstance(out, dict)
            and (out.get("meal") or {}).get("estimated_kcal") is not None):
        out["total_is"] = ("an estimate for everything they said — `assumption` names what "
                           "was assumed. It is not partial.")
        out["not_in_library"] = out.pop("unresolved", [])
        out.pop("needs_quantity", None)
    return out


DATE = {"type": "string", "description": "YYYY-MM-DD"}
#: Whether a read is shown as a card — the agent's call, said explicitly. Rows
#: read to find one number ("Blue Tokai pe kitna kharcha hua?") came back as a
#: table nobody asked for (2026-10-10).
SHOW = {"type": "boolean",
        "description": "true only when they asked to SEE the list itself — 'dikhao', "
                       "'kya kya', 'last 3', 'history'. false when you read it to find a "
                       "number, an id or a fact: then nothing is shown and you answer in "
                       "the sentence"}
MONEY = {"type": "integer", "description": "integer paise, never rupees (₹25 is 2500). "
         "Only an amount they said: with none said, do not call — ask."}

TOOLS: list[dict] = [
    _tool("paisa_report",
          "Money numbers for a date range. Ask only for the fields you need. "
          "'balance' answers 'how much is left' — left, committed, free, and what came "
          "in and went out — already worked out; never subtract it yourself, because "
          "'spent' is discretionary expenses ONLY and excludes fixed costs and lendings. "
          "'commitments' answers 'kya kya committed hai / kitna pay karna baaki hai' — "
          "one line per thing owed this month, with its id, expected, paid, owed, due day "
          "and whether it repeats or is skipped; to CHANGE one use manage_commitment. "
          "Do NOT use 'fixed' for that: 'fixed' is what has ALREADY been paid, the "
          "opposite set. "
          "'udhaar' gives the totals AND `open`: every unsettled lending and borrowing "
          "with its id — that id is the `settles_id` a repayment needs. For a person's "
          "history and habits call `people` instead. "
          "'rows' returns the actual transactions, newest first, capped at 30 — for "
          "'last 5' pass rows_limit=5. Rows are shown as a table only with show=true — "
          "when they asked to SEE payments; to find a number or an id, leave it false. "
          "'to_review' lists payments the nightly categoriser was unsure about and "
          "the user has not answered — each with its guess and why. Not date-scoped. "
          "`from` left out is the 1st of the month: for 'aaj' pass from=to=today. The "
          "result names its `period`; `no_records` means nothing was logged then — say "
          "there is no data, never ₹0. Today's spend and limit are already in the "
          "turn's context; answer those from there.",
          {"from": DATE, "to": DATE,
           "fields": {"type": "array", "items": {"type": "string",
                                                 "enum": sorted(PAISA_FIELDS)}},
           "category": {"type": "string"}, "counterparty_id": {"type": "string"},
           "after": {"type": "string", "description": "cursor from a previous page"},
           "show": SHOW},
          ["to", "fields"], t_paisa_report),

    _tool("log_payment",
          "Record money moving — only with an amount the person said; with none said, "
          "do not call this at all: ask. kind: expense | income | lent | borrowed | repayment | "
          "transfer. A lent or borrowed row must name the person. category: the closest "
          "of the categories listed in the prompt — an auto, cab or metro ride is "
          "Transport, never food. A lent, borrowed or repayment row is always filed as "
          "Udhaar, whatever you pass. A NEW payment only: the same thing again with an "
          "amount ('chai 20' twice in a day) is a second payment. A sentence that "
          "corrects one already logged — 'ki thi', 'sorry', '90k sorry', 'nahi, 50 tha' — "
          "is correct_payment on that row, never a second log_payment. With no amount "
          "said, ask for it; never log 0.",
          {"amount_paise": MONEY,
           "direction": {"type": "string", "enum": ["debit", "credit"]},
           "kind": {"type": "string",
                    "enum": ["expense", "income", "lent", "borrowed", "repayment", "transfer"]},
           "category": {"type": "string"}, "description": {"type": "string"},
           "local_day": DATE, "time": {"type": "string", "description": "HH:MM:SS, local — only a clock time they said ('8 baje', 'subah 9 bje'); otherwise leave it out and the moment of their message is used"},
           "counterparty_name": {"type": "string"},
           "method": {"type": "string", "enum": ["cash", "digital"]},
           "note": {"type": "string"},
           "settles_id": {"type": "string",
                          "description": "for a repayment: the id of the lending it pays. "
                                         "Read it from paisa_report rows or from people — "
                                         "never from memory or an earlier turn"},
           "category_stated": {"type": "boolean",
                               "description": "true only when the user named the category "
                                              "themselves; otherwise it is your guess"}},
          ["amount_paise", "direction", "kind", "category", "description", "local_day"],
          t_log_payment),

    _tool("correct_payment",
          "Change a payment already logged — the day it happened, category, description, "
          "amount, place, counterparty. Also how a category guess is confirmed: passing "
          "the category the user named — or the guess they said yes to — marks it "
          "confirmed. The id of a payment logged earlier in this conversation is in "
          "the turn's `[rows written …]` list — use it, no lookup needed. "
          "Otherwise paisa_report(fields=['rows']). Never invent one.",
          {"transaction_id": {"type": "string",
                              "description": "from a report's rows, never constructed"},
           "local_day": dict(DATE, description="move the payment to this day"),
           "category": {"type": "string"},
           "description": {"type": "string"}, "amount_paise": MONEY,
           "note": {"type": "string",
                    "description": "the USER's words about the row. Never your own "
                                   "intentions, and never a record of what you could not do"},
           "place_id": {"type": "string"},
           "counterparty_name": {"type": "string"},
           "commitment_id": {"type": ["string", "null"],
                             "description": "the commitment this payment pays; null for "
                             "none. Ids come from paisa_report `commitments`, never "
                             "from memory"}},
          ["transaction_id"], t_correct_payment),

    _tool("categorise_now",
          "Run the categoriser now over payments the user never confirmed a category "
          "for, or filed as Other. Free tiers first, one model call for the rest. "
          "Fills the sure ones silently. `to_review` in the result is every payment "
          "still waiting on the user, this run's and earlier ones' — answer from that, "
          "and say how many there are. `examined: 0` only means nothing NEW was looked "
          "at; it never means there is nothing to review. Use for 'aaj ke payments dekh "
          "lo' or 'doubtful payments'. Never changes a row the user categorised "
          "themselves.",
          {"local_day": {**DATE, "description": "YYYY-MM-DD; omit for everything pending"}},
          [], t_categorise_now),

    _tool("delete_payment",
          "Remove a payment that should not exist at all — a double entry, or something "
          "that never happened. A payment with a WRONG VALUE is correct_payment instead; "
          "the correction is data worth keeping. Soft delete, so the row is recoverable. "
          "Its id: the turn's `[rows written …]` list, or "
          "paisa_report(fields=['rows']); never invent one.",
          {"transaction_id": {"type": "string",
                              "description": "from a report's rows, never constructed"}},
          ["transaction_id"], t_delete_payment),

    _tool("diet_report",
          "Food, sleep, weight, habits and pantry for a date range. Ask only for the "
          "fields you need — weight, sleep and today's totals are fields of their own, "
          "never answered by fetching rows. 'today' carries protein_left_g — lead with "
          "that. Meals fetched with 'rows' show as a table only with show=true. Every meal "
          "you fetch with 'rows' is shown to the user on a card: fetch rows when they "
          "asked to see what they ate, or to find one meal_id — never just to look "
          "around before answering something else.",
          {"from": DATE, "to": DATE,
           "fields": {"type": "array", "items": {"type": "string",
                                                 "enum": sorted(DIET_FIELDS)}},
           "meal_type": {"type": "string"}, "after": {"type": "string"},
           "show": SHOW},
          ["to", "fields"], t_diet_report),

    _tool("log_meal",
          "Log a NEW meal the person ATE — 'khaya', 'piya', 'had', 'kha liya' — in their "
          "own words. Food bought ('laya', 'kharida', 'le aaya', 'mangaya') is not a meal: "
          "bought for the house is pantry_move, ordered food is a payment and a "
          "question. Resolves each item "
          "against the dish and food library; unresolved items are reported, never "
          "invented. Only for a meal not logged yet. Anything the user adds about a meal "
          "you just logged — what it was ('boiled eggs'), how much of something ('dal ek "
          "katori thi', 'roti 40 g each'), what the salad was — is correct_meal on that "
          "meal, whose id is in the turn's `[rows written …]` list. "
          "Never a second log_meal: it makes a second plate, and the day's protein "
          "counts the food twice. The result's total is an estimate for the whole "
          "plate; `assumption` says what it assumed.",
          {"text_said": {"type": "string",
                         "description": "the food exactly as the user said it, e.g. '2 roti "
                                        "aur dal' — never your commentary, an assumption, "
                                        "or a clarification they gave later"},
           "meal_type": {"type": "string",
                         "description": "Breakfast | Lunch | Snack | Dinner"},
           "local_day": DATE, "time": {"type": "string", "description": "HH:MM:SS, local — only a clock time they said ('8 baje', 'subah 9 bje'); otherwise leave it out and the moment of their message is used"}, "note": {"type": "string"},
           "dish_id": {"type": "string",
                       "description": "only when the dish is already known by id — skips "
                                      "resolution; text_said is then its name"},
           "servings": {"type": "number"}},
          ["text_said", "meal_type", "local_day"], t_log_meal),

    _tool("correct_meal",
          "Change a meal already logged, including the day it was eaten — and the way "
          "to apply anything the user adds about a meal just logged: a portion, what a "
          "vague item was. Work out the revised kcal and protein from what they said "
          "(it stays marked as your estimate) and keep `dish` as the food they named, "
          "never with your notes appended. The meal_id of a meal logged earlier in this "
          "conversation is in the turn's `[rows written …]` list; otherwise "
          "diet_report(fields=['rows']). Never invent one.",
          {"meal_id": {"type": "string",
                       "description": "from a report's rows, never constructed"},
           "local_day": dict(DATE, description="move the meal to this day"),
           "dish": {"type": "string"},
           "kcal": {"type": "integer"}, "protein_g": {"type": "number"},
           "meal_type": {"type": "string"},
           "note": {"type": "string", "description": "the USER's words about the row"}},
          ["meal_id"], t_correct_meal),

    _tool("delete_meal",
          "Remove a meal that should not exist at all — logged twice, or never eaten. "
          "A meal with the wrong dish or macros is correct_meal instead. Soft delete, "
          "and whatever the plate took off the shelf goes back on it. Its id: the "
          "`[rows written …]` list, or "
          "diet_report(fields=['rows']); never invent one.",
          {"meal_id": {"type": "string",
                       "description": "from a report's rows, never constructed"}},
          ["meal_id"], t_delete_meal),

    _tool("log_day",
          "The day's facts in one write: sleep, weight, and habit ticks — only what "
          "they said they did ('aaj workout kiya' ticks Workout). The habits they "
          "track are listed in every turn's context: never call this to look. A name "
          "not tracked comes back unticked; starting one is manage_habit. A sleep or "
          "weight they correct ('sorry 7 ghante soya tha') is this tool again with the "
          "right number: it replaces the day's value. A weight said as a guess — "
          "'around 72', '71 ke aas paas' — is approximate=true; a reading is not.",
          {"local_day": DATE, "time": {"type": "string", "description": "HH:MM:SS, local — only a clock time they said ('8 baje', 'subah 9 bje'); otherwise leave it out and the moment of their message is used"},
           "sleep_hours": {"type": "number"},
           "weight_kg": {"type": "number"},
           "approximate": {"type": "boolean", "description": "true only when they gave "
                           "the weight as a guess; leave it out for a reading"},
           "note": {"type": "string"},
           "habits": {"type": "array", "items": {"type": "object", "properties": {
               "habit": {"type": "string", "description": "the habit's name, or the "
                         "habit_id manage_habit returned"},
               "amount": {"type": "number"},
               "note": {"type": "string"}}, "required": ["habit"],
               "additionalProperties": False}}},
          ["local_day"], t_log_day),

    _tool("pantry_move",
          "Stock arriving ('purchase') or a stock-take ('opening'). Food bought for the "
          "house — '200g paneer laya', 'atta kharida', 'doodh le aaya' — is a purchase "
          "here and never a meal. Consumption is "
          "never posted by hand — logging a meal spends it. Buying a food the pantry "
          "does not track yet starts tracking it — the result then says now_tracked; "
          "say it is on the pantry list now.",
          {"food_name": {"type": "string"}, "quantity": {"type": "integer"},
           "kind": {"type": "string", "enum": ["purchase", "opening", "correction", "waste"]},
           "local_day": DATE},
          ["food_name", "quantity", "kind", "local_day"], t_pantry_move),

    _tool("suggest_dishes",
          "Candidate dishes with their signals — cookable now, protein, minutes, how "
          "long since you had it. You rank them; the database has no score.",
          {"local_day": DATE, "minutes": {"type": "integer"},
           "meal_type": {"type": "string"}},
          ["local_day"], t_suggest_dishes),

    _tool("dishes_search", "Search the whole dish pool by name or alias.",
          {"q": {"type": "string"}}, ["q"], t_dishes_search),

    _tool("keep_dish",
          "Star a dish. With a dish_id it saves that one; with a name it creates a "
          "private dish and saves it. 'X save kar lo' saves it now — not in the library, "
          "pass its name, and unknown nutrition stays unknown. Never ask for the recipe "
          "first; add steps or ingredients when they give them.",
          {"dish_id": {"type": "string"}, "name": {"type": "string"},
           "serving_label": {"type": "string"}, "protein_g": {"type": "number"},
           "kcal": {"type": "integer"}, "minutes": {"type": "integer"},
           "meal_type": {"type": "string"}, "steps": {"type": "string"},
           "source_url": {"type": "string"}, "note": {"type": "string"}},
          [], t_keep_dish),

    _tool("exercises",
          "The exercise library, filtered — a read, for suggesting or finding one. A habit "
          "is not an exercise: 'aaj workout kiya' ticks the Workout habit with log_day. "
          "'leg lagana hai, 20 minute' is muscle_group=legs, minutes=20. `tried`=true "
          "keeps only exercises done before; leave it out to search everything. "
          "Nothing found under a filter is not 'not in the library': search again "
          "without it before saying so.",
          {"q": {"type": "string"},
           "kind": {"type": "string", "enum": ["strength", "cardio", "mobility", "stretch"]},
           "muscle_group": {"type": "string"}, "equipment": {"type": "string"},
           "minutes": {"type": "integer"},
           "tried": {"type": "boolean", "description": "true: only ones done before. "
                     "Usually leave it out"}},
          [], t_exercises),

    _tool("log_exercise",
          "Mark an exercise done (tried += 1) when they say they did it — 'aaj goblet "
          "squat kiya' — or add a new one to the library they asked for. Never on a "
          "question or a suggestion: suggesting is the `exercises` read.",
          {"exercise_id": {"type": "string"}, "name": {"type": "string"},
           "kind": {"type": "string", "enum": ["strength", "cardio", "mobility", "stretch"]},
           "muscle_group": {"type": "string"}, "equipment": {"type": "string"},
           "typical_minutes": {"type": "integer"}, "steps": {"type": "string"},
           "source_url": {"type": "string"}, "local_day": DATE,
           "did": {"type": "boolean", "description": "false to add without marking it done"}},
          [], t_log_exercise),

    _tool("manage_habit",
          "Start tracking a habit, rename one, change what it counts, or stop tracking. "
          "A name alone starts one; habit_id names an existing one to change, "
          "and delete=true stops that one. "
          "direction: 'build' for something you want more of, 'break' for less. "
          "unit is what a tick can carry an amount in — minutes, units — or leave it "
          "out when a tick is the whole fact, like a cigarette. This does NOT tick a "
          "habit; that is log_day. 'X track karo' / 'X bhi track karo' / 'track karna "
          "shuru karo' IS the ask: start it, do not ask again. A name already tracked "
          "is that habit, left as it is — it comes back with already_tracked, never a "
          "second one; changing it is habit_id. Never start one they did not ask for.",
          {"habit_id": {"type": "string", "description": "which habit to change — its "
                        "name as the user says it, or an id from an earlier result"},
           "name": {"type": "string", "description": "the name to start it under, or "
                    "the new name when habit_id is given"},
           "direction": {"type": "string", "enum": ["build", "break"]},
           "unit": {"type": "string"},
           "delete": {"type": "boolean"}},
          [], t_manage_habit),

    _tool("manage_commitment",
          "Make, change, skip or delete something the user OWES each month — rent, an EMI, "
          "a subscription, a loan: an obligation, never everyday spending (food, health, "
          "transport are not commitments). A name + amount + category makes one, and it "
          "repeats every month by default; `commitment` (its name as the user says it, or "
          "an id) picks one to change. amount_paise changes what is expected this month; "
          "skip=true is 'not this month' (skip=false undoes it); repeats=false is 'this "
          "no longer comes every month'; delete=true removes it and ends the repeat; "
          "pay_with is a payment id that should count toward it. This does NOT log a "
          "payment — 'rent de diya' is log_payment, which links itself. Use this, never "
          "correct_payment, to change what is owed. Reads are paisa_report `commitments`.",
          {"commitment": {"type": "string", "description": "which one to change — its name as "
                          "the user says it, or an id from paisa_report `commitments`"},
           "name": {"type": "string"},
           "amount_paise": MONEY,
           "category": {"type": "string"},
           "category_stated": {"type": "boolean", "description": "true only when the user "
                               "named the category themselves"},
           "due_day": {"type": "integer", "minimum": 1, "maximum": 31,
                       "description": "day of the month it falls due"},
           "repeats": {"type": "boolean"},
           "another": {"type": "boolean", "description": "true only when the user said this "
                       "is a second, separate commitment with a name already in use"},
           "skip": {"type": "boolean"},
           "delete": {"type": "boolean"},
           "pay_with": {"type": "string", "description": "a payment id — from the turn's "
                        "`[rows written …]` list or a report, never from memory"}},
          [], t_manage_commitment),

    _tool("manage_project",
          "Make a project, change one, archive or delete it. A name alone makes one; "
          "`project` names one to change — its name, an alias, or an id. `aliases` are "
          "what it is called elsewhere (a Linear project, a repo, a nickname) and are "
          "ADDED to the ones it has. delete=true moves its tasks to the default project. "
          "Never make a project the person has not asked for — if they name one that "
          "does not exist, ask first.",
          {"project": {"type": "string", "description": "which project to change"},
           "name": {"type": "string", "description": "the name to make it under, or the "
                    "new name when `project` is given"},
           "description": {"type": "string", "description": "one or two lines of what it "
                           "is, in their words"},
           "icon": {"type": "string", "description": "an emoji, or icon:<name> from: "
                    "briefcase code home heart book cart rocket star bolt leaf chat money "
                    "globe tool person flag"},
           "aliases": {"type": "array", "items": {"type": "string"}},
           "archive": {"type": "boolean"}, "delete": {"type": "boolean"},
           "make_default": {"type": "boolean"}},
          [], t_manage_project),

    _tool("work_report",
          "Tasks and projects, read — the ONLY way to answer a question about tasks: "
          "what is due today or tomorrow, what is late, what is open in a project, what "
          "got done this week. `due` picks the window (for done tasks, when they were "
          "finished); `project` narrows to one; status open by default. `projects` "
          "carries each one's open, overdue, due-today and done-this-week counts — read "
          "them, never add them up yourself. Never answer a task question from "
          "paisa_report: that is money only. The user sees their live task list as a "
          "card under your reply when you pass show=true — do so when they asked to see "
          "their tasks; then do not list them again: say in a sentence "
          "what matters — how many are open, what is late, what is due today. Which "
          "projects they have is listed in the prompt: answer that without this tool.",
          {"today": DATE, "project": {"type": "string"},
           "status": {"type": "string", "enum": ["open", "done", "all"]},
           "due": {"type": "string", "enum": ["any", "overdue", "today", "tomorrow",
                                              "this_week", "this_month", "undated"]},
           "limit": {"type": "integer"},
           "show": SHOW},
          [], t_work_report),

    _tool("save_task",
          "Add a work or personal task, or change one. Leave `task` out to ADD: give "
          "`title`, and `project` if they named one. When they named none and exactly "
          "one project plainly fits — read the projects and their descriptions in the "
          "prompt — pass it with guessed=true and say where you put it; otherwise leave "
          "`project` out and it goes to the default project. Give `task` (its id, or "
          "words from its title) to CHANGE one: done=true ticks it, done=false reopens "
          "it, or rename it, re-date it (due=null clears), re-prioritise, archive, or "
          "move it to another `project`. A project that does not exist is an error you "
          "ask about, never one you make. When the result has `move_in`, the task came "
          "from Linear: remind them to move it forward there — Spica never does. When "
          "the result has `already`, that task was on their list before — say so in "
          "one line, and never add it again in other words.",
          {"task": {"type": "string", "description": "which task to change — leave out "
                    "to add a new one"},
           "title": {"type": "string", "description": "the new task, short, as they would "
                     "write it — or its new title"},
           "project": {"type": "string"}, "guessed": {"type": "boolean"},
           "done": {"type": "boolean"},
           "due": {"type": ["string", "null"], "description": "YYYY-MM-DD, or null"},
           "priority": {"type": "integer", "enum": [1, 2, 3], "description": "1 most urgent"},
           "archive": {"type": "boolean"}},
          [], t_save_task),

    _tool("people",
          "Everyone the ledger knows: sent, received, `they_owe_you`, `you_owe_them`, "
          "typical "
          "days to repay, and when you last dealt with them. with_money_open=true for "
          "just the udhaar. This is the ONLY place names and dates for open lendings "
          "live, and it looks at all time — a lending from June is still open in "
          "September and will not be in a September date range.",
          {"kind": {"type": "string", "enum": ["person", "shop", "service"]},
           "with_money_open": {"type": "boolean"}},
          [], t_people),

    _tool("file_person",
          "Say what a counterparty is, or add someone the ledger has not seen.",
          {"counterparty_id": {"type": "string"}, "raw_name": {"type": "string"},
           "kind": {"type": "string", "enum": ["person", "shop", "service"]},
           "relation": {"type": "string"}, "display_name": {"type": "string"},
           "note": {"type": "string"}},
          [], t_file_person),

    _tool("places", "Pins on the map, with what was spent at each.",
          {"kind": {"type": "string"}}, [], t_places),

    _tool("save_place",
          "Add or edit a pin. Linking a counterparty makes the pin show that person's "
          "spend with nothing tagged by hand.",
          {"place_id": {"type": "string"}, "name": {"type": "string"},
           "lat": {"type": "number"}, "lng": {"type": "number"},
           "kind": {"type": "string",
                    "enum": ["home", "office", "shop", "eat", "hangout", "pickup", "gym", "other"]},
           "radius_m": {"type": "number"}, "counterparty_id": {"type": "string"},
           "note": {"type": "string"}},
          [], t_save_place),

    _tool("remember",
          "Store a lasting fact about the PERSON — how they like to be answered, what "
          "they are working on. 'yaad rakhna …' / 'remember …' is always this tool, "
          "whatever the fact mentions (gym, food, money): never a habit or an exercise. "
          "Never a fact about their data, and only when they ask. A question about what "
          "you remember is answered from 'Who they are' in the prompt — never a call "
          "here.",
          {"slug": {"type": "string", "description": "stable handle, e.g. 'learning-style'"},
           "kind": {"type": "string",
                    "enum": ["identity", "preference", "style", "interest", "project",
                             "reference"]},
           "text_": {"type": "string", "description": "the fact, in their words"}},
          ["slug", "kind", "text_"], t_remember),

    _tool("update_profile",
          "Set one fact about the person, or one target — one field per call. Facts: "
          "display_name; gender (female, male or other) only as they said it, never "
          "from a name; age in whole years as they said it — the server turns it into "
          "a date of birth, so never work a date out yourself; dob only for an exact "
          "date they gave (YYYY-MM-DD); height_cm in centimetres (5 ft 9 in is 175.3); "
          "city; diet (veg, nonveg, eggetarian or any). Targets: protein, kcal, carbs, "
          "fat, sleep minutes, steps, savings_target_paise (a month's saving, in paise) "
          "and weight_target_kg — the weight they aim to reach, never the change ('lose "
          "5 kg' at 72 kg is 67). Only what they said: a field they left out stays as "
          "it is. 'Actually I'm 29' is this tool again — it replaces the value.",
          {"field": {"type": "string", "enum": list(PROFILE_FIELDS)},
           "value": {"type": ["number", "string"]}},
          ["field", "value"], t_update_profile),
]

BY_NAME: dict[str, dict] = {t["name"]: t for t in TOOLS}


def schemas(tools: list[dict] | None = None) -> list[dict]:
    """The tool list in the Responses API's flat shape. Anthropic's differs
    only in the key names. `strict` is off explicitly: these schemas mark
    optional fields by leaving them out of `required`, which strict mode
    forbids, and the API would otherwise decide per call whether to try.
    The chat's whole table unless another agent offers its own list."""
    return [{"type": "function", "name": t["name"], "description": t["description"],
             "parameters": t["schema"], "strict": False}
            for t in (TOOLS if tools is None else tools)]


#: Tools that read the turn's own words, passed as `_said` — never an argument
#: the model can set.
HEARS = frozenset({"save_task"})


async def run(session: AsyncSession, user: str, name: str, args: dict,
              default_time: str | None = None, said: str | None = None,
              registry: dict[str, dict] | None = None) -> dict:
    """Execute one tool call. A refusal from the route comes back as data, not
    an exception — the model reads it and tells the user why.

    Each call runs inside a **savepoint**, so a failure undoes that tool and
    nothing else. A plain `rollback()` would also discard the conversation row
    and any tool that already succeeded this turn, which is how a refused
    lending came to wipe the thread it was refused in.

    `registry` is what the calling agent was offered — the chat's whole table
    when None. A name outside it is unknown here, whatever the model tries.
    """
    tool = (BY_NAME if registry is None else registry).get(name)
    if tool is None:
        return {"error": f"no tool called {name!r}"}
    # The caller's wall clock, for a write that did not state one. The model
    # may still pass `time` and that wins.
    if default_time and "time" in tool["schema"]["properties"] and "time" not in args:
        args = {**args, "time": default_time}
    args = {k: v for k, v in args.items() if not k.startswith("_")}
    if name in HEARS and said is not None:
        args["_said"] = said
    savepoint = await session.begin_nested()
    try:
        out = await tool["fn"](session, user, **args)
    except HTTPException as e:
        # A route that already committed has ended the savepoint; rolling back
        # a finished savepoint raises instead of being a no-op.
        if savepoint.is_active:
            await savepoint.rollback()
        return {"error": e.detail, "status": e.status_code}
    except (TypeError, ValueError, KeyError) as e:
        if savepoint.is_active:
            await savepoint.rollback()
        return {"error": str(e)}
    except IntegrityError as e:
        # A database constraint the route did not catch first. It used to
        # escape as a 500 and the user saw "Didn't reach the server"; the model
        # can read this and say what it tried to do.
        if savepoint.is_active:
            await savepoint.rollback()
        return {"error": f"the ledger refused this write: {getattr(e, 'orig', e)}"}
    if savepoint.is_active:
        try:
            # The write flushes here, not inside the tool — so a constraint the
            # tool did not trip until now has to be caught here too. A null
            # protein on a correction ended the whole turn as a 500
            # (2026-10-10).
            await savepoint.commit()
        except IntegrityError as e:
            await savepoint.rollback()
            return {"error": f"the ledger refused this write: {getattr(e, 'orig', e)}"}
    return out
