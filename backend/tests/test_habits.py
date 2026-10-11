"""spec/in-progress/habits.md — the habit library.

Three habits existed because a migration inserted them; there was no route, no
screen and no tool that could add a fourth, and `/habit-logs` only ever wrote
the ticks. These assert the library itself.
"""

import pytest

from tests.helpers import ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def make(client, name, direction="build", unit=None, **over):
    body = {"id": ulid(), "name": name, "direction": direction, "unit": unit}
    body.update(over)
    return await client.post("/habits", json=body)


async def by_name(client, name):
    return next((h for h in (await client.get("/habits")).json() if h["name"] == name), None)


# ─── the library ─────────────────────────────────────────────────────────────

async def test_a_habit_can_be_started_renamed_and_retired(client):
    made = (await make(client, "Hab-Meditation", unit="minutes")).json()
    assert made["direction"] == "build" and made["unit"] == "minutes"
    assert made["days_this_week"] == 0 and made["logged_ever"] == 0

    r = await client.patch(f"/habits/{made['id']}",
                           json={"name": "Hab-Meditation 10m", "unit": None})
    assert r.status_code == 200
    assert r.json()["name"] == "Hab-Meditation 10m" and r.json()["unit"] is None

    assert (await client.delete(f"/habits/{made['id']}")).status_code == 204
    assert await by_name(client, "Hab-Meditation 10m") is None


async def test_two_habits_cannot_share_a_name_whatever_the_case(client):
    """`log_day` matches by the name the user said, so two would make a tick
    ambiguous."""
    await make(client, "Hab-Running")
    r = await make(client, "hab-running")
    assert r.status_code == 409 and "already tracked" in r.json()["detail"]


async def test_a_retired_name_can_be_used_again(client):
    """The unique constraint was plain, not partial, so a soft-deleted habit
    held its name for ever. Every other table in the schema guards uniqueness
    on `deleted_at IS NULL`; habits were the exception."""
    first = (await make(client, "Hab-Reuse")).json()
    await client.delete(f"/habits/{first['id']}")
    again = await make(client, "Hab-Reuse")
    assert again.status_code == 201, again.text


async def test_retiring_keeps_the_logs(client):
    """That you went in August is still true. The week strip keeps drawing it."""
    h = (await make(client, "Hab-Gym")).json()
    await client.post("/habit-logs", json={
        "id": ulid(), "habit_id": h["id"], "local_day": "2026-08-20",
        "occurred_at": "2026-08-20T07:00:00+05:30", "source": "manual"})
    assert (await by_name(client, "Hab-Gym"))["logged_ever"] == 1
    await client.delete(f"/habits/{h['id']}")
    logs = (await client.get("/deck", params={"to": "2026-08-20"})).json()["diet"]["habit_logs"]
    assert any(x["habit_id"] == h["id"] for x in logs), "the tick was taken with it"


async def test_a_direction_outside_build_or_break_is_refused(client):
    assert (await make(client, "Hab-Bad", direction="sideways")).status_code == 422


# ─── the agent ───────────────────────────────────────────────────────────────

async def test_the_agent_can_start_and_stop_a_habit(client, db_session):
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)

    made = await T.run(db_session, user, "manage_habit",
                       {"name": "Hab-Agent", "direction": "break", "unit": "units"})
    await db_session.commit()
    assert not made.get("error"), made
    assert made["direction"] == "break"

    renamed = await T.run(db_session, user, "manage_habit",
                          {"habit_id": made["habit_id"], "name": "Hab-Agent 2"})
    await db_session.commit()
    assert renamed["name"] == "Hab-Agent 2"

    gone = await T.run(db_session, user, "manage_habit",
                       {"habit_id": made["habit_id"], "delete": True})
    await db_session.commit()
    assert gone["deleted"] and await by_name(client, "Hab-Agent 2") is None


async def test_manage_habit_needs_a_name_or_an_id(client, db_session):
    from app.agent import tools as T
    from tests.helpers import the_user
    out = await T.run(db_session, await the_user(db_session), "manage_habit", {})
    assert "error" in out


async def test_an_untracked_habit_names_what_is_tracked_instead_of_refusing(client, db_session):
    """It used to return "no such habit" and stop, leaving the user a refusal
    with no next step. The reply can now offer to start it."""
    from app.agent import tools as T
    from tests.helpers import the_user
    out = await T.run(db_session, await the_user(db_session), "log_day", {
        "local_day": "2026-08-20", "habits": [{"habit": "Nothing-Like-This"}]})
    [entry] = out["habits"]
    assert entry["logged"] is False
    assert "not tracked" in entry["why"] and "ask" in entry["why"]
    assert entry["tracked"], "the reply has nothing to offer without this"


async def test_the_agent_does_not_tick_through_manage_habit(client):
    """One verb per tool. `log_day` is the tick."""
    from app.agent import tools as T
    props = T.BY_NAME["manage_habit"]["schema"]["properties"]
    assert "local_day" not in props and "amount" not in props


async def test_a_habit_started_mid_turn_can_be_ticked_in_the_same_turn(client, db_session):
    """The model started the habit, then passed the id it had just been handed
    into `log_day` — which matched habits by name only, so the tick was dropped
    and the reply said the tracker had not taken it. Both are addressable now."""
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)

    made = await T.run(db_session, user, "manage_habit",
                       {"name": "Hab-Journaling", "unit": "minutes"})
    await db_session.commit()
    out = await T.run(db_session, user, "log_day", {
        "local_day": "2026-08-21", "habits": [{"habit": made["habit_id"], "amount": 10}]})
    await db_session.commit()
    [entry] = out["habits"]
    assert entry["logged"] is True, entry
    assert entry["habit"] == "Hab-Journaling"

    same = await T.run(db_session, user, "log_day", {
        "local_day": "2026-08-22", "habits": [{"habit": "hab-journaling"}]})
    await db_session.commit()
    assert same["habits"][0]["logged"] is True, "the name still works, whatever the case"

    await T.run(db_session, user, "manage_habit", {"habit_id": made["habit_id"], "delete": True})
    await db_session.commit()


async def test_a_habit_can_be_changed_by_the_name_the_user_says(client, db_session):
    """Nothing ever handed the agent a habit id, so a rename dead-ended: it
    would not invent one, and rightly. The name the user says addresses it."""
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)

    await T.run(db_session, user, "manage_habit", {"name": "Hab-Pages", "unit": "minutes"})
    await db_session.commit()

    renamed = await T.run(db_session, user, "manage_habit",
                          {"habit_id": "hab-pages", "name": "Hab-Morning pages"})
    await db_session.commit()
    assert renamed["name"] == "Hab-Morning pages", renamed

    gone = await T.run(db_session, user, "manage_habit",
                       {"habit_id": "Hab-Morning pages", "delete": True})
    await db_session.commit()
    assert gone["deleted"] and gone["name"] == "Hab-Morning pages"
    assert await by_name(client, "Hab-Morning pages") is None


async def test_a_habit_that_is_not_there_says_what_is(client, db_session):
    """A refusal with the tracked list beside it, so the reply has somewhere to
    go — the same rule log_day follows on an unknown tick."""
    from app.agent import tools as T
    from tests.helpers import the_user
    out = await T.run(db_session, await the_user(db_session), "manage_habit",
                      {"habit_id": "Nothing-Like-This", "name": "Whatever"})
    assert "error" in out and out["tracked"]


async def test_every_habit_write_earns_a_card(client, db_session):
    """Cards for every write. Retiring keeps the logs, so the card says the
    tracking stopped — not that the history went."""
    from app.agent import cards
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)

    made = await T.run(db_session, user, "manage_habit",
                       {"name": "Hab-Carded", "direction": "break"})
    await db_session.commit()
    [card] = cards.from_tool("manage_habit", {}, made)
    assert card.kind == "confirm" and card.state == "written"
    assert "Hab-Carded" in card.lede and "break" in card.lede

    gone = await T.run(db_session, user, "manage_habit",
                       {"habit_id": made["habit_id"], "delete": True})
    await db_session.commit()
    [card] = cards.from_tool("manage_habit", {}, gone)
    assert card.state == "deleted" and "Hab-Carded" in card.lede
