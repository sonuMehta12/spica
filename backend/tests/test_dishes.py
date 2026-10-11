"""spec/done/dishes.md — a thing you eat, described once."""

import pytest

from tests.helpers import make_meal, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def make_dish(client, name, **over):
    body = {"id": ulid(), "name": name, "serving_label": "1 plate", "protein_g": "20"}
    body.update(over)
    r = await client.post("/dishes", json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


async def test_a_dish_needs_only_a_serving_and_protein(client):
    """Office thali is a dish and nobody cooks it: ingredients and steps are
    optional, protein is not — the diet mode turns on it."""
    d = await make_dish(client, "Test thali", serving_label="1 thali", protein_g="18")
    assert d["items"] == [] and d["minutes"] is None
    bad = await client.post("/dishes", json={"id": ulid(), "name": "No protein",
                                             "serving_label": "1 plate"})
    assert bad.status_code == 422


async def test_your_library_is_saved_or_tried(client):
    """The pool is global; the library is your slice of it."""
    d = await make_dish(client, "Test unsaved dish")
    mine = [x["id"] for x in (await client.get("/dishes?mine=true")).json()]
    pool = [x["id"] for x in (await client.get("/dishes?mine=false")).json()]
    assert d["id"] in pool and d["id"] not in mine


async def test_saving_is_a_bookmark_and_idempotent(client):
    d = await make_dish(client, "Test saved dish")
    assert (await client.put(f"/dishes/{d['id']}/save")).status_code == 204
    assert (await client.put(f"/dishes/{d['id']}/save")).status_code == 204  # one row
    mine = {x["id"]: x for x in (await client.get("/dishes")).json()}
    assert mine[d["id"]]["saved"] is True and mine[d["id"]]["tried"] == 0

    assert (await client.delete(f"/dishes/{d['id']}/save")).status_code == 204
    assert d["id"] not in {x["id"] for x in (await client.get("/dishes")).json()}


async def test_tried_is_counted_from_the_ledger(client, db_session):
    """No stored counter: delete the meal and the count drops on its own."""
    from sqlalchemy import text
    d = await make_dish(client, "Test counted dish")
    meal = await make_meal(client, dish="Test counted dish")
    meal_id = meal.json()["meal"]["id"]
    await db_session.execute(text("""
        INSERT INTO meal_items (id, meal_log_id, dish_id, servings, said)
        VALUES (:i, :m, :d, 1, 'Test counted dish')"""),
        {"i": ulid(), "m": meal_id, "d": d["id"]})
    await db_session.commit()

    mine = {x["id"]: x for x in (await client.get("/dishes")).json()}
    assert mine[d["id"]]["tried"] == 1 and mine[d["id"]]["last_tried"] == "2026-08-20"

    assert (await client.delete(f"/meals/{meal_id}")).status_code == 204
    assert d["id"] not in {x["id"] for x in (await client.get("/dishes")).json()}


async def test_a_component_dish_is_flattened_for_the_caller(client, db_session):
    """Ghar ka dinner claimed to be cookable on its dal alone until the
    ingredients inside its component were expanded."""
    from sqlalchemy import text
    inner = await make_dish(client, "Test roti sabzi")
    outer = await make_dish(client, "Test ghar dinner")
    food = (await client.post("/pantry", json={"id": ulid(), "food_name": "Test atta"})).json()
    await db_session.execute(text("""
        INSERT INTO dish_items (id, dish_id, food_id, quantity, servings)
        VALUES (:i, :d, :f, 60, 1)"""), {"i": ulid(), "d": inner["id"], "f": food["food_id"]})
    await db_session.execute(text("""
        INSERT INTO dish_items (id, dish_id, component_dish_id, servings)
        VALUES (:i, :d, :c, 2)"""), {"i": ulid(), "d": outer["id"], "c": inner["id"]})
    await db_session.commit()

    rows = {x["id"]: x for x in (await client.get("/dishes?mine=false")).json()}
    lines = rows[outer["id"]]["items"]
    assert len(lines) == 1
    assert lines[0]["food_name"] == "Test atta"
    assert lines[0]["quantity"] == 120           # scaled by the 2 servings
    assert lines[0]["from_dish"] == inner["id"]  # the UI can say where it came from


async def test_search_matches_a_name_or_an_alias(client):
    await make_dish(client, "Test whey shake", aliases=["protein shake"])
    by_name = [d["name"] for d in (await client.get("/dishes?mine=false&q=whey")).json()]
    by_alias = [d["name"] for d in
                (await client.get("/dishes?mine=false&q=protein shake")).json()]
    assert "Test whey shake" in by_name and "Test whey shake" in by_alias


async def test_a_dish_you_have_eaten_is_unstarred_not_deleted(client, db_session):
    from sqlalchemy import text
    d = await make_dish(client, "Test eaten dish")
    meal = await make_meal(client, dish="Test eaten dish")
    await db_session.execute(text("""
        INSERT INTO meal_items (id, meal_log_id, dish_id, servings)
        VALUES (:i, :m, :d, 1)"""),
        {"i": ulid(), "m": meal.json()["meal"]["id"], "d": d["id"]})
    await db_session.commit()
    r = await client.delete(f"/dishes/{d['id']}")
    assert r.status_code == 409 and "unstar" in r.json()["detail"]
