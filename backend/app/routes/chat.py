"""
The agent. spec/agent.md.

One thread per user, no streaming, cards not prose. `POST /chat` is a turn;
`GET /chat` is the scrollback the user reads, which is longer than what the
model is given.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.agent.runner import ModelFailed, act, clear, history, reply
from app.auth import CurrentUser
from app.config import settings
from app.db import SessionDep
from app.llm import model
from app.schemas.chat import ActIn, ChatIn, ChatOut, HistoryOut, MessageOut

log = logging.getLogger(__name__)

router = APIRouter(tags=["agent"])


async def turns_today(session, user: str) -> int:
    """How many times this user has spoken since midnight where they are.

    The model key is server-wide, so an open door is an open tab. The boundary
    comes from the user's own `timezone` column rather than UTC: a limit that
    resets at 5:30am local is a limit nobody can reason about.
    """
    from datetime import UTC, datetime, time
    from zoneinfo import ZoneInfo

    from sqlalchemy import func, select

    from app.models.chat import Message
    from app.models.users import User

    tz = await session.scalar(select(User.timezone).where(User.id == user)) or "Asia/Kolkata"
    local_midnight = datetime.combine(
        datetime.now(ZoneInfo(tz)).date(), time.min, tzinfo=ZoneInfo(tz)
    )
    return await session.scalar(
        select(func.count()).select_from(Message).where(
            Message.user_id == user,
            Message.role == "user",
            Message.created_at >= local_midnight.astimezone(UTC),
        )
    ) or 0


@router.post("/chat")
async def chat(body: ChatIn, session: SessionDep, user: CurrentUser) -> ChatOut:
    if await turns_today(session, user) >= settings().daily_turn_limit:
        # Not an error status: the agent stops talking, and every other route
        # keeps working. The ledger never goes down over a budget.
        return ChatOut(
            reply="That is me done for today — I will be back tomorrow. "
                  "You can still log, read and correct anything in the meantime.",
            cards=[], tokens_in=0, tokens_out=0, model="limit",
        )
    try:
        turn = await reply(session, user, body.message, body.local_day, body.local_time)
    except ModelFailed as e:
        # The model's fault — a key, a credit balance, the provider down — not
        # the person's and not a bug here. Said plainly, and logged with its
        # cause, as the first run's turn does; a bare 500 hid both.
        log.warning("chat turn: the model call failed: %s", e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            "the model could not be reached just now — nothing was written") from e
    return ChatOut(reply=turn.text, cards=turn.cards, tokens_in=turn.tokens_in,
                   tokens_out=turn.tokens_out, model=model())


@router.post("/chat/act")
async def chat_act(body: ActIn, session: SessionDep, user: CurrentUser) -> ChatOut:
    """A tap on a card: the tool runs, no model, and the cards come back for
    the client to show as a receipt. `record: true` also appends the turn.
    A tool that refuses comes back as the route's own status, not as prose."""
    turn = await act(session, user, body.name, body.args, record=body.record)
    return ChatOut(reply=turn.text, cards=turn.cards, tokens_in=0, tokens_out=0, model="tap")


@router.get("/chat")
async def chat_history(
    session: SessionDep, user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    before: Annotated[int | None, Query(
        description="a message seq; returns the page before it")] = None,
    include_cleared: Annotated[bool, Query(
        description="also return what the user cleared from view")] = False,
) -> HistoryOut:
    """One page of what the user has said and been told, oldest last.

    A `seq` cursor rather than an offset, so a soft delete or a new arrival
    cannot shift the page under someone mid-scroll.
    """
    from sqlalchemy import select

    from app.models.chat import Conversation
    rows, more = await history(session, user, limit, before, include_cleared)
    convo = await session.scalar(select(Conversation).where(
        Conversation.user_id == user, Conversation.deleted_at.is_(None)))
    return HistoryOut(messages=[MessageOut.model_validate(m) for m in rows],
                      summary=convo.summary if convo else None, has_more=more,
                      cleared_through_seq=convo.cleared_through_seq if convo else 0)


@router.post("/chat/clear")
async def chat_clear(
    session: SessionDep, user: CurrentUser,
    keep: Annotated[int, Query(ge=0, le=20,
                               description="messages left on screen")] = 1,
) -> HistoryOut:
    """Clear the screen without forgetting. Everything above the last `keep`
    messages is folded into the summary and hidden; nothing is deleted, and
    *Show older* brings it back."""
    convo = await clear(session, user, keep)
    rows, more = await history(session, user, 50)
    return HistoryOut(messages=[MessageOut.model_validate(m) for m in rows],
                      summary=convo.summary, has_more=more,
                      cleared_through_seq=convo.cleared_through_seq)
