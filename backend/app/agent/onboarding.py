"""
The first run's agent. spec/done/onboarding-goals.md § The onboarding agent.

Screen 3 asks a few fixed questions. Each answer comes here, and an agent
writes what it hears through the app's own tools — the same functions, the
same savepoints and the same confirm cards as a sentence said in the chat, on
the runner's own tool loop. What differs is what it is given:

* **its own prompt**, `skills/onboarding.md`, and on the turn the question
  just asked and what is already known about the person — read live, so
  coming back mid-flow never asks for a fact twice;
* **six tools, not twenty-seven**: five the chat already has, and
  `next_question`, which only this agent has and which tells the screen to
  move on;
* **no thread.** Nothing is written to the conversation: the facts live in
  rows, and the chat agent reads rows.

**One answer is one transaction.** The routes commit for themselves, so the
turn runs on a session whose commits are savepoints inside one transaction,
committed once when the turn ends (`db.one_transaction`). A model call that
fails in the second round, or a tool that raises, takes the first round's
writes with it — never half an answer. A person's turns take a lock first,
so two at once run one after the other rather than crossing.

The picks on screen 2 are not sent: the client chooses the questions from
them, and nothing here needs them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import db
from app.agent import prompt as P
from app.agent import runner as R
from app.agent import tools as T
from app.agent.cards import rupees
from app.models.diet import Habit
from app.models.users import Memory, User, WeighIn

SKILL_FILE = Path(__file__).with_name("skills") / "onboarding.md"


async def _remember(session, user, **kw) -> dict:
    """The chat's `remember`, kept as the person's own words: the question
    asked for it and the card shows it back, so it lands confirmed (source
    `user`). The chat's own memories stay `cortex` until confirmed."""
    return await T.t_remember(session, user, **kw, _source="user")


async def t_next_question(session, user, *, status: str) -> dict:
    """Writes nothing. The screen reads it off the turn and asks the next
    question — or, when this was the last, says it has what it needs."""
    if status not in ("answered", "skipped"):
        return {"error": "status is answered or skipped"}
    return {"status": status}


#: The tools it is offered, and all it can run. Five are the chat's own
#: entries — function, schema and description — so a write here is exactly
#: the write a sentence in the chat makes; `remember` differs only in whose
#: words the memory is.
SHARED = ("update_profile", "log_day", "remember", "manage_habit", "save_task")

NEXT_QUESTION = T._tool(
    "next_question",
    "The question is done: the screen moves on and asks the next one. 'answered' "
    "once every fact the answer gave is written; 'skipped' when they skipped it, "
    "would rather not say, or answered something else — and nothing was written. "
    "Never beside a follow-up you are asking, and never for an answer you could not "
    "read: those wait for their next answer, on the same question.",
    {"status": {"type": "string", "enum": ["answered", "skipped"]}},
    ["status"], t_next_question)

TOOLS: list[dict] = [
    *({**T.BY_NAME[n], "fn": _remember} if n == "remember" else T.BY_NAME[n]
      for n in SHARED),
    NEXT_QUESTION,
]


async def known(session: AsyncSession, user: str) -> list[str]:
    """What the person has already told Spica, from their rows, one line each
    — the profile, the latest weigh-in, the targets the questions set, the
    memories, the habits. Absent is left out, never a default. Money is in
    rupees: a figure the model never converts it cannot get wrong."""
    profile = await session.get(User, user)
    if profile is None:
        return []
    weight = await session.scalar(
        select(WeighIn).where(WeighIn.user_id == user, WeighIn.deleted_at.is_(None))
        .order_by(WeighIn.local_day.desc()).limit(1))
    memories = (await session.scalars(
        select(Memory).where(Memory.user_id == user, Memory.deleted_at.is_(None))
        .order_by(Memory.kind, Memory.slug))).all()
    habits = (await session.scalars(
        select(Habit).where(Habit.user_id == user, Habit.deleted_at.is_(None))
        .order_by(Habit.name))).all()
    lines = [f"- name: {profile.display_name}", *P.about(profile, weight)]
    if profile.weight_target_kg:
        lines.append(f"- weight target: {float(profile.weight_target_kg):g} kg")
    if profile.savings_target_paise:
        lines.append(f"- saves {rupees(profile.savings_target_paise)} a month (their target)")
    lines += [f"- [{m.kind}] {m.text}" for m in memories]
    lines += [f"- tracks the habit {h.name} ({h.direction})" for h in habits]
    return lines


def _turn(question: str, text: str, local_day: date, facts: list[str]) -> str:
    """The one message the model is given: what is true now, then what they
    said. The prompt and the tools ahead of it are the same for everyone, so
    the cache holds them across accounts."""
    return (f"[today] {local_day.isoformat()} ({local_day:%A})\n"
            f"[question] {question}\n"
            f"[already known]\n" + ("\n".join(facts) or "- (nothing yet)")
            + f"\n\n{text}")


@dataclass
class Answer:
    cards: list[dict]
    #: A follow-up, or "Say that again?" — None once the screen moves on.
    reply: str | None
    next: bool


async def turn(user: str, question: str, text: str, local_day: date) -> Answer:
    """One answer to one question, in one transaction. Raises
    `runner.ModelFailed` when the model call fails, and then nothing it wrote
    is kept."""
    # One at a time per person: a second answer waits for the first to land,
    # and then reads what it wrote.
    async with db.one_transaction(lock=f"onboarding:{user}") as session:
        items = [{"role": "user", "content": _turn(question, text, local_day,
                                                    await known(session, user))}]
        done, _ = await R.rounds(session, user, items, system=SKILL_FILE.read_text(),
                                 tools=TOOLS, cache_key="cortex-onboarding", said=text,
                                 refused=None)
    moved = any(t["tool"] == "next_question" and t["ok"] for t in done.trace)
    return Answer(
        # One confirm card per write. Nothing else is sent: there is no read
        # among these tools, and the agent's words travel as `reply`.
        cards=[c for c in done.cards if c.get("kind") == "confirm"],
        # Once the screen moves on, it asks the next question itself; anything
        # the model said beside that would be a second voice over the copy.
        reply=None if moved else (done.text or None),
        next=moved,
    )
