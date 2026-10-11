"""
Today's plan. spec/in-progress/today-plan.md.

One read for Home's Meals and Workout widgets: the rest of today's meals,
sized to what is left of the targets, and one workout. It writes nothing of its
own — logging from the plan goes through `POST /chat/act` like any card's tap —
except a picture found for a dish or exercise that had none.
"""

from datetime import date

from fastapi import APIRouter

from app.agent import plan
from app.auth import CurrentUser
from app.db import SessionDep

router = APIRouter(tags=["plan"])


@router.get("/plan/today")
async def today_plan(session: SessionDep, user: CurrentUser, local_day: date,
                     local_time: str | None = None) -> dict:
    """`local_time` is the phone's clock, `HH:MM` — it decides which meals are
    still ahead. Without it, the user's own timezone does."""
    return await plan.today(session, user, local_day, local_time)
