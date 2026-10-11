"""spec/done/ledger-writes.md — POST creates, PATCH fixes, DELETE soft-deletes."""

import pytest

from tests.helpers import make_meal, make_transaction, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_post_is_a_replay_not_an_edit(client):
    """The client supplies the id, so a retry returns the stored row and
    ignores the body — a retry is a retry."""
    tid = ulid()
    first = await make_transaction(client, id=tid, amount_paise=5000)
    assert first.status_code == 201

    again = await make_transaction(client, id=tid, amount_paise=999999)
    assert again.status_code == 200
    assert again.json()["amount_paise"] == 5000  # body ignored


async def test_patch_only_touches_what_was_sent(client):
    r = await make_transaction(client, description="Chai", amount_paise=4000)
    tid = r.json()["id"]
    patched = await client.patch(f"/transactions/{tid}", json={"description": "Chai + samosa"})
    assert patched.status_code == 200
    assert patched.json()["description"] == "Chai + samosa"
    assert patched.json()["amount_paise"] == 4000  # untouched


async def test_patch_refuses_unknown_fields(client):
    r = await make_transaction(client)
    assert (await client.patch(f"/transactions/{r.json()['id']}",
                               json={"nonsense": 1})).status_code == 422


async def test_delete_is_soft_and_then_404(client, db_session):
    from sqlalchemy import text
    r = await make_transaction(client)
    tid = r.json()["id"]
    assert (await client.delete(f"/transactions/{tid}")).status_code == 204
    # Gone from the API…
    assert (await client.patch(f"/transactions/{tid}", json={"description": "x"})).status_code == 404
    # …but still a row, with a stamp. Sync needs the tombstone.
    kept = (await db_session.execute(
        text("SELECT deleted_at FROM transactions WHERE id = :i"), {"i": tid})).scalar()
    assert kept is not None


async def test_a_meal_returns_the_pantry_moves_it_caused(client):
    """The card shows stock dropping without a refetch, so the write says what
    it spent."""
    r = await make_meal(client)
    assert r.status_code == 201
    assert "meal" in r.json() and "pantry_moves" in r.json()


async def test_carbs_and_fat_may_be_unknown(client):
    """The composer knows kcal and protein for a chip but not fat. Unknown
    stays null — a 0 would be a fabricated number."""
    r = await make_meal(client, dish="Chai")
    assert r.status_code == 201
    meal = r.json()["meal"]
    assert meal["carbs_g"] is None and meal["fat_g"] is None


async def test_a_write_never_takes_user_id_from_the_body(client, db_session):
    from sqlalchemy import text
    r = await make_transaction(client, description="Not yours")
    assert r.status_code == 201
    owner = (await db_session.execute(
        text("SELECT user_id FROM transactions WHERE id = :i"), {"i": r.json()["id"]})).scalar()
    real = (await db_session.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).scalar()
    assert owner == real


async def test_a_payee_matches_whatever_the_case(client, db_session):
    """UPI renders "MOHAN LAL"; a person — or the agent — types "Mohan
    Shyam". One shop, one row. An exact match made two on 2026-09-12."""
    from sqlalchemy import text
    loud = f"MOHD {ulid()[-5:]}".upper()
    await make_transaction(client, counterparty_name=loud, description="first")
    await make_transaction(client, counterparty_name=loud.title(), description="second")
    n = (await db_session.execute(
        text("SELECT count(*) FROM counterparties WHERE lower(raw_name) = :n"),
        {"n": loud.lower()})).scalar()
    assert n == 1
