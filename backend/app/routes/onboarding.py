"""
The first run's answers. spec/done/onboarding-goals.md § The onboarding agent.

`POST /onboarding/turn` is one answer to one of screen 3's questions. The
onboarding agent writes what it hears through the app's own tools, and the
confirm cards come back. Nothing goes into the chat thread — that stays a
conversation the person starts — and nothing is replayed: every tool the
agent writes through is already safe to repeat, so an answer sent twice
writes the same rows once.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.agent import onboarding as O
from app.agent.runner import ModelFailed
from app.auth import CurrentUser
from app.config import settings
from app.db import SessionDep
from app.models.users import User
from app.schemas.onboarding import OnboardingTurnIn, OnboardingTurnOut

log = logging.getLogger(__name__)

router = APIRouter(tags=["onboarding"])


async def count_turn(session, user: str, tz: str) -> bool:
    """Count this answer against today's cap, or refuse it — False past it.

    One UPDATE, so two answers sent at once cannot both slip under the cap.
    Counted before the model is called and kept when the turn fails, because
    the call is billed either way. The day is the person's own, from their
    `timezone`, never the client's word for it: a client choosing its day
    could choose a new one per request. Raw SQL so `updated_at` stays put — a
    count is not a change to who they are.
    """
    today = datetime.now(ZoneInfo(tz)).date()
    # The count this answer would make, held to the cap — so a cap of 0 is a
    # switch that stops every turn, a new day's first one included.
    counted = await session.scalar(text(
        "UPDATE users SET onboarding_turns = CASE WHEN onboarding_turns_day = :d "
        "THEN onboarding_turns + 1 ELSE 1 END, onboarding_turns_day = :d "
        "WHERE id = :u AND CASE WHEN onboarding_turns_day = :d "
        "THEN onboarding_turns + 1 ELSE 1 END <= :cap RETURNING onboarding_turns"),
        {"u": user, "d": today, "cap": settings().onboarding_turn_limit})
    await session.commit()
    return counted is not None


@router.post("/onboarding/turn")
async def onboarding_turn(body: OnboardingTurnIn, session: SessionDep,
                          user: CurrentUser) -> OnboardingTurnOut:
    person = await session.get(User, user)
    if person.onboarding_done_at is not None:
        # Finished or skipped: the questions are over. Profile and the chat
        # are where a fact changes now.
        raise HTTPException(status.HTTP_409_CONFLICT, "the first run is already finished")
    if not await count_turn(session, user, person.timezone):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "that is enough answers for today — nothing was written")
    try:
        answer = await O.turn(user, body.question, body.text, body.local_day)
    except ModelFailed as e:
        # The model's fault, not the person's and not a bug here: the turn's
        # transaction has rolled back, and the screen offers to send it again.
        log.warning("onboarding turn: the model call failed: %s", e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            "the answer could not be read just now — nothing was written") from e
    return OnboardingTurnOut(cards=answer.cards, reply=answer.reply, next=answer.next)
