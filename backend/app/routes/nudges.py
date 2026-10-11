"""
The bell's page. spec/in-progress/nudges.md.

Two routes: the list, and the three switches a nudge has. Nudges are written
by scheduled jobs (`app/agent/jobs.py`), never through HTTP — a nudge the
phone could create would be a nudge with no run behind it, and every nudge
names the run that made it.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.agent.jobs import IST
from app.auth import CurrentUser
from app.db import SessionDep
from app.models.nudges import Nudge
from app.routes.writes import live_or_404, now
from app.schemas.nudges import NudgeOut, NudgePatch

router = APIRouter(tags=["nudges"])

#: Which column each switch stamps.
SWITCHES = {"seen": "seen_at", "done": "done_at", "dismissed": "dismissed_at"}


@router.get("/nudges", response_model=list[NudgeOut])
async def nudges(session: SessionDep, user: CurrentUser,
                 days: int = Query(7, ge=1, le=31)):
    """The last `days` local days, today included — *Today*, then *Earlier*.
    A nudge expires with its day, and after the window it is off the page.
    Dismissed ones come back too: the phone hides them for their day, and
    knowing one was dismissed is how it does."""
    first = datetime.now(IST).date() - timedelta(days=days - 1)
    rows = (await session.scalars(
        select(Nudge).where(Nudge.user_id == user, Nudge.deleted_at.is_(None),
                            Nudge.local_day >= first)
        .order_by(Nudge.created_at.desc(), Nudge.id.desc())
    )).all()
    return rows


@router.patch("/nudges/{row_id}", response_model=NudgeOut)
async def patch_nudge(row_id: str, body: NudgePatch, session: SessionDep, user: CurrentUser):
    """True stamps now; false clears. A switch left out, or sent as null, is
    left alone. Stamping again moves the time — opened twice is opened, and
    the latest is what the card shows."""
    row = await live_or_404(session, Nudge, row_id, user)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, SWITCHES[key], now() if value else None)
    await session.commit()
    await session.refresh(row)
    return row
