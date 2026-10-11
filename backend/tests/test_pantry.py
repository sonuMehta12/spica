"""spec/done/pantry-view.md — the list over the ledger, in each food's unit."""

import pytest

from tests.helpers import ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def track(client, name, unit="g", staple=False):
    r = await client.post("/pantry", json={"id": ulid(), "food_name": name,
                                           "unit": unit, "staple": staple})
    assert r.status_code in (200, 201), r.text
    return r.json()


async def move(client, food_id, quantity, kind="purchase", day="2026-08-28"):
    return await client.post("/pantry-moves", json={
        "id": ulid(), "food_id": food_id, "local_day": day,
        "occurred_at": f"{day}T12:00:00+05:30", "quantity": quantity, "kind": kind})


async def row_for(client, name):
    return next(r for r in (await client.get("/pantry")).json() if r["name"] == name)


async def test_stock_is_the_sum_of_moves(client):
    """No stored counter: a counter drifts the first time a path forgets."""
    food = await track(client, "Test tofu")
    await move(client, food["food_id"], 400)
    await move(client, food["food_id"], 200)
    assert (await row_for(client, "Test tofu"))["stock_g"] == 600


async def test_a_stock_take_resets_the_count(client):
    """`opening` is an observation — I looked, there are 18 — so everything
    before it is history, not arithmetic."""
    food = await track(client, "Test eggs", unit="piece")
    await move(client, food["food_id"], 30)
    await move(client, food["food_id"], -25, kind="consumption")
    await move(client, food["food_id"], 18, kind="opening")
    row = await row_for(client, "Test eggs")
    assert row["stock_g"] == 18 and row["unit"] == "piece"


async def test_a_new_food_is_created_in_the_unit_you_pick(client):
    milk = await track(client, "Test milk", unit="ml")
    assert milk["unit"] == "ml"


async def test_a_food_with_no_inbound_move_has_no_stock_figure(client):
    """Present, amount unknowable — the read path agrees with the write path,
    which already refuses to spend an untracked food."""
    await track(client, "Test spices")
    row = await row_for(client, "Test spices")
    assert row["inbound"] == 0 and row["last_in"] is None


async def test_consumption_is_never_posted_by_hand(client):
    """POST /meals writes it, from the meal's lines. Nobody types it."""
    food = await track(client, "Test paneer")
    assert (await move(client, food["food_id"], -50, kind="consumption")).status_code == 422


async def test_consumption_cannot_be_undone_from_the_pantry(client, db_session):
    """It belongs to the meal that caused it; deleting it here would strand
    the meal. Written directly, since the API refuses to create one by hand."""
    from sqlalchemy import text
    food = await track(client, "Test khoya")
    user = (await db_session.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).scalar()
    move_id = ulid()
    await db_session.execute(text("""
        INSERT INTO pantry_moves (id, user_id, food_id, local_day, occurred_at, quantity, kind)
        VALUES (:i, :u, :f, '2026-08-28', '2026-08-28T12:00:00+05:30', -50, 'consumption')"""),
        {"i": move_id, "u": user, "f": food["food_id"]})
    await db_session.commit()
    r = await client.delete(f"/pantry-moves/{move_id}")
    assert r.status_code == 409 and "meal" in r.json()["detail"]


async def test_undoing_a_purchase_puts_the_stock_back(client):
    food = await track(client, "Test oats")
    first = await move(client, food["food_id"], 1000)
    await move(client, food["food_id"], 500)
    assert (await row_for(client, "Test oats"))["stock_g"] == 1500
    assert (await client.delete(f"/pantry-moves/{first.json()['id']}")).status_code == 204
    assert (await row_for(client, "Test oats"))["stock_g"] == 500


async def test_tracking_the_same_food_twice_is_refused(client):
    await track(client, "Test sattu")
    r = await client.post("/pantry", json={"id": ulid(), "food_name": "Test sattu"})
    assert r.status_code == 409


async def test_a_food_can_be_tracked_again_after_being_dropped(client):
    """Stop tracking soft-deletes the row, so the one-row-per-food rule has to
    ignore dead rows — Banana could not come back until it did."""
    food = await track(client, "Test kela", unit="piece")
    assert (await client.delete(f"/pantry/{food['id']}")).status_code == 204
    again = await client.post("/pantry", json={"id": ulid(), "food_name": "Test kela"})
    assert again.status_code == 201


async def test_stopping_tracking_keeps_the_moves(client, db_session):
    from sqlalchemy import text
    food = await track(client, "Test walnut")
    await move(client, food["food_id"], 100)
    await client.delete(f"/pantry/{food['id']}")
    await db_session.commit()
    left = (await db_session.execute(
        text("SELECT count(*) FROM pantry_moves WHERE food_id = :f AND deleted_at IS NULL"),
        {"f": food["food_id"]})).scalar()
    assert left == 1


async def test_settings_are_the_rows_inputs_not_a_quantity(client):
    food = await track(client, "Test curd")
    r = await client.patch(f"/pantry/{food['id']}",
                           json={"reorder_at_g": 200, "shelf_life_days": 3})
    assert r.status_code == 200 and r.json()["reorder_at_g"] == 200
    # There is no quantity field to send.
    assert (await client.patch(f"/pantry/{food['id']}", json={"stock_g": 999})).status_code == 422
