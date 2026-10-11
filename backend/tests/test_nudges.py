"""spec/in-progress/nudges.md — what Spica says without being asked.

A scheduled job was going to speak into the thread, and an unprompted message
in the person's conversation reads as one nobody sent. These assert what
replaced it: the bell's two routes — a week of nudges, newest first, and the
three switches each one has — and the morning brief, which writes Your day,
Meals today and Workout from live rows and today's plan, **and nothing into
the thread**.

The plan is today-plan.md's model call; here it is a fixed plan, so no model is
called and the brief's own reading of the rows is what is under test.
"""

from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from tests.helpers import the_user, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")

FIELDS = {"id", "kind", "title", "line", "local_day", "created_at", "seen_at", "done_at",
          "dismissed_at", "schedule_id", "refs"}
DAY = date(2026, 9, 15)


def _at(hh: int, mm: int = 0, day: date = DAY) -> datetime:
    from app.agent.jobs import IST
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST)


def _today() -> date:
    from app.agent.jobs import IST
    return datetime.now(IST).date()


async def _nudge(db_session, user: str, **over):
    from app.models.nudges import Nudge
    body = dict(id=ulid(), user_id=user, kind="day", local_day=_today(), title="Your day",
                line="Teen kaam aaj ke hain.", refs={})
    body.update(over)
    row = Nudge(**body)
    db_session.add(row)
    await db_session.commit()
    return row


async def _someone(db_session, **targets):
    """A second person, with nothing of the first's — so counts are exactly
    what the test made, and nothing they own is the seeded user's to see."""
    from app.models.base import new_id
    from app.models.users import User
    person = User(id=new_id(), display_name="Someone else", **targets)
    db_session.add(person)
    await db_session.commit()
    return person.id


# ─── the routes ──────────────────────────────────────────────────────────────

async def test_the_list_is_the_last_week_newest_first(client, db_session):
    me = await the_user(db_session)
    t0 = datetime.now(UTC)
    old = await _nudge(db_session, me, local_day=_today() - timedelta(days=3), kind="meals",
                       title="Meals today", line=None, refs={"plan_day": "x"},
                       created_at=t0 - timedelta(days=3))
    new = await _nudge(db_session, me, created_at=t0)
    edge = await _nudge(db_session, me, local_day=_today() - timedelta(days=6),
                        created_at=t0 - timedelta(days=6))
    gone = await _nudge(db_session, me, local_day=_today() - timedelta(days=7),
                        created_at=t0 - timedelta(days=7))
    deleted = await _nudge(db_session, me, created_at=t0, deleted_at=t0)

    r = await client.get("/nudges")
    assert r.status_code == 200
    listed = r.json()
    ids = [n["id"] for n in listed]
    assert set(listed[0]) == FIELDS, "the contract the phone is built against"
    mine = [i for i in ids if i in {old.id, new.id, edge.id}]
    assert mine == [new.id, old.id, edge.id], "newest first"
    assert gone.id not in ids, "seven local days, today included — the eighth is gone"
    assert deleted.id not in ids
    m = next(n for n in listed if n["id"] == old.id)
    assert m["line"] is None and m["refs"] == {"plan_day": "x"} and m["kind"] == "meals"
    assert m["seen_at"] is None and m["done_at"] is None and m["dismissed_at"] is None

    today_only = [n["id"] for n in (await client.get("/nudges?days=1")).json()]
    assert new.id in today_only and old.id not in today_only
    assert (await client.get("/nudges?days=0")).status_code == 422


async def test_seen_done_and_dismissed_stamp_and_clear(client, db_session):
    """True stamps now, false clears; a switch left out is left alone."""
    me = await the_user(db_session)
    n = await _nudge(db_session, me)

    r = await client.patch(f"/nudges/{n.id}", json={"seen": True})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == FIELDS and body["seen_at"] and body["done_at"] is None

    body = (await client.patch(f"/nudges/{n.id}", json={"done": True, "dismissed": True})).json()
    assert body["seen_at"] and body["done_at"] and body["dismissed_at"], "seen is left alone"

    body = (await client.patch(f"/nudges/{n.id}", json={"dismissed": False})).json()
    assert body["dismissed_at"] is None and body["done_at"], "false clears only its own"

    body = (await client.patch(f"/nudges/{n.id}", json={"seen": False, "done": False})).json()
    assert body["seen_at"] is None and body["done_at"] is None

    assert (await client.patch(f"/nudges/{n.id}", json={"read": True})).status_code == 422


async def test_someone_elses_or_a_deleted_nudge_is_not_found(client, db_session):
    other = await _someone(db_session)
    theirs = await _nudge(db_session, other)
    me = await the_user(db_session)
    dead = await _nudge(db_session, me, deleted_at=datetime.now(UTC))

    assert (await client.patch(f"/nudges/{theirs.id}", json={"seen": True})).status_code == 404
    assert (await client.patch(f"/nudges/{dead.id}", json={"seen": True})).status_code == 404
    assert (await client.patch("/nudges/NOSUCHNUDGE", json={"seen": True})).status_code == 404
    assert theirs.id not in [n["id"] for n in (await client.get("/nudges")).json()]
    await db_session.refresh(theirs)
    assert theirs.seen_at is None, "untouched"


# ─── the morning brief ───────────────────────────────────────────────────────

PLAN = {
    "local_day": DAY.isoformat(), "available": True, "done": False,
    "slots_ahead": ["Lunch", "Dinner"],
    "meals": [
        {"slot": "Lunch", "dish_id": None, "name": "Rajma chawal", "kcal": 620,
         "protein_g": 24.0, "idea": True},
        {"slot": "Dinner", "dish_id": None, "name": "Paneer bhurji, 2 roti", "kcal": 640,
         "protein_g": 38.0, "idea": True},
    ],
    "workout": {"kind": "run", "name": "Easy run", "minutes": 30,
                "why": "Two rest days this week; an easy 30 keeps the streak",
                "exercises": [], "idea": True},
}


def _plan(monkeypatch, plan: dict) -> list:
    """today-plan.md's plan, fixed. Records how it was asked for."""
    asked = []

    async def fixed(session, user, day, clock):
        asked.append((user, day, clock))
        return plan
    monkeypatch.setattr("app.agent.brief.plan_today", fixed)
    return asked


async def _brief_for(db_session):
    """A person with a week's worth of state, and their morning brief at 8:00:
    two tasks due today, one late, one with no date, one done; a breakfast of
    30 g protein against a 120 g target; an income and one spend."""
    from app.models.diet import MealLog
    from app.models.paisa import Transaction
    from app.models.schedules import Schedule
    from app.models.work import Project, Task

    person = await _someone(db_session, protein_g_target=120, kcal_target=2000)
    home = Project(user_id=person, key="personal", name="Personal", color="#7A8578",
                   is_default=True)
    db_session.add(home)
    await db_session.flush()
    task = dict(user_id=person, project_id=home.id, source="manual")
    late = Task(title="Send the invoice", due=DAY - timedelta(days=2), **task)
    due = [Task(title=f"Due today {i}", due=DAY, priority=i, **task) for i in (1, 2)]
    db_session.add_all([
        late, *due,
        Task(title="Someday", **task),
        Task(title="Finished", due=DAY, status="done", done_at=_at(7), **task),
        MealLog(user_id=person, occurred_at=_at(7, 30), local_day=DAY, meal_type="Breakfast",
                dish="Eggs and toast", kcal=380, protein_g=30, source="manual"),
        Transaction(user_id=person, occurred_at=_at(9, 0, DAY.replace(day=1)),
                    local_day=DAY.replace(day=1), amount_paise=4_500_000, direction="credit",
                    kind="income", category="Salary", description="Salary", source="manual"),
        Transaction(user_id=person, occurred_at=_at(7, 45), local_day=DAY, amount_paise=20_000,
                    direction="debit", kind="expense", category="Food", description="Chai",
                    source="manual"),
    ])
    sched = Schedule(id=ulid(), user_id=person, job="morning_brief", at_local_time=time(8, 0),
                     grace_hours=3)
    db_session.add(sched)
    await db_session.commit()
    return person, sched, [late.id, due[0].id, due[1].id]


async def _nudges_of(db_session, user):
    from app.models.nudges import Nudge
    return list((await db_session.scalars(select(Nudge).where(Nudge.user_id == user)
                                          .order_by(Nudge.created_at, Nudge.id))).all())


async def _messages(db_session) -> int:
    from app.models.chat import Message
    return await db_session.scalar(select(func.count()).select_from(Message))


async def test_the_morning_brief_writes_three_nudges_and_nothing_in_the_thread(
        client, db_session, monkeypatch):
    from app.agent import jobs
    from app.paisa_summary import paisa_summary
    person, sched, task_ids = await _brief_for(db_session)
    asked = _plan(monkeypatch, PLAN)
    before = await _messages(db_session)

    made = await jobs.run_one(db_session, sched, now_local=_at(8), narrated=False)

    assert asked == [(person, DAY, "08:00")], "the plan Home reads, at the run's clock"
    assert [n.kind for n in made] == ["day", "meals", "workout"]
    assert await _messages(db_session) == before, "a nudges job writes nothing into the thread"
    stored = await _nudges_of(db_session, person)
    assert {n.id for n in stored} == {n.id for n in made}
    assert all(n.schedule_id == sched.id and n.local_day == DAY for n in stored), \
        "every nudge names the run that made it, and its day"

    day, meals, workout = made
    left = (await paisa_summary(db_session, person, DAY.replace(day=1), DAY,
                                {"limit_today"}))["limit_today"]["left_paise"]
    assert day.title == "Your day"
    assert day.line == (f"2 due, 1 late · ₹{round(left / 100):,} left · "
                        f"90 g protein to go · lunch and dinner planned"), \
        "narration off: the plain summary, every number from the rows"
    assert day.refs == {"plan_day": "2026-09-15", "task_ids": task_ids}, \
        "live ids — late first, then today's; not the undated, not the done"
    assert meals.title == "Meals today" and meals.line is None, "the page shows the plan live"
    assert meals.refs == {"plan_day": "2026-09-15"}
    assert workout.title == "Workout" and workout.line == PLAN["workout"]["why"]
    assert workout.refs == {"plan_day": "2026-09-15"}

    await db_session.refresh(sched)
    assert sched.last_run_local_day == DAY and sched.last_error is None


async def test_the_days_line_is_the_agents_own_when_narrated(client, db_session, monkeypatch):
    from app.agent import jobs
    _, sched, _ = await _brief_for(db_session)
    _plan(monkeypatch, PLAN)
    sent = []

    async def said(**kw):
        sent.append(kw)
        return SimpleNamespace(output_text="Do kaam aaj ke hain, ek late — invoice pehle.")
    monkeypatch.setattr("app.agent.jobs.respond", said)

    day, meals, workout = await jobs.run_one(db_session, sched, now_local=_at(8))
    assert day.line == "Do kaam aaj ke hain, ek late — invoice pehle.", \
        "the agent's sentence, not the summary"
    assert meals.line is None and workout.line == PLAN["workout"]["why"], \
        "a spec that carries its line keeps it"
    assert len(sent) == 1, "one model call per brief — the plan's is shared with Home"
    assert "lunch and dinner planned" in str(sent[0]["input"])


async def test_a_rest_day_writes_no_workout_nudge(client, db_session, monkeypatch):
    from app.agent import jobs
    _, sched, _ = await _brief_for(db_session)
    _plan(monkeypatch, {**PLAN, "workout": {"kind": "rest", "name": "Rest", "minutes": None,
                                            "why": "Three runs this week", "exercises": []}})
    made = await jobs.run_one(db_session, sched, now_local=_at(8), narrated=False)
    assert [n.kind for n in made] == ["day", "meals"]


async def test_no_plan_is_said_and_never_a_meals_nudge(client, db_session, monkeypatch):
    """Unknown is not zero: a plan that could not be made is said, not
    skipped as though the day were planned."""
    from app.agent import jobs
    _, sched, _ = await _brief_for(db_session)
    _plan(monkeypatch, {**PLAN, "available": False, "meals": [], "workout": None})
    made = await jobs.run_one(db_session, sched, now_local=_at(8), narrated=False)
    assert [n.kind for n in made] == ["day"]
    assert made[0].line.endswith("no meal plan yet")


async def test_the_same_day_twice_writes_nothing_new(client, db_session, monkeypatch):
    """The day stamp: a tick that fires again, a dispatcher run by hand — no
    second brief."""
    from app.agent import jobs
    person, sched, _ = await _brief_for(db_session)
    _plan(monkeypatch, PLAN)
    assert len(await jobs.run_one(db_session, sched, now_local=_at(8), narrated=False)) == 3

    ran_for = []

    async def spy(session, user, params, now_local):
        ran_for.append(user)
        return None
    monkeypatch.setitem(jobs.JOBS, "morning_brief",
                        SimpleNamespace(**{**jobs.JOBS["morning_brief"].__dict__, "run": spy}))
    for minute in (5, 30):
        await jobs.run_due(db_session, _at(8, minute), narrated=False)
    assert person not in ran_for, "stamped today, so the tick passes it by"
    assert len(await _nudges_of(db_session, person)) == 3


async def test_a_first_day_account_gets_no_brief(client, db_session, monkeypatch):
    """Nothing logged yet is nothing to look at — Getting started is the first
    day's voice."""
    from app.agent import jobs
    from app.models.schedules import Schedule
    person = await _someone(db_session)
    sched = Schedule(id=ulid(), user_id=person, job="morning_brief", at_local_time=time(8, 0),
                     grace_hours=3)
    db_session.add(sched)
    await db_session.commit()
    asked = _plan(monkeypatch, PLAN)

    assert await jobs.run_one(db_session, sched, now_local=_at(8), narrated=False) is None
    assert await _nudges_of(db_session, person) == [] and asked == []


async def test_the_brief_is_seeded_and_listed(client):
    """Seeded by the migration, on at 8:00 — Daily runs shows it working."""
    from app.agent.jobs import JOBS
    assert JOBS["morning_brief"].posts == "nudges" and JOBS["categorise"].posts == "thread"
    listed = (await client.get("/schedules")).json()
    brief = next(s for s in listed if s["job"] == "morning_brief")
    assert brief["label"] == "Your day" and brief["at_local_time"].startswith("08:00")
    assert brief["enabled"] is True and brief["grace_hours"] == 3
