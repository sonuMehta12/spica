"""spec/done/deck-api.md — every row the three cards need, in one call."""

import pytest

from tests.helpers import make_meal, make_transaction

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_one_call_carries_all_three_modes(client):
    """Swiping between cards must never show a loading state."""
    d = (await client.get("/deck?to=2026-08-28")).json()
    assert set(d) >= {"from", "to", "profile", "paisa", "diet", "work"}
    assert set(d["diet"]) >= {"meals", "habits", "habit_logs", "days"}
    assert set(d["work"]) >= {"projects", "tasks"}


async def test_rows_never_totals(client):
    """The client computes every number it shows; two places for the same
    arithmetic is one place too many."""
    d = (await client.get("/deck?to=2026-08-28")).json()
    assert isinstance(d["paisa"]["transactions"], list)
    assert not any(k in d["paisa"] for k in ("total", "spent", "limit"))


async def test_the_window_is_the_users_local_dates(client):
    """Only the client knows what day it is where the user is — a server
    deciding 'today' puts an 11:30pm chai on the wrong day."""
    await make_transaction(client, description="In window", local_day="2026-08-20")
    await make_transaction(client, description="Out of window", local_day="2026-09-15",
                           occurred_at="2026-09-15T12:00:00+05:30")
    days = {t["local_day"] for t in
            (await client.get("/deck?to=2026-08-28")).json()["paisa"]["transactions"]}
    assert "2026-08-20" in days and "2026-09-15" not in days


async def test_the_month_arc_survives_a_one_day_range(client):
    """Each mode's window is unioned with what its card structurally needs, so
    a one-day range never blanks the month arc."""
    d = (await client.get("/deck?from=2026-08-28&to=2026-08-28")).json()
    days = {t["local_day"] for t in d["paisa"]["transactions"]}
    assert any(day < "2026-08-28" for day in days)


async def test_a_deleted_row_leaves_the_deck(client):
    r = await make_meal(client, dish="Deck delete test")
    mid = r.json()["meal"]["id"]
    before = {m["id"] for m in (await client.get("/deck?to=2026-08-28")).json()["diet"]["meals"]}
    assert mid in before
    await client.delete(f"/meals/{mid}")
    after = {m["id"] for m in (await client.get("/deck?to=2026-08-28")).json()["diet"]["meals"]}
    assert mid not in after


async def test_from_is_serialised_as_from(client):
    """`from` is a Python keyword; the field is from_ and must not leak."""
    d = (await client.get("/deck?from=2026-08-01&to=2026-08-28")).json()
    assert d["from"] == "2026-08-01" and "from_" not in d
