"""
The schedules the user owns. spec/in-progress/schedules.md.

Four routes, the shape every other library in this app has. The dispatcher
(`app/agent/jobs.py`) never goes through HTTP — it reads the rows directly —
so these exist purely so the user can see and change what runs, which is the
whole reason the times are rows and not a crontab.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.agent.jobs import IST, JOBS, is_due
from app.auth import CurrentUser
from app.db import SessionDep
from app.models.schedules import Schedule
from app.routes.writes import apply, existing, live_or_404, now
from app.schemas.schedules import ScheduleIn, ScheduleOut, SchedulePatch

router = APIRouter(tags=["schedules"])


def _out(row: Schedule, at: datetime) -> ScheduleOut:
    job = JOBS[row.job]
    return ScheduleOut(
        id=row.id, job=row.job, label=job.label, blurb=job.blurb,
        at_local_time=row.at_local_time, repeat=row.repeat, days=row.days,
        params=row.params, enabled=row.enabled, grace_hours=row.grace_hours,
        last_run_local_day=row.last_run_local_day, last_run_at=row.last_run_at,
        last_error=row.last_error, due_now=is_due(row, at),
    )


def _known(job: str) -> None:
    """A schedule pointing at nothing would sit in the UI looking like it
    works, so the vocabulary is closed and checked at the door."""
    if job not in JOBS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"no job called {job!r} — there is {', '.join(sorted(JOBS))}")


@router.get("/schedules", response_model=list[ScheduleOut])
async def schedules(session: SessionDep, user: CurrentUser):
    at = datetime.now(IST)
    rows = (await session.scalars(
        select(Schedule).where(Schedule.user_id == user, Schedule.deleted_at.is_(None))
        .order_by(Schedule.at_local_time)
    )).all()
    # A row whose job no longer exists in the registry is not drawn: the code
    # that would run it is gone, so showing a switch for it would be a lie.
    return [_out(r, at) for r in rows if r.job in JOBS]


@router.post("/schedules", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
async def create_schedule(body: ScheduleIn, session: SessionDep, user: CurrentUser,
                          response: Response):
    _known(body.job)
    if (prior := await existing(session, Schedule, body.id, user)) is not None:
        response.status_code = status.HTTP_200_OK
        return _out(prior, datetime.now(IST))
    taken = await session.scalar(select(Schedule).where(
        Schedule.user_id == user, Schedule.job == body.job, Schedule.deleted_at.is_(None)))
    if taken is not None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{body.job} is already scheduled — change that one")
    row = Schedule(user_id=user, **body.model_dump())
    session.add(row)
    await session.commit()
    return _out(row, datetime.now(IST))


@router.patch("/schedules/{row_id}", response_model=ScheduleOut)
async def patch_schedule(row_id: str, body: SchedulePatch, session: SessionDep,
                         user: CurrentUser):
    row = await live_or_404(session, Schedule, row_id, user)
    apply(row, body)
    if row.repeat == "weekly" and not row.days:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "a weekly schedule needs at least one day")
    # Changing the time does not re-run today: `last_run_local_day` already
    # says it ran. Moving 20:30 to 21:00 takes effect tomorrow, and running it
    # now is what the agent and the script are for.
    await session.commit()
    return _out(row, datetime.now(IST))


@router.delete("/schedules/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(row_id: str, session: SessionDep, user: CurrentUser):
    """Soft, and the name frees for re-use — the partial index. Turning a job
    *off* is `enabled: false`, which keeps its time; this is for removing it."""
    row = await live_or_404(session, Schedule, row_id, user)
    row.deleted_at = now()
    await session.commit()
