"""spec/done/workouts.md — the exercise library.

A library to suggest from, not a ledger to record into: a workout is a habit
log, yes or no. So the tests are about *what exists*, *what the filters answer*,
and the one stored count in Spica that has no ledger under it.
"""

import pytest

from tests.helpers import ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def an_exercise(client, name=None, **over):
    body = {"id": ulid(), "name": name or f"Exercise {ulid()[-6:]}",
            "kind": "strength", "muscle_group": "legs",
            "equipment": "barbell", "typical_minutes": 12}
    body.update(over)
    r = await client.post("/exercises", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def ids(client, **params):
    return [e["id"] for e in (await client.get("/exercises", params=params)).json()]


async def one(client, eid):
    return next(e for e in (await client.get("/exercises")).json() if e["id"] == eid)


# ─── what a row holds ────────────────────────────────────────────────────────

async def test_a_new_exercise_starts_never_tried(client):
    row = await an_exercise(client, "Hack squat")
    assert row["tried"] == 0 and row["last_tried"] is None
    assert row["source"] == "manual"


async def test_an_exercise_carries_its_how_to_and_its_link(client):
    """What the agent found is kept with the row, not summarised away."""
    row = await an_exercise(
        client, "Copenhagen plank",
        steps="Side plank with the top leg on a bench. 3 sets, 20s a side.",
        source_url="https://youtube.com/watch?v=test",
        image_url="https://img.test/form.gif",
        source="chat", note="adductors ke liye")
    assert row["steps"].startswith("Side plank")
    assert row["source_url"].endswith("v=test") and row["image_url"].endswith(".gif")
    assert row["source"] == "chat" and row["note"] == "adductors ke liye"


async def test_something_already_known_can_start_above_zero(client):
    """Adding an exercise you have done for years should not claim you never
    did it."""
    row = await an_exercise(client, tried=40, last_tried="2026-08-14")
    assert row["tried"] == 40 and row["last_tried"] == "2026-08-14"


async def test_an_unknown_kind_is_refused(client):
    r = await client.post("/exercises", json={"id": ulid(), "name": "Vibes", "kind": "yoga"})
    assert r.status_code == 422


# ─── the filters are the suggestion ──────────────────────────────────────────

async def test_leg_day_does_not_return_a_treadmill(client):
    """The reason `kind` is separate from `muscle_group`: cardio is not a
    muscle, and the first seeded CSV filed it as one."""
    squat = await an_exercise(client, kind="strength", muscle_group="legs-t")
    run = await an_exercise(client, kind="cardio", muscle_group=None)
    legs = await ids(client, muscle_group="legs-t")
    cardio = await ids(client, kind="cardio")
    assert squat["id"] in legs and run["id"] not in legs
    assert run["id"] in cardio and squat["id"] not in cardio


async def test_filtering_by_minutes_keeps_the_unknown_ones(client):
    """"Mere paas 20 minute hain." An exercise with no typical length is
    unknown, not too long — filtering it out would treat a missing number as a
    large one."""
    short = await an_exercise(client, typical_minutes=10)
    long_one = await an_exercise(client, typical_minutes=45)
    unknown = await an_exercise(client, typical_minutes=None)
    found = await ids(client, minutes=20)
    assert short["id"] in found and unknown["id"] in found and long_one["id"] not in found


async def test_filtering_by_equipment_is_the_no_gym_question(client):
    home = await an_exercise(client, equipment="bodyweight-t")
    gym = await an_exercise(client, equipment="barbell-t")
    found = await ids(client, equipment="bodyweight-t")
    assert home["id"] in found and gym["id"] not in found


async def test_search_matches_an_alias_not_only_the_name(client):
    """"OHP" has to find the shoulder press without a model call."""
    row = await an_exercise(client, "Overhead press test", aliases=["ohp-test", "military"])
    assert row["id"] in await ids(client, q="ohp-test")


async def test_tried_splits_what_you_know_from_what_you_bookmarked(client):
    """The distinction the old `exercise_saves` star was making, carried by an
    integer that was already there."""
    fresh = await an_exercise(client)
    known = await an_exercise(client, tried=3)
    assert fresh["id"] in await ids(client, tried=False)
    assert known["id"] in await ids(client, tried=True)
    assert known["id"] not in await ids(client, tried=False)


# ─── the count ───────────────────────────────────────────────────────────────

async def test_doing_it_increments_and_stamps_the_day(client):
    row = await an_exercise(client)
    r = await client.post(f"/exercises/{row['id']}/did", json={"local_day": "2026-08-20"})
    assert r.status_code == 200
    assert r.json()["tried"] == 1 and r.json()["last_tried"] == "2026-08-20"

    again = await client.post(f"/exercises/{row['id']}/did", json={"local_day": "2026-08-22"})
    assert again.json()["tried"] == 2 and again.json()["last_tried"] == "2026-08-22"


async def test_a_miscount_is_corrected_deliberately(client):
    """Nothing decrements on its own — a wrong count is a PATCH, so an
    accidental tap cannot quietly walk the number backwards."""
    row = await an_exercise(client)
    await client.post(f"/exercises/{row['id']}/did", json={})
    fixed = await client.patch(f"/exercises/{row['id']}", json={"tried": 0, "last_tried": None})
    assert fixed.status_code == 200
    assert fixed.json()["tried"] == 0 and fixed.json()["last_tried"] is None


async def test_tried_cannot_go_negative(client):
    row = await an_exercise(client)
    assert (await client.patch(f"/exercises/{row['id']}",
                               json={"tried": -1})).status_code == 422


# ─── ownership and lifecycle ─────────────────────────────────────────────────

async def test_every_row_belongs_to_the_user(client, db_session):
    """`user_id` is the whole scoping rule — there is no pool, which is what
    removed the NULL-author trap that 500'd this endpoint once."""
    from sqlalchemy import text
    row = await an_exercise(client)
    owner = await db_session.scalar(
        text("SELECT user_id FROM exercises WHERE id = :i"), {"i": row["id"]})
    assert owner is not None


async def test_editing_a_row_keeps_what_it_did_not_send(client):
    row = await an_exercise(client, steps="original", tried=2)
    patched = await client.patch(f"/exercises/{row['id']}", json={"note": "felt heavy"})
    assert patched.json()["note"] == "felt heavy"
    assert patched.json()["steps"] == "original" and patched.json()["tried"] == 2


async def test_deleting_takes_it_out_of_the_library(client):
    row = await an_exercise(client)
    assert (await client.delete(f"/exercises/{row['id']}")).status_code == 204
    assert row["id"] not in await ids(client)
    assert (await client.post(f"/exercises/{row['id']}/did", json={})).status_code == 404


async def test_adding_the_same_id_twice_replays(client):
    row_id = ulid()
    body = {"id": row_id, "name": f"Replay {ulid()[-5:]}", "muscle_group": "core"}
    assert (await client.post("/exercises", json=body)).status_code == 201
    again = await client.post("/exercises", json=body)
    assert again.status_code == 200 and again.json()["id"] == row_id
    assert (await ids(client)).count(row_id) == 1


async def test_a_nameless_exercise_is_refused(client):
    assert (await client.post("/exercises", json={"id": ulid(), "name": ""})).status_code == 422


async def test_the_workout_habit_is_still_a_habit(client, db_session):
    """The point of the 2026-09-07 revert: a workout is logged yes or no, the
    same way a cigarette is. Nothing records which exercises were done."""
    from sqlalchemy import text
    tables = (await db_session.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name IN ('workout_logs', 'workout_items', 'exercise_saves')"))).scalars().all()
    assert tables == []
