"""spec/done/users-profile.md — the table, not the lock."""

import pytest

from tests.helpers import ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_one_user_with_a_real_id(client):
    """`me` was a placeholder that leaked into every table; the seam returns a
    real id now."""
    r = await client.get("/users/me")
    assert r.status_code == 200
    me = r.json()
    assert me["id"] != "me" and len(me["id"]) >= 20
    assert me["display_name"]


async def test_patch_a_target_and_read_it_back(client):
    r = await client.patch("/users/me", json={"savings_target_paise": 1500000})
    assert r.status_code == 200 and r.json()["savings_target_paise"] == 1500000
    assert (await client.get("/users/me")).json()["savings_target_paise"] == 1500000
    await client.patch("/users/me", json={"savings_target_paise": 1200000})


async def test_locked_fields_are_refused(client):
    """id and created_at are not in the patch schema, so they cannot be sent."""
    assert (await client.patch("/users/me", json={"id": "x"})).status_code == 422


async def test_absurd_target_is_a_422_not_a_500(client):
    """A typo like 135140 g reached the column before; bounds make it a
    refusal the editor can show."""
    r = await client.patch("/users/me", json={"protein_g_target": "135140"})
    assert r.status_code == 422


async def test_a_target_can_be_unset(client):
    """Unset is unset — the ring shows the value with no denominator, never an
    invented 2,050."""
    assert (await client.patch("/users/me", json={"fibre_g_target": None})).status_code == 200
    assert (await client.get("/users/me")).json()["fibre_g_target"] is None


async def test_deck_serves_the_whole_profile(client):
    """Targets left config.ts; the deck carries them."""
    p = (await client.get("/deck?to=2026-08-28")).json()["profile"]
    for key in ("savings_target_paise", "kcal_target", "protein_g_target", "timezone"):
        assert key in p


async def test_weigh_in_is_a_ledger_one_row_per_day(client):
    """A weight is a measurement over time; a second reading the same day is a
    correction, not a second row."""
    day = "2026-08-25"
    a = await client.post("/weigh-ins", json={"id": ulid(), "local_day": day, "weight_kg": "78.4"})
    assert a.status_code == 201
    b = await client.post("/weigh-ins", json={"id": ulid(), "local_day": day, "weight_kg": "78.1"})
    assert b.status_code == 200  # replaced, not created
    rows = [w for w in (await client.get("/weigh-ins")).json() if w["local_day"] == day]
    assert len(rows) == 1 and rows[0]["weight_kg"] == "78.1"
    await client.delete(f"/weigh-ins/{rows[0]['id']}")


async def test_memory_slug_is_the_stable_handle(client):
    """One slug, one row — the whole fix for memory scattered across apps."""
    first = await client.post("/memories", json={
        "id": ulid(), "slug": "test-fact", "kind": "reference",
        "text": "first", "source": "cortex"})
    assert first.status_code == 201 and first.json()["confirmed_at"] is None

    again = await client.post("/memories", json={
        "id": ulid(), "slug": "test-fact", "kind": "reference",
        "text": "second", "source": "user"})
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]      # same row
    assert again.json()["text"] == "second"
    # A user's own words confirm the fact; an inferred one stays marked.
    assert again.json()["confirmed_at"] is not None

    rows = [m for m in (await client.get("/memories")).json() if m["slug"] == "test-fact"]
    assert len(rows) == 1
    await client.delete(f"/memories/{rows[0]['id']}")
    assert not [m for m in (await client.get("/memories")).json() if m["slug"] == "test-fact"]
