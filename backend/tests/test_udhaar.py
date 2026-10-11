"""spec/done/udhaar-repayment.md and udhaar-borrowed.md — money out, money back."""

import pytest

from tests.helpers import make_transaction, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def lend(client, amount=400000, name="Dost test"):
    r = await make_transaction(client, kind="lent", direction="debit", category="Udhaar",
                               description=f"{name} ko diya", amount_paise=amount,
                               counterparty_name=name)
    assert r.status_code == 201
    return r.json()["id"]


async def test_a_repayment_needs_a_live_lending(client):
    r = await make_transaction(client, kind="repayment", direction="credit",
                               category="Udhaar", description="from nobody")
    assert r.status_code == 409 and "settles_id" in r.json()["detail"]


async def test_repaying_more_than_is_out_is_refused_with_the_amount(client):
    lending = await lend(client, 400000)
    r = await make_transaction(client, kind="repayment", direction="credit", category="Udhaar",
                               description="too much", amount_paise=500000, settles_id=lending)
    assert r.status_code == 409 and "4,000" in r.json()["detail"]


async def test_a_partial_repayment_leaves_the_rest_out(client):
    lending = await lend(client, 400000)
    part = await make_transaction(client, kind="repayment", direction="credit", category="Udhaar",
                                  description="half", amount_paise=150000, settles_id=lending)
    assert part.status_code == 201
    # The remainder is still owed, so another 250000 is fine and 250001 is not.
    over = await make_transaction(client, kind="repayment", direction="credit", category="Udhaar",
                                  description="over", amount_paise=250001, settles_id=lending)
    assert over.status_code == 409


async def test_the_direction_must_match_what_is_being_settled(client):
    """A credit pays back a lending; a debit pays back a borrowing."""
    lending = await lend(client)
    r = await make_transaction(client, kind="repayment", direction="debit", category="Udhaar",
                               description="wrong way", amount_paise=1000, settles_id=lending)
    assert r.status_code == 409 and "credit" in r.json()["detail"]


async def test_money_coming_back_makes_the_person_a_peer(client, db_session):
    """is_peer flips the first time money comes back, and never flips back —
    shops take money, people also return it."""
    from sqlalchemy import text
    name = f"Peer test {ulid()[-4:]}"
    lending = await lend(client, 100000, name)
    before = (await db_session.execute(
        text("SELECT is_peer FROM counterparties WHERE raw_name = :n"), {"n": name})).scalar()
    assert before is False

    await make_transaction(client, kind="repayment", direction="credit", category="Udhaar",
                           description="back", amount_paise=100000, settles_id=lending)
    await db_session.commit()  # see the other session's write
    after = (await db_session.execute(
        text("SELECT is_peer FROM counterparties WHERE raw_name = :n"), {"n": name})).scalar()
    assert after is True


async def test_borrowing_makes_them_a_peer_immediately(client, db_session):
    """Someone who lent you money is a peer from the first row."""
    from sqlalchemy import text
    name = f"Lender test {ulid()[-4:]}"
    r = await make_transaction(client, kind="borrowed", direction="credit", category="Udhaar",
                               description=f"{name} se liya", counterparty_name=name)
    assert r.status_code == 201
    await db_session.commit()
    assert (await db_session.execute(
        text("SELECT is_peer FROM counterparties WHERE raw_name = :n"), {"n": name})).scalar() is True


async def test_deleting_a_lending_with_repayments_is_refused(client):
    """A cascade would be convenient and invisible; a refusal is one tap more
    and never surprises."""
    lending = await lend(client, 200000)
    await make_transaction(client, kind="repayment", direction="credit", category="Udhaar",
                           description="back", amount_paise=100000, settles_id=lending)
    r = await client.delete(f"/transactions/{lending}")
    assert r.status_code == 409 and "undo" in r.json()["detail"].lower()


async def test_undoing_the_repayment_frees_the_lending(client):
    lending = await lend(client, 200000)
    rep = await make_transaction(client, kind="repayment", direction="credit", category="Udhaar",
                                 description="back", amount_paise=200000, settles_id=lending)
    assert (await client.delete(f"/transactions/{rep.json()['id']}")).status_code == 204
    assert (await client.delete(f"/transactions/{lending}")).status_code == 204


async def test_a_lending_or_borrowing_must_name_a_person(client):
    """The server owns the rule: a lent or borrowed row without a counterparty
    is refused for every caller, the UI and the agent alike."""
    for kind, direction in (("lent", "debit"), ("borrowed", "credit")):
        r = await make_transaction(client, kind=kind, direction=direction, category="Udhaar",
                                   description="kisko?")
        assert r.status_code == 422 and "who" in r.json()["detail"]


async def test_a_settles_id_that_points_nowhere_is_refused_not_a_crash(client):
    """`settle()` validated this properly but ran after the row was in the
    session, and `person()` autoflushes before it — so a stale id hit the
    foreign key first and came back a 500. The agent, handed an id it
    remembered from a deleted lending, showed "Didn't reach the server"."""
    r = await client.post("/transactions", json={
        "id": ulid(), "occurred_at": "2026-08-20T12:00:00+05:30",
        "local_day": "2026-08-20", "amount_paise": 100000, "direction": "credit",
        "kind": "repayment", "category": "Udhaar", "description": "wapas aaya",
        "counterparty_name": "Ghost", "source": "manual",
        "settles_id": "01NOSUCHROWNOSUCHROWNOSUCH"})
    assert r.status_code == 422, r.status_code
    assert "no live row" in r.json()["detail"]


async def test_settles_id_must_point_at_a_lending_not_any_row(client):
    spend = (await make_transaction(client, description="Chai")).json()
    r = await client.post("/transactions", json={
        "id": ulid(), "occurred_at": "2026-08-20T12:00:00+05:30",
        "local_day": "2026-08-20", "amount_paise": 1000, "direction": "credit",
        "kind": "repayment", "category": "Udhaar", "description": "wapas",
        "counterparty_name": "Ghost", "source": "manual", "settles_id": spend["id"]})
    assert r.status_code == 422
    assert "not a lending" in r.json()["detail"]


async def test_the_agent_reads_the_refusal_instead_of_crashing(client, db_session):
    """Whatever the route refuses must reach the model as data. Before this a
    constraint violation escaped `T.run` entirely."""
    from app.agent import tools as T
    from tests.helpers import the_user
    out = await T.run(db_session, await the_user(db_session), "log_payment", {
        "amount_paise": 100000, "direction": "credit", "kind": "repayment",
        "category": "Udhaar", "description": "wapas", "counterparty_name": "Ghost",
        "local_day": "2026-08-20", "settles_id": "01NOSUCHROWNOSUCHROWNOSUCH"})
    assert "error" in out and "no live row" in out["error"]
