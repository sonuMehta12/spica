"""spec/home-day-rail.md — Home draws the day as one rail, each row at its time.

The rail never invents a time: every row it draws comes with the moment it
happened. These assert the deck carries that moment for each kind of row.
"""

import pytest

from tests.helpers import make_meal, make_transaction, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def deck(client, day):
    return (await client.get("/deck", params={"to": day})).json()


async def test_a_spend_carries_the_time_it_happened(client):
    t = (await make_transaction(client, description="Rail-chai", local_day="2026-08-21",
                                occurred_at="2026-08-21T09:15:00+05:30")).json()
    rows = (await deck(client, "2026-08-21"))["paisa"]["transactions"]
    row = next(x for x in rows if x["id"] == t["id"])
    assert row["occurred_at"].startswith("2026-08-21T03:45:00"), row["occurred_at"]


async def test_a_meal_carries_the_time_it_happened(client):
    m = (await make_meal(client, dish="Rail-poha", local_day="2026-08-21",
                         occurred_at="2026-08-21T08:40:00+05:30")).json()
    rows = (await deck(client, "2026-08-21"))["diet"]["meals"]
    row = next(x for x in rows if x["id"] == m["meal"]["id"])
    assert row["occurred_at"].startswith("2026-08-21T03:10:00"), row["occurred_at"]


async def test_a_habit_log_carries_the_time_it_happened(client):
    """The one row the deck sent without its time: a cigarette at 10:50 must
    sit at 10:50 on the rail, not at the top of the day."""
    h = (await client.post("/habits", json={"id": ulid(), "name": "Rail-Cigarettes", "direction": "break"})).json()
    log_id = ulid()
    await client.post("/habit-logs", json={
        "id": log_id, "habit_id": h["id"], "local_day": "2026-08-21",
        "occurred_at": "2026-08-21T10:50:00+05:30", "source": "manual"})
    rows = (await deck(client, "2026-08-21"))["diet"]["habit_logs"]
    row = next(x for x in rows if x["id"] == log_id)
    assert row["occurred_at"].startswith("2026-08-21T05:20:00"), row["occurred_at"]



# ─── a log said in chat lands at the moment it was said ──────────────────────

async def test_a_habit_said_in_chat_lands_at_the_moment_it_was_said(client, db_session):
    """'Ek cigarette pi' at 21:10 was a tick at noon: log_day took no time,
    so every habit said in chat sat at 12:00 on the rail."""
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)
    await client.post("/habits", json={"id": ulid(), "name": "Rail-Chat-Smoke", "direction": "break"})
    out = await T.run(db_session, user, "log_day",
                      {"local_day": "2026-08-22", "habits": [{"habit": "Rail-Chat-Smoke"}]},
                      default_time="21:10:00")
    await db_session.commit()
    log_id = out["habits"][0]["id"]
    rows = (await deck(client, "2026-08-22"))["diet"]["habit_logs"]
    row = next(x for x in rows if x["id"] == log_id)
    assert row["occurred_at"].startswith("2026-08-22T15:40:00"), row["occurred_at"]


async def test_a_meal_said_in_chat_takes_the_messages_clock(client, db_session):
    """No clock said: the meal is at the moment of the message, not midday."""
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)
    out = await T.run(db_session, user, "log_meal",
                      {"text_said": "Rail-chat 2 roti", "meal_type": "Dinner", "local_day": "2026-08-22"},
                      default_time="20:35:00")
    await db_session.commit()
    meal_id = out.get("id") or out.get("meal", {}).get("id")
    rows = (await deck(client, "2026-08-22"))["diet"]["meals"]
    row = next(x for x in rows if x["id"] == meal_id)
    assert row["occurred_at"].startswith("2026-08-22T15:05:00"), row["occurred_at"]


async def test_every_write_tool_tells_the_model_to_leave_the_time_out():
    """The model's own guess — 12:00 for a lunch — won over the message's clock."""
    from app.agent.tools import BY_NAME
    for name in ("log_payment", "log_meal", "log_day"):
        t = BY_NAME[name]["schema"]["properties"]["time"]
        assert "leave it out" in t["description"], name


# ─── a logged meal names its dish, for its picture ───────────────────────────

async def test_a_meal_names_the_first_dish_among_its_lines(client, db_session):
    """Home shows a logged meal's photo from its dish; the deck said nothing
    about which dish, so the tile was always the bowl icon."""
    from datetime import datetime, timezone
    from sqlalchemy import text
    from tests.test_dishes import make_dish
    first = await make_dish(client, "Rail-dish rajma")
    second = await make_dish(client, "Rail-dish salad")
    m = (await make_meal(client, dish="Rail-dish rajma chawal", local_day="2026-08-23")).json()
    meal_id = m["meal"]["id"]
    lines = ((first, datetime(2026, 8, 23, 8, 0, 0, tzinfo=timezone.utc)),
             (second, datetime(2026, 8, 23, 8, 0, 1, tzinfo=timezone.utc)))
    for d, at in lines:
        await db_session.execute(text("""
            INSERT INTO meal_items (id, meal_log_id, dish_id, servings, created_at)
            VALUES (:i, :m, :d, 1, :at)"""), {"i": ulid(), "m": meal_id, "d": d["id"], "at": at})
    await db_session.commit()
    rows = (await deck(client, "2026-08-23"))["diet"]["meals"]
    assert next(x for x in rows if x["id"] == meal_id)["dish_id"] == first["id"]


async def test_a_meal_of_foods_only_names_no_dish(client):
    m = (await make_meal(client, dish="Rail-dish 2 boiled eggs", local_day="2026-08-23")).json()
    rows = (await deck(client, "2026-08-23"))["diet"]["meals"]
    assert next(x for x in rows if x["id"] == m["meal"]["id"])["dish_id"] is None
