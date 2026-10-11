"""spec/in-progress/schedules.md — the things Spica does on its own.

`scripts/categorise.py` was written as a nightly job and ran only when someone
typed a command; its docstring suggested a crontab line nobody installed. These
assert the table that replaced that idea: the due predicate clause by clause,
that a day stamp makes a second run impossible, that a failure is bounded and
visible, and that what a job produces is one agent turn in the thread — never a
user message the person did not type.
"""

from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

import pytest

from tests.helpers import ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")

IST = None  # bound in `_at`, from the module under test


def _at(hh: int, mm: int = 0, day: int = 15):
    from app.agent.jobs import IST as tz
    return datetime(2026, 9, day, hh, mm, tzinfo=tz)


def row(**over):
    """A schedule in memory — the due predicate is pure, so most of this file
    never touches the database."""
    from app.models.schedules import Schedule
    body = dict(id=ulid(), user_id="u", job="categorise", at_local_time=time(20, 30),
                repeat="daily", days=[], params={}, enabled=True, grace_hours=12,
                last_run_local_day=None)
    body.update(over)
    return Schedule(**body)


async def make(client, **over):
    body = {"id": ulid(), "job": "categorise", "at_local_time": "20:30"}
    body.update(over)
    return await client.post("/schedules", json=body)


# ─── due, clause by clause ───────────────────────────────────────────────────

async def test_due_needs_every_clause(client):
    from app.agent.jobs import is_due
    assert is_due(row(), _at(20, 30)), "exactly on time is due"
    assert is_due(row(), _at(23, 59)), "inside the grace is due"

    assert not is_due(row(), _at(20, 29)), "before its time"
    assert not is_due(row(enabled=False), _at(21)), "turned off"
    assert not is_due(row(last_run_local_day=date(2026, 9, 15)), _at(21)), "already ran today"
    assert not is_due(row(grace_hours=1), _at(22)), "past the grace"
    assert is_due(row(last_run_local_day=date(2026, 9, 14)), _at(21)), "ran yesterday, not today"


async def test_a_job_missed_overnight_runs_in_the_morning(client):
    """The laptop was shut at 20:30. The first tick that finds it runs it —
    that is what the day stamp buys — and `grace_hours` is what stops a
    *morning* brief from arriving at six in the evening."""
    from app.agent.jobs import is_due
    overnight = row(grace_hours=12)          # 20:30 + 12h = 08:30 tomorrow
    assert is_due(overnight, _at(8, 0, day=16)) is False, "a new day, before its time"
    assert is_due(overnight, _at(23, 0)), "same night, still inside grace"
    assert not is_due(row(grace_hours=2), _at(23, 0)), "a short grace says it is too late"


async def test_weekly_runs_only_on_its_days_and_once_is_armed_until_it_runs(client):
    from app.agent.jobs import is_due, runs_today
    # 2026-09-15 is a Tuesday (weekday 1).
    assert runs_today(row(repeat="weekly", days=[1]), date(2026, 9, 15))
    assert not runs_today(row(repeat="weekly", days=[0, 2]), date(2026, 9, 15))
    assert is_due(row(repeat="weekly", days=[1]), _at(21))
    assert not is_due(row(repeat="weekly", days=[6]), _at(21))
    assert is_due(row(repeat="once"), _at(21)), "once is due until it has run"


async def test_a_job_the_registry_does_not_know_is_never_due(client):
    from app.agent.jobs import is_due
    assert not is_due(row(job="not_built_yet"), _at(21))


# ─── the routes ──────────────────────────────────────────────────────────────

async def test_the_four_routes(client):
    listed = (await client.get("/schedules")).json()
    mine = next(s for s in listed if s["job"] == "categorise")
    assert mine["label"] == "Review payments" and mine["blurb"]
    assert mine["at_local_time"].startswith("20:30")

    r = await client.patch(f"/schedules/{mine['id']}",
                           json={"at_local_time": "21:15", "enabled": False})
    assert r.status_code == 200
    assert r.json()["at_local_time"].startswith("21:15") and r.json()["enabled"] is False
    assert r.json()["due_now"] is False, "a job that is off is never due"

    await client.patch(f"/schedules/{mine['id']}",
                       json={"at_local_time": "20:30", "enabled": True})


async def test_a_job_that_does_not_exist_is_refused(client):
    """A schedule pointing at nothing would sit in the UI looking like it
    works, so the vocabulary is closed and checked at the door."""
    r = await make(client, job="make_me_rich")
    assert r.status_code == 422 and "categorise" in r.text


async def test_one_schedule_per_job(client):
    r = await make(client)
    assert r.status_code == 409, r.text


async def test_a_weekly_schedule_needs_a_day(client):
    listed = (await client.get("/schedules")).json()
    mine = next(s for s in listed if s["job"] == "categorise")
    r = await client.patch(f"/schedules/{mine['id']}", json={"repeat": "weekly", "days": []})
    assert r.status_code == 422


# ─── running ─────────────────────────────────────────────────────────────────

async def _one(db_session, user, **over):
    """The user's categorise schedule, set to what this test needs.

    The row is seeded by the migration, so tests adjust it rather than insert a
    second — one schedule per job is the rule, and a test that quietly broke it
    would be testing a state the app cannot reach.
    """
    from sqlalchemy import select

    from app.models.schedules import Schedule
    r = await db_session.scalar(select(Schedule).where(
        Schedule.user_id == user, Schedule.job == "categorise",
        Schedule.deleted_at.is_(None)))
    if r is None:
        r = Schedule(id=ulid(), user_id=user, job="categorise")
        db_session.add(r)
    body = dict(at_local_time=time(6, 0), repeat="daily", days=[], params={},
                enabled=True, grace_hours=20, last_run_local_day=None,
                last_run_at=None, last_error=None)
    body.update(over)
    for key, value in body.items():
        setattr(r, key, value)
    await db_session.commit()
    return r


async def _user(db_session):
    from tests.helpers import the_user
    return await the_user(db_session)


async def _messages(db_session, user):
    from sqlalchemy import select

    from app.models.chat import Message
    return list((await db_session.scalars(
        select(Message).where(Message.user_id == user).order_by(Message.seq))).all())


async def test_a_run_with_nothing_to_report_says_nothing(client, db_session, monkeypatch):
    """A thread that collects a daily "nothing to report" teaches the user to
    scroll past the thing that matters on the night it does."""
    from app.agent import jobs
    user = await _user(db_session)
    sched = await _one(db_session, user)
    before = len(await _messages(db_session, user))

    async def quiet(session, u, params):
        return None
    monkeypatch.setitem(jobs.JOBS, "categorise",
                        SimpleNamespace(**{**jobs.JOBS["categorise"].__dict__, "run": quiet}))

    assert await jobs.run_one(db_session, sched, now_local=_at(9)) is None
    assert len(await _messages(db_session, user)) == before, "no turn was appended"
    await db_session.refresh(sched)
    assert sched.last_run_local_day == date(2026, 9, 15), "it still ran; it just said nothing"


async def test_a_run_with_something_appends_one_agent_turn_and_no_user_message(
        client, db_session, monkeypatch, fake):
    """Writing "aaj ke payments dekh lo" into the thread as though they had
    typed it would put words in their mouth — and would come back as history
    the model reads next turn."""
    from app.agent import cards as C
    from app.agent import jobs
    user = await _user(db_session)
    sched = await _one(db_session, user, params={"note": "ignored by this job"})
    before = await _messages(db_session, user)

    card = C.ConfirmCard(source="paisa", row_id="t-1", state="proposed",
                         lede="₹180 · Egg roll", fields=[])

    async def something(session, u, params):
        return [card.model_dump()], "1 to check"
    monkeypatch.setitem(jobs.JOBS, "categorise",
                        SimpleNamespace(**{**jobs.JOBS["categorise"].__dict__, "run": something}))
    fake()   # the seam is mocked; narrate() gets the fake's reply

    turn = await jobs.run_one(db_session, sched, now_local=_at(9))
    assert turn is not None
    after = await _messages(db_session, user)
    new = after[len(before):]
    assert [m.role for m in new] == ["agent"], "one agent turn, and no user message"
    assert new[0].model == "schedule:categorise"
    assert new[0].tool_trace[0]["scheduled"] is True
    kinds = [c["kind"] for c in new[0].cards]
    assert kinds[0] == "agent" and "confirm" in kinds, "the line leads, the cards follow"


async def test_the_turn_survives_a_narration_that_fails(client, db_session, monkeypatch):
    """The work already happened. Losing the report because a sentence could
    not be written would be the worst of both."""
    from app.agent import jobs
    user = await _user(db_session)
    sched = await _one(db_session, user)

    async def something(session, u, params):
        return [], "3 to check"
    monkeypatch.setitem(jobs.JOBS, "categorise",
                        SimpleNamespace(**{**jobs.JOBS["categorise"].__dict__, "run": something}))

    async def broken(**kw):
        raise RuntimeError("the model is down")
    monkeypatch.setattr("app.agent.jobs.respond", broken)

    turn = await jobs.run_one(db_session, sched, now_local=_at(9))
    assert turn is not None and "3 to check" in turn.text
    assert (await _messages(db_session, user))[-1].role == "agent"


async def test_a_failing_job_is_stamped_and_visible_and_does_not_retry(
        client, db_session, monkeypatch):
    """One broken job retried every five minutes is 288 failures a day, and
    the tick is not where you learn that a key expired."""
    from app.agent import jobs
    user = await _user(db_session)
    sched = await _one(db_session, user)

    async def boom(session, u, params):
        raise RuntimeError("no key")
    monkeypatch.setitem(jobs.JOBS, "categorise",
                        SimpleNamespace(**{**jobs.JOBS["categorise"].__dict__, "run": boom}))

    assert await jobs.run_one(db_session, sched, now_local=_at(9)) is None
    await db_session.refresh(sched)
    assert sched.last_error and "no key" in sched.last_error
    assert sched.last_run_local_day == date(2026, 9, 15)
    assert not jobs.is_due(sched, _at(10)), "stamped, so it waits for tomorrow"


async def test_a_job_runs_once_a_day_however_often_the_tick_fires(
        client, db_session, monkeypatch, fake):
    from app.agent import jobs
    user = await _user(db_session)
    await _one(db_session, user)
    ran = []

    async def counted(session, u, params):
        ran.append(1)
        return [], "1 to check"
    monkeypatch.setitem(jobs.JOBS, "categorise",
                        SimpleNamespace(**{**jobs.JOBS["categorise"].__dict__, "run": counted}))
    # The morning brief is seeded on, and 9:00 is inside its grace — the tick
    # runs it too. It is not what this test counts (test_nudges.py is).
    async def silent(session, u, params, now_local):
        return None
    monkeypatch.setitem(jobs.JOBS, "morning_brief",
                        SimpleNamespace(**{**jobs.JOBS["morning_brief"].__dict__, "run": silent}))
    fake()

    for _ in range(4):
        await jobs.run_due(db_session, _at(9))
    assert len(ran) == 1, "a five-minute tick must not run a job five times"

    await jobs.run_due(db_session, _at(9) + timedelta(days=1))
    assert len(ran) == 2, "tomorrow it runs again"


async def test_once_turns_itself_off_and_params_reach_the_job(
        client, db_session, monkeypatch, fake):
    """`params` is the whole reason nothing a run needs is hardcoded."""
    from app.agent import jobs
    user = await _user(db_session)
    sched = await _one(db_session, user, repeat="once", params={"day": "2026-08-20"})
    seen = {}

    async def spy(session, u, params):
        seen.update(params)
        return [], "1 to check"
    monkeypatch.setitem(jobs.JOBS, "categorise",
                        SimpleNamespace(**{**jobs.JOBS["categorise"].__dict__, "run": spy}))
    fake()

    await jobs.run_one(db_session, sched, now_local=_at(9))
    assert seen == {"day": "2026-08-20"}, "the row's params, not a constant in code"
    await db_session.refresh(sched)
    assert sched.enabled is False, "once has had its once"


async def test_the_registry_holds_the_job_and_the_row_holds_the_choice(client):
    """Defaults seed a new row and are read at no other time. A job reading a
    constant from code at run time would be a setting nobody can see."""
    from app.agent.jobs import JOBS
    for key, job in JOBS.items():
        assert job.key == key and job.label and job.blurb
        assert callable(job.run) and job.default_grace > 0
    listed = (await client.get("/schedules")).json()
    assert {s["job"] for s in listed} <= set(JOBS), "no row points at code that is gone"
