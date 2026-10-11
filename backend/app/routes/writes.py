"""
The write surface. spec/in-progress/ledger-writes.md.

POST creates, PATCH fixes in place, DELETE soft-deletes. The client supplies
the id, so a repeated POST is a replay and returns the existing row — a retry
is a retry, not an edit.

`user_id` comes from the auth seam on every write and is never read from the
body: a request cannot write into someone else's rows even by accident.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app import commitments as K
from app.auth import CurrentUser
from app.db import SessionDep
from app.models.commitments import Commitment
from app.models.diet import Day, DishItem, HabitLog, MealItem, MealLog, PantryItem, PantryMove
from app.models.paisa import Counterparty, Prediction, Transaction
from app.models.work import Task
from app.schemas.deck import DayOut, HabitLogOut, MealOut, PantryMoveOut, TaskOut, TransactionOut
from app.schemas.writes import (
    DayIn,
    HabitLogIn,
    HabitLogPatch,
    MealIn,
    MealPatch,
    PantryMoveIn,
    PantryMovePatch,
    Patch,
    TaskIn,
    TaskPatch,
    TransactionIn,
    TransactionPatch,
)

router = APIRouter(tags=["writes"])


def now() -> datetime:
    return datetime.now(UTC)


async def existing(session, model, row_id: str, user: str):
    """The row this user owns with this id, deleted or not. Replay and 404
    checks both start here."""
    return await session.scalar(select(model).where(model.id == row_id, model.user_id == user))


async def live_or_404(session, model, row_id: str, user: str):
    row = await existing(session, model, row_id, user)
    if row is None or row.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__tablename__}: no such row")
    return row


def apply(row, patch: Patch) -> dict:
    """Only the fields the client actually sent. Absent = untouched; null = cleared."""
    changes = patch.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(row, key, value)
    return changes


async def replay_or_create(session, model, body, user: str, response: Response,
                           exclude: set[str] | None = None):
    """POST semantics: an id already written returns the stored row with 200 and
    ignores the body; a new id is inserted and returns 201.

    `exclude` is for bodies that carry child rows — a meal's lines are part of
    the request but not columns on `meal_logs`, and the caller writes them.
    """
    found = await existing(session, model, body.id, user)
    if found is not None:
        response.status_code = status.HTTP_200_OK
        return found, False
    row = model(user_id=user, **body.model_dump(exclude=exclude or set()))
    session.add(row)
    response.status_code = status.HTTP_201_CREATED
    return row, True


# ─── pantry derivation ───────────────────────────────────────────────────────

async def dish_quantities(
    session, dish_id: str, servings: Decimal | float = 1, depth: int = 0
) -> dict[str, int]:
    """How much of each food one serving of this dish spends, in that food's own
    unit — 60 g of atta, 2 eggs — expanding component dishes × their servings.
    Ghar ka dinner is two rotis' worth of atta."""
    if depth > 5:  # a dish that contains itself is a data error, not a stack overflow
        return {}
    items = (await session.scalars(
        select(DishItem).where(DishItem.dish_id == dish_id, DishItem.deleted_at.is_(None))
    )).all()
    grams: dict[str, int] = {}
    for it in items:
        if it.food_id and it.quantity:
            grams[it.food_id] = grams.get(it.food_id, 0) + round(it.quantity * float(servings))
        elif it.component_dish_id:
            for food, g in (await dish_quantities(
                session, it.component_dish_id, float(it.servings) * float(servings), depth + 1
            )).items():
                grams[food] = grams.get(food, 0) + g
    return grams


async def is_tracked(session, user: str, food_id: str) -> bool:
    """A food with at least one inbound move. Untracked staples — the family's
    atta, present but unmeasured — must not be spent: a lone negative would
    flip 'present, unknown' into a tracked negative balance."""
    return (await session.scalar(
        select(PantryMove.id).where(
            PantryMove.user_id == user, PantryMove.food_id == food_id,
            PantryMove.kind.in_(("purchase", "opening")), PantryMove.deleted_at.is_(None),
        ).limit(1)
    )) is not None


#: Rungs certain enough to move a shelf. A trigram hit is a *guess* about
#: identity — good enough to show on a card and to hand the estimator as
#: context, not good enough to silently take food out of the house. A missing
#: subtraction is visible ("pantry still says I have eggs"); a wrong one is
#: silent. spec/in-progress/meal-estimates.md § what may spend.
#:
#: A **new rung must be added here to spend**, which is the safe default: the
#: ladder's planned embedding rung is a guess too, and forgetting to list it
#: costs a subtraction rather than a wrong one.
CERTAIN_RUNGS = ("exact", "alias", "id")


def may_spend(line: MealItem) -> bool:
    """`rung` is NULL when nobody guessed: a client POSTed `food_id` directly,
    which is the caller naming the food, not the ladder matching a word."""
    return line.rung is None or line.rung in CERTAIN_RUNGS


async def spend(session, user: str, meal: MealLog) -> list[PantryMove]:
    """
    What this meal took out of the house. Walks the meal's lines: a dish line
    spends its ingredients × servings, a food line spends its grams directly —
    and only when the food was named certainly (`EXACT_ENOUGH`).

    Same transaction as the meal itself, and every move carries the meal's id,
    so deleting the meal gives the food back.
    """
    lines = (await session.scalars(
        select(MealItem).where(MealItem.meal_log_id == meal.id, MealItem.deleted_at.is_(None))
    )).all()
    if not lines:
        return []
    wanted: dict[str, int] = {}
    for line in lines:
        if line.dish_id:
            for food_id, grams in (await dish_quantities(
                session, line.dish_id, line.servings or 1
            )).items():
                wanted[food_id] = wanted.get(food_id, 0) + grams
        elif line.food_id and line.quantity and may_spend(line):
            wanted[line.food_id] = wanted.get(line.food_id, 0) + line.quantity
    moves = []
    for food_id, grams in wanted.items():
        if not await is_tracked(session, user, food_id):
            continue
        move = PantryMove(
            user_id=user, food_id=food_id, local_day=meal.local_day,
            occurred_at=meal.occurred_at, quantity=-grams, kind="consumption",
            meal_log_id=meal.id, note=meal.dish,
        )
        session.add(move)
        moves.append(move)
    return moves


async def unspend(session, meal: MealLog) -> None:
    """Soft-delete the consumption a meal wrote, so sync sees the reversal."""
    rows = (await session.scalars(select(PantryMove).where(
        PantryMove.meal_log_id == meal.id, PantryMove.deleted_at.is_(None)
    ))).all()
    for m in rows:
        m.deleted_at = now()


# ─── transactions ────────────────────────────────────────────────────────────

async def outstanding(session, lending: Transaction) -> int:
    """What is still out on a lending: its amount minus the live repayments on it."""
    repaid = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount_paise), 0)).where(
            Transaction.settles_id == lending.id, Transaction.kind == "repayment",
            Transaction.deleted_at.is_(None),
        )
    )
    return lending.amount_paise - int(repaid or 0)


async def person(session, user: str, row: Transaction) -> None:
    """`counterparty_name` on a write becomes the user's counterparty row, created
    if new — so a lending or borrowing typed on the report names a person the
    ledger can recognise next time. Someone who lent you money is a peer."""
    if row.counterparty_id or not row.counterparty_name:
        return
    # Case-insensitive: the ledger holds "MOHAN LAL" as UPI rendered it, and
    # a person — or an agent — typing "Mohan Lal" means the same shop. An
    # exact match made a second row on 2026-09-12. The stored `raw_name` is
    # still whatever arrived first; only the lookup forgives case.
    who = await session.scalar(select(Counterparty).where(
        Counterparty.user_id == user,
        func.lower(Counterparty.raw_name) == row.counterparty_name.strip().lower()))
    if who is None:
        who = Counterparty(user_id=user, raw_name=row.counterparty_name,
                           is_peer=row.kind == "borrowed")
        session.add(who)
        await session.flush()
    elif row.kind == "borrowed" and not who.is_peer:
        who.is_peer = True
    row.counterparty_id = who.id


async def settle(session, user: str, row: Transaction) -> None:
    """A repayment must point at a live lending and cannot exceed what is out.
    spec/in-progress/udhaar-repayment.md § Rules. It inherits the lending's
    counterparty, and that person becomes a peer: money came back from them."""
    if not row.settles_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a repayment needs settles_id — the lending it pays"
        )
    lending = await session.scalar(select(Transaction).where(
        Transaction.id == row.settles_id, Transaction.user_id == user,
        Transaction.deleted_at.is_(None)))
    if lending is None or lending.kind not in ("lent", "borrowed"):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "settles_id is not a live lending or borrowing"
        )
    # A credit pays back a lending; a debit pays back a borrowing.
    expected = "credit" if lending.kind == "lent" else "debit"
    if row.direction != expected:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"a repayment of a {lending.kind} row must be a {expected}",
        )
    # The new row is already flushed, so `outstanding` has subtracted it once.
    still_out = await outstanding(session, lending) + row.amount_paise
    if row.amount_paise > still_out:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"more than what is out — ₹{still_out / 100:,.0f} is still owed on this lending",
        )
    if row.counterparty_id is None:
        row.counterparty_id = lending.counterparty_id
    if row.counterparty_id:
        who = await session.get(Counterparty, row.counterparty_id)
        if who is not None and not who.is_peer:
            who.is_peer = True


async def set_commitment_link(session, user: str, row: Transaction,
                              commitment_id: str | None) -> None:
    """A statement, not a guess: the payment pays this commitment, or none.
    Only an expense can pay one, and only the user's own live row."""
    if commitment_id is None:
        row.commitment_id = None
        row.commitment_inferred = False
        return
    if row.kind != "expense":
        raise HTTPException(status.HTTP_409_CONFLICT, "only an expense can pay a commitment")
    c = await existing(session, Commitment, commitment_id, user)
    if c is None or c.deleted_at is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"no commitment with id {commitment_id!r} — read the ids from the commitments "
            f"list, never from memory")
    row.commitment_id = c.id
    row.commitment_inferred = False


@router.post("/transactions", response_model=TransactionOut)
async def create_transaction(body: TransactionIn, session: SessionDep, user: CurrentUser,
                             response: Response):
    # A lending or borrowing is about a person. The agent's separate
    # log_lending tool existed only to force this; the server owning the rule
    # means it holds for every caller, the UI included.
    if body.kind in ("lent", "borrowed") and not (body.counterparty_name or body.counterparty_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"a {body.kind} row needs a counterparty — who?")
    # `settles_id` is checked BEFORE the row is written, not after.
    #
    # `settle()` validates it properly, but it runs once the row is already in
    # the session — and `person()` autoflushes before that, so a `settles_id`
    # pointing at no row hit the foreign key first and came back a 500. The
    # agent, handed an id it had remembered from a deleted lending, produced
    # "Didn't reach the server" instead of a sentence explaining itself.
    if body.settles_id:
        target = await session.scalar(select(Transaction).where(
            Transaction.id == body.settles_id, Transaction.user_id == user,
            Transaction.deleted_at.is_(None)))
        if target is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"no live row with id {body.settles_id!r} — get settles_id from a report "
                f"or from people, never from memory",
            )
        if target.kind not in ("lent", "borrowed"):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"settles_id points at a {target.kind} row, not a lending or borrowing",
            )
    link_id = body.commitment_id
    row, created = await replay_or_create(session, Transaction, body, user, response,
                                          exclude={"commitment_id"})
    if created:
        await person(session, user, row)
        if link_id is not None:
            await set_commitment_link(session, user, row, link_id)
        elif row.kind == "expense":
            # A guess from the category, marked as one until the user moves
            # or confirms it. spec/done/commitments.md § Settling.
            await K.auto_link(session, user, row)
        if row.kind == "repayment":
            await session.flush()
            await settle(session, user, row)
    await session.commit()
    return row


@router.patch("/transactions/{row_id}", response_model=TransactionOut)
async def patch_transaction(row_id: str, body: TransactionPatch, session: SessionDep,
                            user: CurrentUser):
    row = await live_or_404(session, Transaction, row_id, user)
    changes = body.model_dump(exclude_unset=True)
    link_sent = "commitment_id" in changes
    link_id = changes.pop("commitment_id", None)
    for key, value in changes.items():
        setattr(row, key, value)
    if link_sent:
        await set_commitment_link(session, user, row, link_id)
    elif row.kind != "expense" and row.commitment_id:
        # No longer spending: no longer pays anything.
        await set_commitment_link(session, user, row, None)
    # The correction trail lives on the prediction, not in a second ledger row.
    # A typo the user made themselves has no prediction and trains nothing.
    pred = await session.scalar(select(Prediction).where(
        Prediction.transaction_id == row.id, Prediction.user_id == user))
    if pred is not None:
        pred.actual_category = row.category
        pred.actual_description = row.description
        pred.corrected_at = now()
    await session.commit()
    return row


@router.delete("/transactions/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(row_id: str, session: SessionDep, user: CurrentUser):
    row = await live_or_404(session, Transaction, row_id, user)
    if row.kind in ("lent", "borrowed"):
        # Deleting the lending would orphan the credits that paid it. Refuse —
        # one more tap for the user, never a surprise (undo the repayments first).
        n = await session.scalar(select(func.count()).select_from(Transaction).where(
            Transaction.settles_id == row.id, Transaction.deleted_at.is_(None)))
        if n:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"this {row.kind} row has {n} repayment{'s' if n > 1 else ''} — undo them first",
            )
    row.deleted_at = now()
    await session.commit()


async def deleted_or_404(session, model, row_id: str, user: str):
    """The row this user deleted — the only kind there is to restore."""
    row = await existing(session, model, row_id, user)
    if row is None or row.deleted_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"{model.__tablename__}: no deleted row to restore")
    return row


@router.post("/transactions/{row_id}/restore", response_model=TransactionOut)
async def restore_transaction(row_id: str, session: SessionDep, user: CurrentUser):
    """Undo a delete. Deletes are soft, so the row comes back exactly as it was
    — the Undo on a card that says *Removed*. A repayment whose lending is
    itself deleted stays deleted: it would settle nothing."""
    row = await deleted_or_404(session, Transaction, row_id, user)
    if row.settles_id:
        lending = await existing(session, Transaction, row.settles_id, user)
        if lending is None or lending.deleted_at is not None:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "the lending this repaid is deleted — restore that first")
    row.deleted_at = None
    await session.commit()
    return row


# ─── meals ───────────────────────────────────────────────────────────────────

class MealWritten(BaseModel):
    """The meal plus the pantry moves it caused, so the card can show stock
    dropping without a refetch."""

    meal: MealOut
    pantry_moves: list[PantryMoveOut]
    #: What each line resolved to, so a card can show it without a refetch.
    items: list[dict] = []


@router.post("/meals", response_model=MealWritten)
async def create_meal(body: MealIn, session: SessionDep, user: CurrentUser, response: Response):
    lines = body.items
    row, created = await replay_or_create(session, MealLog, body, user, response,
                                          exclude={"items"})
    if created and lines:
        # The meal must exist before its lines: there is no ORM relationship
        # between them, so the unit of work does not know to order the inserts.
        await session.flush()
        # Before `spend`, not after: it walks these to work out what left the
        # house, and an empty walk silently takes nothing.
        for line in lines:
            session.add(MealItem(meal_log_id=row.id, dish_id=line.dish_id,
                                 food_id=line.food_id, servings=line.servings,
                                 quantity=line.quantity, said=line.said,
                                 rung=line.rung))
        await session.flush()
    moves = await spend(session, user, row) if created else []
    await session.commit()
    return MealWritten(
        meal=MealOut.model_validate(row),
        pantry_moves=[PantryMoveOut.model_validate(m) for m in moves],
        items=[line.model_dump(mode="json") for line in lines],
    )


@router.patch("/meals/{row_id}", response_model=MealWritten)
async def patch_meal(row_id: str, body: MealPatch, session: SessionDep, user: CurrentUser):
    row = await live_or_404(session, MealLog, row_id, user)
    changes = apply(row, body)
    # A changed macro is the user overruling the estimate, and that pair is
    # the calibration the next estimate reads back. Stamped here the same way
    # `patch_transaction` stamps a prediction's `corrected_at`; changing the
    # day or the note is not a correction and leaves it alone.
    if {"kcal", "protein_g", "carbs_g", "fat_g", "fibre_g"} & set(changes):
        row.corrected_at = now()
    moves: list[PantryMove] = []
    # A different recipe spends different food: reverse the old moves, write
    # the new ones, all in this one transaction.
    if "recipe_id" in changes:
        await unspend(session, row)
        moves = await spend(session, user, row)
    await session.commit()
    return MealWritten(meal=MealOut.model_validate(row),
                       pantry_moves=[PantryMoveOut.model_validate(m) for m in moves])


@router.delete("/meals/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(row_id: str, session: SessionDep, user: CurrentUser):
    row = await live_or_404(session, MealLog, row_id, user)
    row.deleted_at = now()
    await unspend(session, row)  # the food goes back on the shelf
    await session.commit()


@router.post("/meals/{row_id}/restore", response_model=MealWritten)
async def restore_meal(row_id: str, session: SessionDep, user: CurrentUser):
    """Undo a delete: the meal is back, and what it took off the shelf leaves it
    again — written fresh, as eating it the first time did."""
    row = await deleted_or_404(session, MealLog, row_id, user)
    row.deleted_at = None
    moves = await spend(session, user, row)
    await session.commit()
    return MealWritten(meal=MealOut.model_validate(row),
                       pantry_moves=[PantryMoveOut.model_validate(m) for m in moves])


# ─── habit logs ──────────────────────────────────────────────────────────────

@router.post("/habit-logs", response_model=HabitLogOut)
async def create_habit_log(body: HabitLogIn, session: SessionDep, user: CurrentUser,
                           response: Response):
    row, _ = await replay_or_create(session, HabitLog, body, user, response)
    await session.commit()
    return row


@router.patch("/habit-logs/{row_id}", response_model=HabitLogOut)
async def patch_habit_log(row_id: str, body: HabitLogPatch, session: SessionDep,
                          user: CurrentUser):
    row = await live_or_404(session, HabitLog, row_id, user)
    apply(row, body)
    await session.commit()
    return row


@router.delete("/habit-logs/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_habit_log(row_id: str, session: SessionDep, user: CurrentUser):
    row = await live_or_404(session, HabitLog, row_id, user)
    row.deleted_at = now()
    await session.commit()


# ─── tasks ───────────────────────────────────────────────────────────────────

async def _project_of(session, user: str, project_id: str | None) -> str:
    """The project a task goes in: the one named, which must be theirs, or the
    default. Every task has one (spec/done/projects.md)."""
    from app import projects as P
    from app.models.work import Project

    if project_id is None:
        return (await P.default_project(session, user)).id
    found = await session.scalar(select(Project.id).where(
        Project.id == project_id, Project.user_id == user, Project.deleted_at.is_(None)))
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projects: no such row")
    return found


@router.post("/tasks", response_model=TaskOut)
async def create_task(body: TaskIn, session: SessionDep, user: CurrentUser, response: Response):
    if await existing(session, Task, body.id, user) is None:
        body = body.model_copy(update={"project_id": await _project_of(
            session, user, body.project_id)})
    row, created = await replay_or_create(session, Task, body, user, response)
    if created:
        row.status_at = now()
        if row.status == "done":
            row.done_at = row.status_at
    await session.commit()
    return row


@router.patch("/tasks/{row_id}", response_model=TaskOut)
async def patch_task(row_id: str, body: TaskPatch, session: SessionDep, user: CurrentUser):
    """A task is state, not an event — the one table edited in place by design."""
    row = await live_or_404(session, Task, row_id, user)
    was_done = row.status == "done"
    if "project_id" in body.model_fields_set:
        # Moving it — or naming the project it is already in — is the person
        # saying where it belongs, so a guess stops being one.
        body = body.model_copy(update={"project_id": await _project_of(
            session, user, body.project_id)})
        row.project_guessed = False
    changes = apply(row, body)
    if "archived" in changes:
        row.archived_at = now() if changes["archived"] else None
        del row.__dict__["archived"]  # not a column; the flag was consumed above
    if row.status == "done" and not was_done:
        row.done_at = now()
    elif row.status != "done" and was_done:
        row.done_at = None  # un-ticking must not leave a stale completion time
    if "status" in changes:
        # When the person last said done or not done — what tells a tick from
        # a move in the tracker (spec/work-sync.md). `updated_at` cannot: a
        # pull refreshes titles on every run.
        row.status_at = now()
        row.done_by = "phone" if row.status == "done" else None
    await session.commit()
    return row


@router.delete("/tasks/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(row_id: str, session: SessionDep, user: CurrentUser):
    row = await live_or_404(session, Task, row_id, user)
    row.deleted_at = now()
    await session.commit()


# ─── pantry moves ────────────────────────────────────────────────────────────

@router.post("/pantry-moves", response_model=PantryMoveOut)
async def create_pantry_move(body: PantryMoveIn, session: SessionDep, user: CurrentUser,
                             response: Response):
    row, created = await replay_or_create(session, PantryMove, body, user, response)
    if created and row.kind in ("purchase", "opening"):
        # Counting a thing is what makes it not a staple. Buying atta once
        # means atta is now something with a number, and the flag follows.
        item = await session.scalar(select(PantryItem).where(
            PantryItem.user_id == user, PantryItem.food_id == row.food_id,
            PantryItem.deleted_at.is_(None)))
        if item is not None and item.staple:
            item.staple = False
    await session.commit()
    return row


@router.delete("/pantry-moves/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pantry_move(row_id: str, session: SessionDep, user: CurrentUser):
    """Undo a move the user wrote. Consumption belongs to its meal — delete the
    meal and this goes with it, so removing it here would strand the meal."""
    row = await live_or_404(session, PantryMove, row_id, user)
    if row.kind == "consumption":
        raise HTTPException(status.HTTP_409_CONFLICT, "consumption is undone by deleting its meal")
    row.deleted_at = now()
    await session.commit()


@router.patch("/pantry-moves/{row_id}", response_model=PantryMoveOut)
async def patch_pantry_move(row_id: str, body: PantryMovePatch, session: SessionDep,
                            user: CurrentUser):
    row = await live_or_404(session, PantryMove, row_id, user)
    if row.kind == "consumption":
        # Consumption belongs to the meal that caused it; fix the meal instead.
        raise HTTPException(status.HTTP_409_CONFLICT, "consumption is edited through its meal")
    apply(row, body)
    await session.commit()
    return row


# ─── days ────────────────────────────────────────────────────────────────────

@router.put("/days/{local_day}", response_model=DayOut)
async def put_day(local_day: date, body: DayIn, session: SessionDep, user: CurrentUser):
    """Sleep, weight, log-complete for one day. An upsert keyed on the day,
    because one person has exactly one of each per day and a second POST would
    be a duplicate, not a correction. Fields left out are left alone."""
    row = await session.scalar(select(Day).where(
        Day.user_id == user, Day.local_day == local_day, Day.deleted_at.is_(None)))
    if row is None:
        row = Day(user_id=user, local_day=local_day)
        session.add(row)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row

