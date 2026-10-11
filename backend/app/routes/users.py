"""
The person: profile, weigh-ins, memory. spec/in-progress/users-profile.md.

Same conventions as every other write — client ULIDs, `user_id` from the seam
and never the body, soft deletes. Two of the POSTs dedupe on something other
than the id: a weigh-in on the same day replaces the day's reading, and a
memory with the same slug updates the fact rather than filing a second one.
"""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select, update

from app.auth import CurrentUser
from app.db import SessionDep
from app.models.diet import Day
from app.models.users import Memory, User, WeighIn
from app.routes.writes import apply, existing, live_or_404
from app.schemas.users import (
    MemoryIn,
    MemoryOut,
    MemoryPatch,
    UserOut,
    UserPatch,
    WeighInIn,
    WeighInOut,
)

router = APIRouter(tags=["users"])


@router.get("/users/me")
async def me(session: SessionDep, user: CurrentUser) -> UserOut:
    return UserOut.model_validate(await session.get(User, user))


@router.patch("/users/me")
async def patch_me(body: UserPatch, session: SessionDep, user: CurrentUser) -> UserOut:
    row = await session.get(User, user)
    if row.onboarding_done_at is not None and body.onboarding_done_at is None:
        # Past the first run stays past it: a null here would show the first
        # run again to someone who finished or skipped it
        # (spec/done/onboarding-goals.md § Which flag).
        body.model_fields_set.discard("onboarding_done_at")
    apply(row, body)
    await session.commit()
    await session.refresh(row)
    return UserOut.model_validate(row)


@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(session: SessionDep, user: CurrentUser) -> None:
    """Leave, and take everything with you.

    A hard delete, not the soft one every other row gets: a soft-deleted user
    is still a row of somebody's spending and health on somebody else's
    server, which is the opposite of what this asks for. The moment strangers
    can sign up this stops being optional — it is the account-scale version of
    the per-item delete the product already believes in.
    """
    from sqlalchemy import delete as sql_delete
    from sqlalchemy import text

    from app.models.base import Base

    # Children before parents: every table that names a user, then the user.
    for table in reversed(Base.metadata.sorted_tables):
        cols = {c.name for c in table.columns}
        if "user_id" in cols:
            await session.execute(sql_delete(table).where(table.c.user_id == user))
        elif "created_by_id" in cols:
            # Shared library rows outlive their author — a dish someone else
            # saved must not vanish. The authorship is what goes.
            await session.execute(
                table.update().where(table.c.created_by_id == user).values(created_by_id=None)
            )
    await session.execute(text("DELETE FROM users WHERE id = :u"), {"u": user})
    await session.commit()


# ─── weigh-ins ───────────────────────────────────────────────────────────────

@router.get("/weigh-ins")
async def weigh_ins(
    session: SessionDep,
    user: CurrentUser,
    since: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
) -> list[WeighInOut]:
    clauses = [WeighIn.user_id == user, WeighIn.deleted_at.is_(None)]
    if since:
        clauses.append(WeighIn.local_day >= since)
    if to:
        clauses.append(WeighIn.local_day <= to)
    rows = (await session.scalars(
        select(WeighIn).where(*clauses).order_by(WeighIn.local_day.desc())
    )).all()
    return [WeighInOut.model_validate(r) for r in rows]


@router.post("/weigh-ins", status_code=status.HTTP_201_CREATED)
async def create_weigh_in(
    body: WeighInIn, session: SessionDep, user: CurrentUser, response: Response
) -> WeighInOut:
    found = await existing(session, WeighIn, body.id, user)
    if found is not None:  # replay
        response.status_code = status.HTTP_200_OK
        return WeighInOut.model_validate(found)
    same_day = await session.scalar(
        select(WeighIn).where(
            WeighIn.user_id == user, WeighIn.local_day == body.local_day,
            WeighIn.deleted_at.is_(None),
        )
    )
    if same_day is not None:
        # A second reading that day is a correction of the first, not a second
        # row — and an exact one clears the first's estimate.
        same_day.weight_kg = body.weight_kg
        same_day.estimated = body.estimated
        same_day.note = body.note
        row = same_day
        response.status_code = status.HTTP_200_OK
    else:
        row = WeighIn(user_id=user, **body.model_dump())
        session.add(row)
    await session.commit()
    await session.refresh(row)
    return WeighInOut.model_validate(row)


@router.delete("/weigh-ins/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_weigh_in(row_id: str, session: SessionDep, user: CurrentUser) -> None:
    row = await live_or_404(session, WeighIn, row_id, user)
    row.deleted_at = datetime.now(UTC)
    # The agent's log_day keeps a copy of the day's reading on `days`. It goes
    # with the reading: an Undo on the weight's card, or a delete on Profile,
    # leaves no weight behind for that day (spec/done/onboarding-goals.md § Data).
    await session.execute(update(Day).where(
        Day.user_id == user, Day.local_day == row.local_day, Day.weight_kg.is_not(None),
    ).values(weight_kg=None))
    await session.commit()


# ─── memories ────────────────────────────────────────────────────────────────

@router.get("/memories")
async def memories(
    session: SessionDep, user: CurrentUser, kind: str | None = None
) -> list[MemoryOut]:
    clauses = [Memory.user_id == user, Memory.deleted_at.is_(None)]
    if kind:
        clauses.append(Memory.kind == kind)
    rows = (await session.scalars(
        select(Memory).where(*clauses)
        .order_by(Memory.confirmed_at.desc().nulls_last(), Memory.updated_at.desc())
    )).all()
    return [MemoryOut.model_validate(r) for r in rows]


@router.post("/memories", status_code=status.HTTP_201_CREATED)
async def create_memory(
    body: MemoryIn, session: SessionDep, user: CurrentUser, response: Response
) -> MemoryOut:
    found = await existing(session, Memory, body.id, user)
    if found is not None:  # replay
        response.status_code = status.HTTP_200_OK
        return MemoryOut.model_validate(found)
    same_slug = await session.scalar(
        select(Memory).where(
            Memory.user_id == user, Memory.slug == body.slug, Memory.deleted_at.is_(None)
        )
    )
    if same_slug is not None:
        # One slug, one row: a rewrite updates the fact. Whoever wrote it last
        # is the source, and a user's own words count as confirmation.
        same_slug.text = body.text
        same_slug.kind = body.kind
        same_slug.source = body.source
        if body.source == "user":
            same_slug.confirmed_at = datetime.now(UTC)
        row = same_slug
        response.status_code = status.HTTP_200_OK
    else:
        row = Memory(user_id=user, **body.model_dump())
        if body.source == "user":
            row.confirmed_at = datetime.now(UTC)
        session.add(row)
    await session.commit()
    await session.refresh(row)
    return MemoryOut.model_validate(row)


@router.patch("/memories/{row_id}")
async def patch_memory(
    row_id: str, body: MemoryPatch, session: SessionDep, user: CurrentUser
) -> MemoryOut:
    row = await live_or_404(session, Memory, row_id, user)
    apply(row, body)
    await session.commit()
    await session.refresh(row)
    return MemoryOut.model_validate(row)


@router.delete("/memories/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(row_id: str, session: SessionDep, user: CurrentUser) -> None:
    row = await live_or_404(session, Memory, row_id, user)
    row.deleted_at = datetime.now(UTC)
    await session.commit()
