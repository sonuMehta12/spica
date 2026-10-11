"""spec/in-progress/people.md — who you pay, and what the ledger knows.

Every number here is arithmetic over `transactions`, so the tests that matter
most are the ones that delete a row and watch the numbers correct themselves.
"""

import pytest

from tests.helpers import make_transaction, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def who(client, name: str) -> dict:
    """The one /people row with this raw_name."""
    rows = [p for p in (await client.get("/people")).json() if p["raw_name"] == name]
    assert len(rows) == 1, f"expected exactly one {name!r}, got {len(rows)}"
    return rows[0]


async def lend(client, name, amount=700000, day="2026-08-02"):
    r = await make_transaction(client, kind="lent", direction="debit", category="Udhaar",
                               description=f"{name} ko diya", amount_paise=amount,
                               local_day=day, counterparty_name=name)
    assert r.status_code == 201
    return r.json()["id"]


async def repay(client, lending, amount=700000, day="2026-08-12"):
    r = await make_transaction(client, kind="repayment", direction="credit", category="Udhaar",
                               description="wapas", amount_paise=amount, local_day=day,
                               settles_id=lending)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_a_payment_creates_the_person_unclassified(client):
    """A counterparty is born from a payment, never from a form — and nothing
    is guessed about it, because the payee name carries no signal."""
    name = f"Shop {ulid()[-5:]}"
    await make_transaction(client, amount_paise=7100, description="chai",
                           counterparty_name=name)
    row = await who(client, name)
    assert row["kind"] is None and row["source"] is None and row["confirmed_at"] is None
    assert row["sent_paise"] == 7100 and row["received_paise"] == 0 and row["tx_count"] == 1


async def test_a_settled_lending_gives_out_zero_and_the_days_it_took(client):
    name = f"Dost {ulid()[-5:]}"
    await repay(client, await lend(client, name))
    row = await who(client, name)
    assert row["still_out_paise"] == 0
    assert row["typical_days"] == 10          # 2 Aug lent, 12 Aug back
    assert row["sent_paise"] == 700000 and row["received_paise"] == 700000
    assert row["is_peer"] is True             # money came back, so: a person


async def test_an_unrepaid_lending_stays_out_with_no_average(client):
    """Unknown is not zero. Nothing has come back, so there is no gap to
    average — a 0 here would read as 'always repays instantly'."""
    name = f"Dost {ulid()[-5:]}"
    await lend(client, name, 400000, "2026-06-24")
    row = await who(client, name)
    assert row["still_out_paise"] == 400000
    assert row["typical_days"] is None


async def test_a_partial_repayment_leaves_the_remainder_out(client):
    name = f"Dost {ulid()[-5:]}"
    await repay(client, await lend(client, name, 700000), 300000)
    row = await who(client, name)
    assert row["still_out_paise"] == 400000
    assert row["typical_days"] == 10          # the clock stops at the first payment


async def test_borrowing_is_counted_the_other_way(client):
    """What you owe them is its own number. Folding it into still_out would
    net a loan against a debt and show zero for two live obligations."""
    name = f"Bhai {ulid()[-5:]}"
    r = await make_transaction(client, kind="borrowed", direction="credit", category="Udhaar",
                               description="liya", amount_paise=200000,
                               counterparty_name=name)
    assert r.status_code == 201
    row = await who(client, name)
    assert row["you_owe_paise"] == 200000 and row["still_out_paise"] == 0


async def test_deleting_a_repayment_puts_the_money_back_out(client):
    """The point of deriving: no row anywhere holds the old total, so there is
    nothing to update and nothing that can be missed."""
    name = f"Dost {ulid()[-5:]}"
    back = await repay(client, await lend(client, name))
    assert (await client.delete(f"/transactions/{back}")).status_code == 204
    row = await who(client, name)
    assert row["still_out_paise"] == 700000
    assert row["typical_days"] is None


async def test_filing_a_row_stamps_it_as_the_users_word(client):
    """The tap is what removes the `· andaaza` mark."""
    name = f"Shop {ulid()[-5:]}"
    await make_transaction(client, amount_paise=4400, counterparty_name=name)
    row = await who(client, name)
    r = await client.patch(f"/counterparties/{row['id']}",
                           json={"kind": "shop", "relation": "paan wala"})
    assert r.status_code == 200
    out = r.json()
    assert out["kind"] == "shop" and out["relation"] == "paan wala"
    assert out["source"] == "user" and out["confirmed_at"] is not None
    assert out["sent_paise"] == 4400          # the numbers come back with it


async def test_the_agents_guess_stays_marked_until_it_is_confirmed(client):
    """is_peer is the one inference the app makes on its own, and it is written
    as a guess: source='agent', unconfirmed, so the UI marks it."""
    name = f"Dost {ulid()[-5:]}"
    await repay(client, await lend(client, name, 100000), 100000)
    row = await who(client, name)
    assert row["is_peer"] is True
    assert row["confirmed_at"] is None        # nobody has said so yet


async def test_raw_name_cannot_be_patched(client):
    """It is how the next notification finds this row again."""
    name = f"Shop {ulid()[-5:]}"
    await make_transaction(client, counterparty_name=name)
    row = await who(client, name)
    r = await client.patch(f"/counterparties/{row['id']}", json={"raw_name": "something else"})
    assert r.status_code == 422


async def test_kind_filters_and_unsorted_is_the_leftovers(client):
    name = f"Shop {ulid()[-5:]}"
    await make_transaction(client, counterparty_name=name)
    row = await who(client, name)
    assert row["id"] in [p["id"] for p in (await client.get(
        "/people", params={"kind": "unsorted"})).json()]

    await client.patch(f"/counterparties/{row['id']}", json={"kind": "service"})
    unsorted = [p["id"] for p in (await client.get(
        "/people", params={"kind": "unsorted"})).json()]
    services = [p["id"] for p in (await client.get(
        "/people", params={"kind": "service"})).json()]
    assert row["id"] not in unsorted and row["id"] in services


async def test_an_unknown_kind_is_refused(client):
    name = f"Shop {ulid()[-5:]}"
    await make_transaction(client, counterparty_name=name)
    row = await who(client, name)
    assert (await client.patch(f"/counterparties/{row['id']}",
                               json={"kind": "friend"})).status_code == 422


async def test_a_missing_counterparty_is_404(client):
    assert (await client.patch("/counterparties/01TESTnope", json={"kind": "shop"})).status_code \
        == 404


# ─── adding someone the ledger has never seen ────────────────────────────────

async def test_a_person_can_be_added_before_any_money_moves(client):
    """Cash you owe, or a friend you are about to lend to. Born confirmed —
    the user typed every word, so there is nothing to mark as a guess."""
    name = f"Wasim {ulid()[-5:]}"
    r = await client.post("/counterparties", json={
        "id": ulid(), "raw_name": name, "kind": "person", "relation": "dost"})
    assert r.status_code == 201
    row = r.json()
    assert row["kind"] == "person" and row["relation"] == "dost"
    assert row["source"] == "user" and row["confirmed_at"] is not None
    assert row["tx_count"] == 0
    assert row["sent_paise"] == 0 and row["still_out_paise"] == 0
    assert row["typical_days"] is None       # unknown is not zero


async def test_the_same_name_twice_is_refused(client):
    """raw_name is the match key — two rows for one name and a notification
    cannot tell which it belongs to."""
    name = f"Twin {ulid()[-5:]}"
    first = await client.post("/counterparties", json={"id": ulid(), "raw_name": name})
    assert first.status_code == 201
    again = await client.post("/counterparties", json={"id": ulid(), "raw_name": name})
    assert again.status_code == 409


async def test_adding_the_same_id_twice_replays(client):
    """A retried request returns the stored row with 200, never a duplicate."""
    row_id, name = ulid(), f"Replay {ulid()[-5:]}"
    body = {"id": row_id, "raw_name": name, "kind": "shop"}
    assert (await client.post("/counterparties", json=body)).status_code == 201
    again = await client.post("/counterparties", json=body)
    assert again.status_code == 200 and again.json()["id"] == row_id


async def test_an_added_person_then_receives_their_payments(client):
    """The point of adding early: when money finally moves, it lands on the
    row you already filed rather than making a second one."""
    name = f"Later {ulid()[-5:]}"
    added = await client.post("/counterparties", json={
        "id": ulid(), "raw_name": name, "kind": "person"})
    cp_id = added.json()["id"]
    await make_transaction(client, amount_paise=25000, counterparty_id=cp_id,
                           description="finally paid")
    row = await who(client, name)
    assert row["id"] == cp_id and row["sent_paise"] == 25000 and row["tx_count"] == 1


async def test_a_nameless_row_is_refused(client):
    assert (await client.post("/counterparties",
                              json={"id": ulid(), "raw_name": ""})).status_code == 422

