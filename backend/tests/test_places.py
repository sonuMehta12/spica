"""spec/in-progress/places.md — where the money was spent.

A place has a ledger under it, unlike the exercise library, so every number on
a pin is a query. The tests that matter most delete a payment and watch the pin
correct itself.
"""

import pytest

from tests.helpers import make_transaction, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")

# Connaught Place, near enough.
LAT, LNG = 28.6315, 77.2167


async def a_place(client, name=None, **over):
    body = {"id": ulid(), "name": name or f"Place {ulid()[-5:]}",
            "lat": LAT, "lng": LNG, "kind": "shop"}
    body.update(over)
    r = await client.post("/places", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def one(client, place_id):
    rows = [p for p in (await client.get("/places")).json() if p["id"] == place_id]
    assert len(rows) == 1
    return rows[0]


# ─── a pin you dropped ───────────────────────────────────────────────────────

async def test_a_dropped_pin_is_confirmed_and_empty(client):
    """You put it there, so there is nothing to mark as a guess — and nothing
    has been spent there until a payment says so."""
    row = await a_place(client, "Ghar", kind="home", source="manual")
    assert row["source"] == "manual" and row["confirmed_at"] is not None
    assert row["payments"] == 0 and row["spent_paise"] == 0
    assert row["last_seen"] is None
    assert row["radius_m"] == 50          # a paan shop default, editable


async def test_a_detected_pin_waits_to_be_confirmed(client):
    """The agent's guess shows `· andaaza` until the user says otherwise."""
    row = await a_place(client, source="detected")
    assert row["confirmed_at"] is None

    named = await client.patch(f"/places/{row['id']}", json={"name": "Chilla Dallupura"})
    assert named.json()["confirmed_at"] is not None   # any edit is the user speaking


async def test_the_radius_is_the_places_own(client):
    """A paan shop is ~20m and a mall ~200m; one threshold would be wrong for
    both, which is why it is a column."""
    small = await a_place(client, radius_m=20)
    big = await a_place(client, radius_m=200)
    assert small["radius_m"] == 20 and big["radius_m"] == 200
    bad = await client.post("/places", json={
        "id": ulid(), "name": "Nowhere", "lat": LAT, "lng": LNG, "radius_m": 0})
    assert bad.status_code == 422


async def test_coordinates_have_to_be_real(client):
    r = await client.post("/places", json={
        "id": ulid(), "name": "Off the map", "lat": 91, "lng": LNG})
    assert r.status_code == 422


async def test_an_unknown_kind_is_refused(client):
    r = await client.post("/places", json={
        "id": ulid(), "name": "X", "lat": LAT, "lng": LNG, "kind": "wishlist"})
    assert r.status_code == 422


# ─── what the ledger says about it ───────────────────────────────────────────

async def test_placing_a_payment_counts_it(client):
    place = await a_place(client)
    tx = await make_transaction(client, amount_paise=7100, description="chai")
    assert (await client.patch(f"/transactions/{tx.json()['id']}",
                               json={"place_id": place["id"]})).status_code == 200
    row = await one(client, place["id"])
    assert row["payments"] == 1 and row["spent_paise"] == 7100
    assert row["last_seen"] == "2026-08-20"


async def test_a_pin_linked_to_a_counterparty_shows_its_spend_untagged(client):
    """The point of the link: nothing at Mohan Lal's shop is tagged by hand,
    and the pin still knows what was spent there."""
    name = f"Shyam {ulid()[-5:]}"
    await make_transaction(client, amount_paise=4400, counterparty_name=name)
    await make_transaction(client, amount_paise=6000, counterparty_name=name)
    who = next(p for p in (await client.get("/people")).json() if p["raw_name"] == name)

    place = await a_place(client, f"{name} ki dukaan", counterparty_id=who["id"])
    row = await one(client, place["id"])
    assert row["payments"] == 2 and row["spent_paise"] == 10400
    assert row["counterparty_name"] == name


async def test_deleting_a_payment_takes_it_off_the_pin(client):
    """Nothing stores the total, so there is nothing to update."""
    place = await a_place(client)
    tx = await make_transaction(client, amount_paise=5000)
    await client.patch(f"/transactions/{tx.json()['id']}", json={"place_id": place["id"]})
    assert (await client.delete(f"/transactions/{tx.json()['id']}")).status_code == 204
    row = await one(client, place["id"])
    assert row["payments"] == 0 and row["spent_paise"] == 0 and row["last_seen"] is None


async def test_a_credit_is_counted_as_a_visit_but_not_as_spend(client):
    """Money coming back at a place is still a payment there; it is not spend."""
    place = await a_place(client)
    tx = await make_transaction(client, direction="credit", kind="income",
                                amount_paise=9000, description="refund")
    await client.patch(f"/transactions/{tx.json()['id']}", json={"place_id": place["id"]})
    row = await one(client, place["id"])
    assert row["payments"] == 1 and row["spent_paise"] == 0


# ─── the fix on the payment ──────────────────────────────────────────────────

async def test_a_payment_can_carry_where_the_phone_was(client):
    """It used to belong in `predictions.signals`, which lost it whenever the
    agent had not guessed — and those are the fixes that discover a place."""
    r = await make_transaction(client, lat=LAT, lng=LNG, fix_accuracy_m=12.5)
    assert r.status_code == 201


async def test_half_a_coordinate_is_not_a_location(client):
    """Refused as a 422 with a sentence, not as a check-constraint stack trace
    — the database says so too, but only as a backstop."""
    r = await make_transaction(client, lat=LAT)
    assert r.status_code == 422 and "lat and lng" in r.text


async def test_the_match_is_redoable_but_the_fix_is_not_editable(client):
    """Clearing `place_id` is the redo; the reading itself is not a decision."""
    place = await a_place(client)
    tx = (await make_transaction(client, lat=LAT, lng=LNG, fix_accuracy_m=8)).json()
    await client.patch(f"/transactions/{tx['id']}", json={"place_id": place["id"]})
    cleared = await client.patch(f"/transactions/{tx['id']}", json={"place_id": None})
    assert cleared.status_code == 200 and cleared.json()["place_id"] is None
    assert (await client.patch(f"/transactions/{tx['id']}", json={"lat": 0})).status_code == 422


# ─── lifecycle ───────────────────────────────────────────────────────────────

async def test_linking_an_unknown_counterparty_is_refused(client):
    r = await client.post("/places", json={
        "id": ulid(), "name": "X", "lat": LAT, "lng": LNG, "counterparty_id": "01TESTnope"})
    assert r.status_code == 422


async def test_deleting_a_pin_leaves_the_payment_alone(client):
    """That the money moved there is still true; the pin just stops being one
    of yours."""
    place = await a_place(client)
    tx = (await make_transaction(client)).json()
    await client.patch(f"/transactions/{tx['id']}", json={"place_id": place["id"]})
    assert (await client.delete(f"/places/{place['id']}")).status_code == 204
    assert place["id"] not in [p["id"] for p in (await client.get("/places")).json()]
    kept = await client.patch(f"/transactions/{tx['id']}", json={"note": "still here"})
    assert kept.json()["place_id"] == place["id"]


async def test_kind_filters(client):
    home = await a_place(client, kind="home")
    shop = await a_place(client, kind="shop")
    found = [p["id"] for p in (await client.get("/places", params={"kind": "home"})).json()]
    assert home["id"] in found and shop["id"] not in found


async def test_a_replayed_post_does_not_duplicate(client):
    body = {"id": ulid(), "name": f"Replay {ulid()[-5:]}", "lat": LAT, "lng": LNG}
    assert (await client.post("/places", json=body)).status_code == 201
    again = await client.post("/places", json=body)
    assert again.status_code == 200 and again.json()["id"] == body["id"]
    assert [p["id"] for p in (await client.get("/places")).json()].count(body["id"]) == 1
