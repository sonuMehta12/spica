"""PUT /days/{local_day} — sleep, weight, log-complete, upserted by day.

The one write route the agent tools needed that did not exist.
spec/in-progress/agent-tools.md § log_day.
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

DAY = "2026-04-07"


async def test_a_day_is_created_then_merged_not_duplicated(client):
    r1 = await client.put(f"/days/{DAY}", json={"sleep_hours": 6.5})
    assert r1.status_code == 200 and r1.json()["sleep_hours"] == 6.5
    r2 = await client.put(f"/days/{DAY}", json={"weight_kg": 78.2})
    assert r2.status_code == 200
    assert r2.json()["id"] == r1.json()["id"]                 # same row
    assert r2.json()["sleep_hours"] == 6.5 and r2.json()["weight_kg"] == 78.2  # merged


async def test_a_field_left_out_is_left_alone_and_null_clears(client):
    await client.put("/days/2026-04-08", json={"sleep_hours": 7, "note": "late"})
    r = await client.put("/days/2026-04-08", json={"note": None})
    assert r.json()["sleep_hours"] == 7 and r.json()["note"] is None


async def test_impossible_values_are_refused(client):
    assert (await client.put(f"/days/{DAY}", json={"sleep_hours": 25})).status_code == 422
    assert (await client.put(f"/days/{DAY}", json={"weight_kg": 0})).status_code == 422
    # an unknown field is a 422, not silently dropped
    assert (await client.put(f"/days/{DAY}", json={"steps": 8000})).status_code == 422


async def test_the_deck_carries_the_day(client):
    await client.put("/days/2026-04-09", json={"sleep_hours": 8})
    d = (await client.get("/deck", params={"from": "2026-04-09", "to": "2026-04-09"})).json()
    assert any(x["local_day"] == "2026-04-09" and x["sleep_hours"] == 8 for x in d["diet"]["days"])
