"""
The exercise library. spec/done/workouts.md.

A library to **suggest** from, not to record into — the same shape as dishes,
minus the ledger. The query parameters on `GET /exercises` are the suggestion
spelled out: *"leg lagana hai"* is `muscle_group`, *"cardio karna hai"* is
`kind`, *"mere paas 20 minute hain"* is `minutes`, *"gym nahi ja paya"* is
`equipment`. What the library does not hold, the agent finds and offers; keeping
it is a POST.

There is no session table. A workout is a habit log, yes or no, and which
exercises were done in the gym is not something this user records — a ledger for
it was built and removed on 2026-09-07.
"""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select

from app.auth import CurrentUser
from app.db import SessionDep
from app.models.diet import Exercise
from app.routes.writes import apply
from app.schemas.workouts import DidIt, ExerciseIn, ExerciseOut, ExercisePatch

router = APIRouter(tags=["workouts"])


async def _live(session, exercise_id: str, user: str) -> Exercise:
    row = await session.scalar(select(Exercise).where(
        Exercise.id == exercise_id, Exercise.user_id == user, Exercise.deleted_at.is_(None)))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such exercise")
    return row


@router.get("/exercises")
async def exercises(
    session: SessionDep,
    user: CurrentUser,
    q: Annotated[str | None, Query(description="name or alias contains")] = None,
    kind: Annotated[str | None, Query()] = None,
    muscle_group: Annotated[str | None, Query()] = None,
    equipment: Annotated[str | None, Query()] = None,
    minutes: Annotated[int | None, Query(ge=1, description="at most this long")] = None,
    tried: Annotated[bool | None, Query(description="true = done before, false = never")] = None,
) -> list[ExerciseOut]:
    """Your library. Every filter is a question someone actually asks."""
    clauses = [Exercise.user_id == user, Exercise.deleted_at.is_(None)]
    if q:
        needle = f"%{q.strip().lower()}%"
        clauses.append(or_(func.lower(Exercise.name).like(needle),
                           Exercise.aliases.any(q.strip().lower())))
    if kind:
        clauses.append(Exercise.kind == kind)
    if muscle_group:
        clauses.append(Exercise.muscle_group == muscle_group)
    if equipment:
        clauses.append(Exercise.equipment == equipment)
    if minutes:
        # Unknown length is not "too long" — an exercise with no typical
        # minutes stays a candidate rather than being silently filtered out.
        clauses.append(or_(Exercise.typical_minutes.is_(None),
                           Exercise.typical_minutes <= minutes))
    if tried is not None:
        clauses.append(Exercise.tried > 0 if tried else Exercise.tried == 0)

    rows = (await session.scalars(
        select(Exercise).where(*clauses)
        .order_by(Exercise.muscle_group.nulls_last(), Exercise.name)
    )).all()
    return [ExerciseOut.model_validate(r) for r in rows]


@router.post("/exercises", status_code=status.HTTP_201_CREATED)
async def create_exercise(
    body: ExerciseIn, session: SessionDep, user: CurrentUser, response: Response
) -> ExerciseOut:
    """Add one — typed, or kept from something the agent found. Nothing is
    inserted on the agent's own say-so; a row exists because it was kept."""
    found = await session.scalar(select(Exercise).where(Exercise.id == body.id))
    if found is not None:  # replay
        response.status_code = status.HTTP_200_OK
        return ExerciseOut.model_validate(found)
    row = Exercise(**body.model_dump(), user_id=user)
    session.add(row)
    await session.commit()
    return ExerciseOut.model_validate(row)


@router.patch("/exercises/{exercise_id}")
async def patch_exercise(
    exercise_id: str, body: ExercisePatch, session: SessionDep, user: CurrentUser
) -> ExerciseOut:
    """Any field, `tried` included — correcting a miscount is deliberate, which
    is why nothing decrements it automatically."""
    row = await _live(session, exercise_id, user)
    apply(row, body)
    await session.commit()
    return ExerciseOut.model_validate(row)


@router.post("/exercises/{exercise_id}/did")
async def did_it(
    exercise_id: str, body: DidIt, session: SessionDep, user: CurrentUser
) -> ExerciseOut:
    """One more time. `tried += 1` and `last_tried`, in a single write — the
    agent calls this when you say *"aaj squats kiye"*.

    Incremented in SQL rather than read-then-written, so two calls in the same
    breath cannot land on the same number.
    """
    row = await _live(session, exercise_id, user)
    row.tried = Exercise.tried + 1
    row.last_tried = body.local_day or date.today()
    await session.commit()
    await session.refresh(row)
    return ExerciseOut.model_validate(row)


@router.delete("/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exercise(exercise_id: str, session: SessionDep, user: CurrentUser) -> None:
    """Soft. Nothing points at an exercise, so this is only about the list."""
    row = await _live(session, exercise_id, user)
    row.deleted_at = datetime.now(UTC)
    await session.commit()
