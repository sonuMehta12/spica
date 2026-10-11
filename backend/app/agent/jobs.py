"""
The jobs a schedule can point at, and the dispatcher that runs the due ones.
spec/in-progress/schedules.md.

**One tick, many jobs.** One line in the OS crontab calls `scripts/run_due.py`
once an hour; it asks this module which schedules are due and runs those.
Hourly because Neon's compute sleeps after five idle minutes and every tick
wakes it (spec/in-progress/deploy.md); every grace window is hours wide.
Adding the morning brief later adds a row to `schedules` and an entry to
`JOBS` — never a second crontab line, and never a time written into code.

**What a job produces is written by the agent**, in one of two places. A
*thread* job's output is a turn in the thread: it runs its tools, and one model
call says what it found in the agent's own voice. A *nudges* job writes
**nudges** instead — rows behind the bell, each opening a page where the thing
gets done — and nothing into the thread: an unprompted message in the person's
conversation reads as a message nobody sent. spec/in-progress/nudges.md.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import cards as C
from app.agent.brief import morning_brief
from app.agent.runner import Turn, _thread
from app.llm import respond
from app.models.chat import Message
from app.models.nudges import Nudge
from app.models.schedules import Schedule

log = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class Job:
    """What is true of a job itself — never what the user chose about it.

    The defaults here seed a brand-new row and are read at no other time: once
    the row exists, its time, repeat and grace come from the row. A job reading
    a constant from this file at run time would be a setting nobody can see.
    """

    key: str
    #: What the Profile row says. The user never sees `key`.
    label: str
    #: One line under it, so a job that has never run still explains itself.
    blurb: str
    default_at: time
    default_grace: int
    #: Runs the work, or returns None when there is nothing worth saying — a
    #: nightly "nothing to report" teaches the user to scroll past the night
    #: it matters. A thread job is called `(session, user, params)` and returns
    #: `(cards, a plain sentence)`. A nudges job is also told the hour it ran
    #: at — a nudge belongs to a local day, and what it says must be about
    #: that day — and returns one spec per nudge:
    #: `{kind, title, summary, refs, line?, facts?}`.
    run: Callable[..., Awaitable[Any]]
    #: Where the output goes: `thread`, a turn in the conversation, or
    #: `nudges`, rows behind the bell and nothing in the thread.
    posts: str = "thread"


# ─── the jobs ────────────────────────────────────────────────────────────────

async def _categorise(session: AsyncSession, user: str, params: dict):
    """The second look at unconfirmed payments. spec/in-progress/categorise.md.

    `params` is what the user's row carries; `day` scopes the run to one day,
    absent means everything pending.
    """
    from app.agent.categorise import categorise, to_review

    day = date.fromisoformat(params["day"]) if params.get("day") else None
    report = await categorise(session, user, day)
    report["to_review"] = await to_review(session, user)

    open_now = report["to_review"]
    if not (report["written"] or report["agreed"] or open_now):
        return None
    cards = [c.model_dump() for c in C.from_tool("categorise_now", {}, report)]
    said = []
    if report["written"]:
        said.append(f"{len(report['written'])} categorised")
    if report["agreed"]:
        said.append(f"{len(report['agreed'])} confirmed")
    if open_now:
        said.append(f"{len(open_now)} to check")
    return cards, " · ".join(said)


JOBS: dict[str, Job] = {
    "categorise": Job(
        key="categorise",
        label="Review payments",
        blurb="Looks at the day's payments and asks about the ones it is unsure of",
        default_at=time(20, 30),
        # Long on purpose: a review missed while the laptop was shut is worth
        # having in the morning. A *morning* brief would take a short one.
        default_grace=12,
        run=_categorise,
    ),
    "morning_brief": Job(
        key="morning_brief",
        label="Your day",
        blurb="Each morning: what to start, what is left to spend, what to eat, and a workout",
        default_at=time(8, 0),
        # Short on purpose: a morning brief at 6pm is not late, it is wrong.
        default_grace=3,
        run=morning_brief,
        posts="nudges",
    ),
}


# ─── due ─────────────────────────────────────────────────────────────────────

def runs_today(row: Schedule, today: date) -> bool:
    if row.repeat == "weekly":
        return today.weekday() in (row.days or [])
    return True     # daily, and once — which is armed until it has run


def is_due(row: Schedule, now_local: datetime) -> bool:
    """Enabled, a day it runs, past its time, not yet run today, not too late.

    The day stamp rather than a timestamp is what makes this safe: a tick that
    fires twice, a laptop waking up, a dispatcher run by hand — none of them
    can run a job twice in one day. It is also what gives catch-up for free,
    which `grace_hours` then bounds.
    """
    if not row.enabled or row.job not in JOBS:
        return False
    today = now_local.date()
    if not runs_today(row, today):
        return False
    if row.last_run_local_day is not None and row.last_run_local_day >= today:
        return False
    at = datetime.combine(today, row.at_local_time, tzinfo=now_local.tzinfo)
    return at <= now_local < at + timedelta(hours=row.grace_hours)


async def due(session: AsyncSession, now_local: datetime | None = None) -> list[Schedule]:
    now_local = now_local or datetime.now(IST)
    rows = (await session.scalars(
        select(Schedule).where(Schedule.deleted_at.is_(None)).order_by(Schedule.at_local_time)
    )).all()
    return [r for r in rows if is_due(r, now_local)]


# ─── running one ─────────────────────────────────────────────────────────────

NARRATE = (
    "You are writing one line in an ongoing conversation with the person whose "
    "ledger you keep. You were not asked anything: you ran on a schedule, did "
    "the work below, and are telling them what you found.\n"
    "One or two sentences. Their register — Hinglish as they write it. Lead "
    "with the number that matters and what it is waiting on. The details are "
    "already on cards under your line, so never list them.\n"
    "Never invent a number that is not in the summary. No greeting, no "
    "headings, no sign-off, no offer to help."
)


class Speaker(Protocol):
    """What `narrate` needs to know about whoever ran: a scheduled `Job`, or a
    borrowed routine such as work sync that no schedule of ours fires."""

    key: str
    label: str
    blurb: str


async def post_turn(session: AsyncSession, user_id: str, text: str, cards: list,
                    trace: list, model: str) -> None:
    """Append one agent turn to the thread, with no user message before it.

    Writing "aaj ke payments dekh lo" into the thread as though they had typed
    it would put words in their mouth, and would come back as history the
    model reads next turn. `model` names who spoke — `schedule:categorise`,
    `routine:work-sync` — and is how a later run finds the last one.
    """
    convo = await _thread(session, user_id)
    seq = (await session.scalar(select(func.coalesce(func.max(Message.seq), 0)).where(
        Message.conversation_id == convo.id))) or 0
    session.add(Message(conversation_id=convo.id, user_id=user_id, seq=seq + 1,
                        role="agent", text=text, cards=cards, tool_trace=trace,
                        tokens_in=0, tokens_out=0, model=model))


async def narrate(job: Speaker, summary: str, facts: dict) -> str:
    """The agent's own line about what the job found.

    A template would read like a template, and the premise of this app is that
    the agent is the app. One call, and a failure costs the sentence rather
    than the turn: the work already happened, and losing the report because a
    line could not be written would be the worst of both.
    """
    try:
        resp = await respond(
            instructions=NARRATE, effort="none", cache_key="cortex-narrate",
            input=[{"role": "user", "content":
                    f"The job that ran: {job.label} — {job.blurb}\n"
                    f"What it found: {summary}\n"
                    f"<facts>{json.dumps(facts, default=str)[:2000]}</facts>"}],
        )
        line = (resp.output_text or "").strip()
        if line:
            return line
    except Exception:  # noqa: BLE001 — the turn matters more than the sentence
        log.exception("narration failed for %s; falling back to the plain line", job.key)
    return f"{job.label}: {summary}."


async def post_nudges(session: AsyncSession, job: Job, row: Schedule, specs: list[dict],
                      day: date, narrated: bool) -> list[Nudge]:
    """One nudge per spec, each naming the run that made it — and nothing in
    the thread. A nudge enters the conversation only when the person hands it
    over.

    A spec that carries its `line` keeps it, None included: Meals today says
    nothing of its own because its page shows the plan live. One without is
    said by the agent, from its plain summary — or is that summary, when
    narration is off.
    """
    made = []
    for spec in specs:
        if "line" in spec:
            line = spec["line"]
        elif narrated:
            line = await narrate(job, spec["summary"], spec.get("facts") or {})
        else:
            line = spec["summary"]
        made.append(Nudge(user_id=row.user_id, kind=spec["kind"], schedule_id=row.id,
                          local_day=day, title=spec["title"], line=line,
                          refs=spec.get("refs") or {}))
    session.add_all(made)
    return made


async def run_one(session: AsyncSession, row: Schedule, *, now_local: datetime | None = None,
                  narrated: bool = True) -> Turn | list[Nudge] | None:
    """Run one schedule and post what it found — a turn, or nudges. Stamps
    the day either way.

    A failure stamps the day too, and records why. The alternative — retry on
    the next tick — turns one broken job into a failure every hour of its
    grace window, and an hourly tick is not where you learn that a key expired.
    """
    now_local = now_local or datetime.now(IST)
    job = JOBS[row.job]
    row.last_run_local_day = now_local.date()
    row.last_run_at = now_local
    if row.repeat == "once":
        row.enabled = False

    try:
        if job.posts == "nudges":
            out = await job.run(session, row.user_id, row.params or {}, now_local)
        else:
            out = await job.run(session, row.user_id, row.params or {})
    except Exception as e:  # noqa: BLE001 — one job must never stop the tick
        row.last_error = f"{type(e).__name__}: {e}"[:500]
        log.exception("scheduled job %s failed", row.job)
        await session.commit()
        return None

    row.last_error = None
    if not out:
        await session.commit()
        return None

    if job.posts == "nudges":
        made = await post_nudges(session, job, row, out, now_local.date(), narrated)
        await session.commit()
        return made

    cards, summary = out
    text = await narrate(job, summary, {"cards": len(cards)}) if narrated else \
        f"{job.label}: {summary}."
    turn = Turn(text=text, cards=[C.AgentCard(text=text).model_dump(), *cards],
                trace=[{"job": row.job, "scheduled": True, "summary": summary}])
    await post_turn(session, row.user_id, turn.text, turn.cards, turn.trace,
                    f"schedule:{row.job}")
    await session.commit()
    return turn


async def run_due(session: AsyncSession, now_local: datetime | None = None,
                  narrated: bool = True) -> list[tuple[Schedule, Turn | list[Nudge] | None]]:
    """The tick. Every due job, each in its own try, none blocking another.
    Each comes back with its row, whose `last_error` tells a failure from a
    run with nothing to say."""
    now_local = now_local or datetime.now(IST)
    out = []
    for row in await due(session, now_local):
        out.append((row, await run_one(session, row, now_local=now_local,
                                       narrated=narrated)))
    return out
