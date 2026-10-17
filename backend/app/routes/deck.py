"""
GET /deck — every row the three cards need, in one call.

Rows, never totals. The client already computes the arcs, bars and strips
(metrics.ts, tasks.ts, workouts.ts); a server that also computed them would put
the same arithmetic in two places today and three once Android exists.

One call rather than three, because swiping between cards must never show a
loading state.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.auth import CurrentUser
from app.db import SessionDep
from app.models.diet import Day, Habit, HabitLog, MealItem, MealLog
from app.models.paisa import BalanceCheck, Transaction
from app.models.users import User
from app.models.work import Project, SourceDocument, Task
from app.schemas.deck import (
    DeckOut,
    DietOut,
    MealRowOut,
    OnboardingOut,
    PaisaOut,
    TransactionRowOut,
    WorkOut,
)
from app.schemas.users import UserOut

router = APIRouter(tags=["deck"])


def month_start(anchor: date) -> date:
    """The paisa arc is monthly whatever range is selected."""
    return anchor.replace(day=1)


def week_start(anchor: date) -> date:
    """The diet chain strip is weekly whatever range is selected. Monday."""
    return date.fromordinal(anchor.toordinal() - anchor.weekday())


@router.get("/deck", response_model_by_alias=True)
async def deck(
    session: SessionDep,
    user: CurrentUser,
    to: Annotated[date, Query(description="Last day of the window, in the user's local dates")],
    since: Annotated[
        date | None,
        Query(alias="from",
              description="First day of the window. Omit for everything up to `to`."),
    ] = None,
) -> DeckOut:
    """
    `from` and `to` are the user's LOCAL dates, sent by the client — only the
    client knows what day it is where the user is. A server deciding "today"
    would put an 11:30pm chai on the wrong day, which is the bug `local_day`
    exists to prevent.
    """
    # Each mode gets the asked-for window UNIONED with what its card
    # structurally needs, so a one-day range never blanks the month arc or the
    # week strip. Those two windows are not selected, they are built in.
    paisa_from = min(since, month_start(to)) if since else None
    diet_from = min(since, week_start(to)) if since else None

    def window(col, lo):
        clauses = [col <= to]
        if lo is not None:
            clauses.append(col >= lo)
        return clauses

    txns = (await session.scalars(
        select(Transaction)
        .where(Transaction.user_id == user, Transaction.deleted_at.is_(None),
               *window(Transaction.local_day, paisa_from))
        .order_by(Transaction.local_day, Transaction.id)
    )).all()

    balance = await session.scalar(
        select(BalanceCheck)
        .where(BalanceCheck.user_id == user, BalanceCheck.as_of <= to)
        .order_by(BalanceCheck.as_of.desc())
        .limit(1)
    )

    meals = (await session.scalars(
        select(MealLog)
        .where(MealLog.user_id == user, MealLog.deleted_at.is_(None),
               *window(MealLog.local_day, diet_from))
        .order_by(MealLog.local_day, MealLog.id)
    )).all()

    # The dish a meal came from, so Home can show its picture: the first dish
    # among its lines. One query for the lot; a meal of foods only has none.
    if meals:
        firsts: dict[str, str] = {}
        for meal_id, dish_id in (await session.execute(
            select(MealItem.meal_log_id, MealItem.dish_id)
            .where(MealItem.meal_log_id.in_([m.id for m in meals]),
                   MealItem.dish_id.is_not(None), MealItem.deleted_at.is_(None))
            .order_by(MealItem.created_at, MealItem.id)
        )).all():
            firsts.setdefault(meal_id, dish_id)
        for m in meals:
            m.dish_id = firsts.get(m.id)

    habit_logs = (await session.scalars(
        select(HabitLog)
        .where(HabitLog.user_id == user, HabitLog.deleted_at.is_(None),
               *window(HabitLog.local_day, diet_from))
        .order_by(HabitLog.local_day)
    )).all()

    days = (await session.scalars(
        select(Day)
        .where(Day.user_id == user, Day.deleted_at.is_(None),
               *window(Day.local_day, diet_from))
        .order_by(Day.local_day)
    )).all()

    # All of them: the strip needs to know a habit exists even on a day with no
    # log, because a blank mark and an unknown habit are different things.
    habits = (await session.scalars(
        select(Habit).where(Habit.user_id == user, Habit.deleted_at.is_(None))
    )).all()

    projects = (await session.scalars(
        select(Project)
        .where(Project.user_id == user, Project.deleted_at.is_(None),
               Project.archived_at.is_(None))
        .order_by(Project.name)
    )).all()

    # Everything still live, plus what was finished inside the window — ticked
    # tasks stay on the card for the rest of the day, then drop.
    tasks = (await session.scalars(
        select(Task)
        .where(Task.user_id == user, Task.deleted_at.is_(None),
               Task.archived_at.is_(None),
               (Task.status != "done") | (Task.done_at.is_not(None)))
        .order_by(Task.due.nulls_last(), Task.priority.nulls_last())
    )).all()

    # A meeting's title, for the tasks it produced — one query for the lot.
    refs = {(t.source, t.source_ref) for t in tasks if t.source_ref and not t.source_key}
    if refs:
        titles = {(d.source, d.ref): d.title for d in (await session.scalars(
            select(SourceDocument).where(
                SourceDocument.user_id == user, SourceDocument.deleted_at.is_(None),
                SourceDocument.ref.in_([r for _, r in refs])))).all()}
        for t in tasks:
            t.source_title = titles.get((t.source, t.source_ref))

    profile = await session.get(User, user)

    return DeckOut(
        from_=since,
        to=to,
        # The whole row: the rings' denominators and the limit's goal come from
        # here, not from a constant in the client.
        profile=UserOut.model_validate(profile),
        # Finished or skipped the first run — the flag the apps decide on.
        # Getting started's derived steps went with the card
        # (spec/done/onboarding-goals.md § Which flag).
        onboarding=OnboardingOut(done_at=profile.onboarding_done_at),
        paisa=PaisaOut.model_validate({"transactions": txns, "balance_check": balance}),
        diet=DietOut.model_validate(
            {"meals": meals, "habits": habits, "habit_logs": habit_logs, "days": days}
        ),
        work=WorkOut.model_validate({"projects": projects, "tasks": tasks}),
    )


# ─── rows by id ──────────────────────────────────────────────────────────────
#
# A chat card names rows by id and renders them from live data. The deck is
# one window; a card can name a row from before it (*"last month's Swiggy"*).
# These two reads hand back exactly the rows asked for — deleted ones
# included, with `deleted_at` set, so the card can strike a row through
# instead of losing it. spec/chat-cards.md § ledger card.

IDS_CAP = 50


def _ids(raw: str) -> list[str]:
    ids = [x for x in (part.strip() for part in raw.split(",")) if x]
    if not ids or len(ids) > IDS_CAP:
        raise HTTPException(status_code=422, detail=f"between 1 and {IDS_CAP} ids")
    return ids


IdsQuery = Annotated[str, Query(description="comma-separated row ids, up to 50; "
                                            "deleted rows come back with deleted_at set")]


@router.get("/transactions", response_model=list[TransactionRowOut])
async def transactions_by_id(session: SessionDep, user: CurrentUser, ids: IdsQuery):
    wanted = _ids(ids)
    rows = (await session.scalars(
        select(Transaction).where(Transaction.user_id == user, Transaction.id.in_(wanted))
        .order_by(Transaction.local_day, Transaction.id))).all()
    return [TransactionRowOut.model_validate(r) for r in rows]


@router.get("/meals", response_model=list[MealRowOut])
async def meals_by_id(session: SessionDep, user: CurrentUser, ids: IdsQuery):
    wanted = _ids(ids)
    rows = (await session.scalars(
        select(MealLog).where(MealLog.user_id == user, MealLog.id.in_(wanted))
        .order_by(MealLog.local_day, MealLog.id))).all()
    return [MealRowOut.model_validate(r) for r in rows]
