"""
The morning brief: the day looked at before the person does.
spec/in-progress/nudges.md, the requirement in spec/in-progress/morning-brief.md.

Three nudges, not one message: **Your day** (what to start, what is left to
spend, protein to go), **Meals today** and **Workout** — so each has its own
page and its own done state. The phone sends one notification for all three.

**Every fact is read live, at run time, from the rows Home reads**: the work
counts the agent's `[work]` line uses, the paisa summary's limit, the diet
summary's protein, and today-plan.md's plan, which is cached per day so the
brief and Home share one model call. What the brief stores is the agent's line
— history, what was said at that hour — and live ids. The numbers on each page
are worked out again when it is drawn.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.commitments import due_soon
from app.diet_summary import diet_summary
from app.models.diet import MealLog
from app.models.paisa import Transaction
from app.models.work import Task
from app.paisa_summary import paisa_summary


async def plan_today(session: AsyncSession, user: str, day: date, clock: str) -> dict:
    """today-plan.md's plan for the rest of the day, at the run's clock — the
    read Home makes, so a brief at 8:00 and Home opened at 8:05 are one model
    call, not two. May come back `available: False`; the brief then says so."""
    from app.agent import plan
    return await plan.today(session, user, day, clock)


async def _anything_logged(session: AsyncSession, user: str) -> bool:
    """A first-day account gets no brief: there is nothing to look at yet, and
    Getting started is its first-day voice. The same rows Getting started
    reads — a payment, a meal, a task."""
    for model in (Transaction, MealLog, Task):
        if await session.scalar(select(model.id).where(
                model.user_id == user, model.deleted_at.is_(None)).limit(1)) is not None:
            return True
    return False


async def _work(session: AsyncSession, user: str, day: date) -> dict:
    """Late, due today and open — counted the way the agent's `[work]` line
    counts them, so the brief and the conversation cannot disagree."""
    rows = list((await session.scalars(select(Task).where(
        Task.user_id == user, Task.deleted_at.is_(None), Task.archived_at.is_(None),
        Task.status != "done",
    ).order_by(Task.due.nulls_last(), Task.priority.nulls_last(), Task.created_at))).all())
    late = [t.id for t in rows if t.due is not None and t.due < day]
    due = [t.id for t in rows if t.due == day]
    return {"late": len(late), "due_today": len(due), "open": len(rows),
            # Live ids for Your day's *Start with*: late first, then today's.
            "task_ids": late + due}


def _rupees(paise: int) -> str:
    return f"₹{round(abs(paise) / 100):,}"


def _slots(meals: list[dict]) -> str:
    names = [m["slot"].lower() for m in meals]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _due_phrase(soon: list) -> str:
    """`Rent due Fri · EMI due Sun`, two at most and how many more. Dated lines
    only: a commitment the person never gave a due day is not announced."""
    from app.commitments import due_date
    named = [f"{ln.c.name} due {due_date(ln.c.local_month, ln.c.due_day):%a}" for ln in soon[:2]]
    if len(soon) > 2:
        named.append(f"{len(soon) - 2} more")
    return " · ".join(named)


def _day_summary(work: dict, left: int | None, protein_left: float | None,
                 plan: dict, soon: list | None = None) -> str:
    """The plain line: `3 due, 1 late · ₹640 left · 92 g protein to go · lunch
    and dinner planned`. What is unknown is left out or said as unknown —
    never a zero."""
    said = []
    tasks = [f"{work['due_today']} due"] if work["due_today"] else []
    if work["late"]:
        tasks.append(f"{work['late']} late")
    if not tasks:
        tasks = [f"nothing due, {work['open']} open" if work["open"] else "nothing due"]
    said.append(", ".join(tasks))
    if soon:
        said.append(_due_phrase(soon))
    if left is not None:
        said.append(f"{_rupees(left)} left" if left >= 0 else
                    f"{_rupees(left)} over today's limit")
    if protein_left is not None:
        said.append(f"{protein_left:g} g protein to go" if protein_left > 0 else
                    "protein target met")
    if not plan.get("available"):
        said.append("no meal plan yet")
    elif plan.get("meals"):
        said.append(f"{_slots(plan['meals'])} planned")
    return " · ".join(said)


async def morning_brief(session: AsyncSession, user: str, params: dict,
                        now_local: datetime) -> list[dict] | None:
    """Your day always; Meals today when the plan has a meal left; Workout
    when the plan's workout is not a rest day."""
    if not await _anything_logged(session, user):
        return None
    day = now_local.date()
    work = await _work(session, user, day)
    limit = (await paisa_summary(session, user, day.replace(day=1), day,
                                 {"limit_today"})).get("limit_today") or {}
    protein_left = ((await diet_summary(session, user, day, day, {"today"}))
                    .get("today") or {}).get("protein_left_g")
    plan = await plan_today(session, user, day, f"{now_local:%H:%M}")
    on = {"plan_day": day.isoformat()}

    soon = await due_soon(session, user, day)
    summary = _day_summary(work, limit.get("left_paise"), protein_left, plan, soon)
    workout = plan.get("workout") if plan.get("available") else None
    out = [{
        "kind": "day", "title": "Your day", "summary": summary,
        "refs": {**on, "task_ids": work["task_ids"],
                 **({"commitment_ids": [ln.c.id for ln in soon]} if soon else {})},
        # What the narration may lean on, and nothing it could invent from.
        "facts": {"tasks": {k: work[k] for k in ("late", "due_today", "open")},
                  "left_today_paise": limit.get("left_paise"),
                  "commitments_due": [{"name": ln.c.name, "owed_paise": ln.owed_paise,
                                       "due_day": ln.c.due_day} for ln in soon],
                  "protein_to_go_g": protein_left,
                  "meals_planned": [m["slot"] for m in plan.get("meals") or []],
                  "workout": workout and {k: workout.get(k) for k in ("kind", "name", "minutes")}},
    }]
    if plan.get("available") and plan.get("meals"):
        # No line: the page shows the plan live, and a meal logged since 8:00
        # is already off it. A sentence about the meals would go stale first.
        out.append({"kind": "meals", "title": "Meals today", "line": None,
                    "summary": f"{_slots(plan['meals'])} planned", "refs": on})
    if workout and workout.get("kind") != "rest":
        minutes = f", {workout['minutes']} min" if workout.get("minutes") else ""
        out.append({"kind": "workout", "title": "Workout", "line": workout.get("why") or None,
                    "summary": f"{workout.get('name') or workout['kind']}{minutes}", "refs": on})
    return out
