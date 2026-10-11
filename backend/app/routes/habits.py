"""
The habit library — what you have decided to track.

Until now a habit could only come into being through a migration: `/habit-logs`
wrote the *ticks* and the `habits` table had no endpoint at all. Three habits
existed, and a fourth was impossible. spec/in-progress/habits.md.

The counts are computed per request, like every other count in this app except
`exercises.tried`. A stored streak is a number that drifts the first time a log
is deleted.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.auth import CurrentUser
from app.db import SessionDep
from app.models.diet import Habit, HabitLog
from app.routes.writes import apply, existing, live_or_404, now
from app.schemas.habits import HabitIn, HabitOut, HabitPatch

router = APIRouter(tags=["habits"])


def week_start(anchor: date) -> date:
    """Monday, the same week the deck's chain strip draws."""
    return date.fromordinal(anchor.toordinal() - anchor.weekday())


async def _rows(session, user: str, *, one: str | None = None) -> list[HabitOut]:
    monday = week_start(date.today())
    week = (
        select(func.count(func.distinct(HabitLog.local_day)))
        .where(HabitLog.habit_id == Habit.id, HabitLog.deleted_at.is_(None),
               HabitLog.local_day >= monday)
        .correlate(Habit).scalar_subquery()
    )
    ever = (
        select(func.count())
        .select_from(HabitLog)
        .where(HabitLog.habit_id == Habit.id, HabitLog.deleted_at.is_(None))
        .correlate(Habit).scalar_subquery()
    )
    stmt = (select(Habit, week.label("days_this_week"), ever.label("logged_ever"))
            .where(Habit.user_id == user, Habit.deleted_at.is_(None))
            .order_by(Habit.name))
    if one:
        stmt = stmt.where(Habit.id == one)
    return [
        HabitOut(id=h.id, name=h.name, direction=h.direction, unit=h.unit,
                 days_this_week=w or 0, logged_ever=e or 0)
        for h, w, e in (await session.execute(stmt)).all()
    ]


async def _name_taken(session, user: str, name: str, *, besides: str | None = None) -> bool:
    """`log_day` matches by the name the user said, so two habits sharing one
    would make a tick ambiguous. Checked here rather than left to the index, so
    the answer is a sentence instead of a constraint violation."""
    stmt = select(Habit.id).where(
        Habit.user_id == user, Habit.deleted_at.is_(None),
        func.lower(Habit.name) == name.strip().lower())
    if besides:
        stmt = stmt.where(Habit.id != besides)
    return (await session.scalar(stmt)) is not None


@router.get("/habits")
async def habits(session: SessionDep, user: CurrentUser) -> list[HabitOut]:
    """Everything you track, by name."""
    return await _rows(session, user)


@router.post("/habits", status_code=status.HTTP_201_CREATED)
async def create_habit(
    body: HabitIn, session: SessionDep, user: CurrentUser, response: Response
) -> HabitOut:
    """Start tracking something."""
    row = await existing(session, Habit, body.id, user)
    if row is not None:  # replay
        response.status_code = status.HTTP_200_OK
    else:
        if await _name_taken(session, user, body.name):
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"{body.name!r} is already tracked")
        row = Habit(**body.model_dump(), user_id=user)
        session.add(row)
        await session.commit()
    return (await _rows(session, user, one=row.id))[0]


@router.patch("/habits/{row_id}")
async def patch_habit(
    row_id: str, body: HabitPatch, session: SessionDep, user: CurrentUser
) -> HabitOut:
    """Rename it, flip which way it goes, change what it counts.

    Old logs are not rewritten: an amount logged in minutes stays minutes.
    Converting it would be inventing a number nobody measured.
    """
    row = await live_or_404(session, Habit, row_id, user)
    if body.name and await _name_taken(session, user, body.name, besides=row_id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{body.name!r} is already tracked")
    apply(row, body)
    await session.commit()
    return (await _rows(session, user, one=row_id))[0]


@router.delete("/habits/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_habit(row_id: str, session: SessionDep, user: CurrentUser) -> None:
    """Stop tracking it. Soft, and the logs stay: that you went to the gym in
    August is still true, and the week strip keeps drawing the days it was
    ticked. The name is freed for re-use — the index is partial."""
    row = await live_or_404(session, Habit, row_id, user)
    row.deleted_at = now()
    await session.commit()
