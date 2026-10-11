"""spec/done/agent-deletes.md — the agent can move a row's day, and delete a row.

Rule 6 of `agent-tools.md` used to read *a tool never deletes*. It was
overturned 2026-09-13 after the agent, having no way to do either, invented an
excuse and wrote its intentions into the ledger's `note` column. These tests
assert the capability, its guard rails, and the two habits that came out of
that failure: an id is read, never constructed, and a memory is about the
person, never about Spica.
"""

from datetime import UTC

import pytest

from tests.helpers import _msg, make_meal, make_transaction, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _user(db_session):
    from tests.helpers import the_user
    return await the_user(db_session)


# ─── moving a row to another day ─────────────────────────────────────────────

async def test_correcting_the_day_moves_the_row_and_its_clock(client, db_session):
    from app.agent import tools as T
    row = (await make_transaction(client, local_day="2026-08-20",
                                  occurred_at="2026-08-20T19:30:00+05:30")).json()
    out = await T.run(db_session, await _user(db_session), "correct_payment",
                      {"transaction_id": row["id"], "local_day": "2026-08-19"})
    assert not out.get("error"), out
    assert out["local_day"] == "2026-08-19"
    # The clock came with it, keeping the time of day. Stored UTC, so 19:30 IST
    # reads 14:00Z — the point is that it shifted exactly one day and the time
    # of day did not move.
    assert out["occurred_at"].startswith("2026-08-19") and "14:00" in out["occurred_at"]
    await db_session.commit()


async def test_a_row_either_side_of_midnight_moves_exactly_one_day(client, db_session):
    """The reason the shift is a delta and not a date stamp: past midnight IST
    the local day and the UTC date already disagree, so stamping the new local
    date onto the UTC value would move the row two days instead of one."""
    from datetime import datetime, timedelta

    from app.agent import tools as T
    row = (await make_transaction(client, local_day="2026-08-21",
                                  occurred_at="2026-08-21T00:30:00+05:30")).json()
    before = datetime.fromisoformat(row["occurred_at"])
    assert before.astimezone(UTC).date().isoformat() == "2026-08-20", "in UTC it is the 20th"
    out = await T.run(db_session, await _user(db_session), "correct_payment",
                      {"transaction_id": row["id"], "local_day": "2026-08-20"})
    assert out["local_day"] == "2026-08-20"
    # Exactly one day earlier, same instant of the clock — not two.
    assert datetime.fromisoformat(out["occurred_at"]) == before - timedelta(days=1)
    await db_session.commit()


async def test_an_explicit_time_is_not_overwritten_by_the_day_move(client, db_session):
    from app.agent import tools as T
    row = (await make_transaction(client, local_day="2026-08-20")).json()
    out = await T.run(db_session, await _user(db_session), "correct_payment",
                      {"transaction_id": row["id"], "local_day": "2026-08-18",
                       "occurred_at": "2026-08-18T07:05:00+05:30"})
    assert out["local_day"] == "2026-08-18" and "01:35" in out["occurred_at"]  # 07:05 IST
    await db_session.commit()


async def test_correcting_a_meals_day_moves_it(client, db_session):
    from app.agent import tools as T
    meal = (await make_meal(client, local_day="2026-08-20")).json()["meal"]
    out = await T.run(db_session, await _user(db_session), "correct_meal",
                      {"meal_id": meal["id"], "local_day": "2026-08-19"})
    assert not out.get("error"), out
    # patch_meal returns the meal plus the pantry moves it caused.
    assert out["meal"]["local_day"] == "2026-08-19"
    await db_session.commit()


async def test_the_model_is_offered_the_day_on_both_correction_tools(client):
    from app.agent import tools as T
    for name in ("correct_payment", "correct_meal"):
        props = T.BY_NAME[name]["schema"]["properties"]
        assert "local_day" in props, f"{name} cannot move a row to another day"


# ─── deleting ────────────────────────────────────────────────────────────────

async def test_deleting_a_payment_soft_deletes_it_and_earns_a_struck_card(client, db_session):
    from app.agent import cards as C
    from app.agent import tools as T
    row = (await make_transaction(client, description="Double entry",
                                  amount_paise=18000)).json()
    out = await T.run(db_session, await _user(db_session), "delete_payment",
                      {"transaction_id": row["id"]})
    await db_session.commit()
    assert out.get("deleted") and not out.get("error")
    [card] = C.from_tool("delete_payment", {}, out)
    assert card.state == "deleted" and card.row_id == row["id"]
    assert "Double entry" in card.lede
    # Gone from the deck, still readable by id — the card can show what went.
    deck = (await client.get("/deck", params={"to": "2026-08-28"})).json()
    assert row["id"] not in {t["id"] for t in deck["paisa"]["transactions"]}
    assert (await client.get("/transactions",
                             params={"ids": row["id"]})).json()[0]["deleted_at"]


async def test_deleting_a_meal_puts_the_food_back_on_the_shelf(client, db_session):
    from app.agent import cards as C
    from app.agent import tools as T
    user = await _user(db_session)
    food = (await client.post("/pantry", json={"id": ulid(), "food_name": "Test delete-tool tofu",
                                               "unit": "g"})).json()
    await client.post("/pantry-moves", json={
        "id": ulid(), "food_id": food["food_id"], "quantity": 500, "kind": "purchase",
        "local_day": "2026-08-20", "occurred_at": "2026-08-20T10:00:00+05:30"})
    meal = (await client.post("/meals", json={
        "id": ulid(), "occurred_at": "2026-08-20T13:00:00+05:30", "local_day": "2026-08-20",
        "meal_type": "Lunch", "dish": "Tofu plate", "kcal": 300, "protein_g": "20",
        "source": "manual",
        "items": [{"food_id": food["food_id"], "quantity": 200, "said": "tofu"}]})).json()
    def stock():
        return next(r for r in shelf if r["name"] == "Test delete-tool tofu")["stock_g"]

    shelf = (await client.get("/pantry")).json()
    spent = stock()
    assert spent == 300, "the meal should have taken 200g off the shelf"

    out = await T.run(db_session, user, "delete_meal", {"meal_id": meal["meal"]["id"]})
    await db_session.commit()
    assert out.get("deleted")
    [card] = C.from_tool("delete_meal", {}, out)
    assert card.state == "deleted" and card.source == "diet"
    shelf = (await client.get("/pantry")).json()
    assert stock() == 500, "deleting the meal must unspend its lines"


async def test_a_lending_with_repayments_refuses_and_the_refusal_is_data(client, db_session):
    """The server's rule, not the model's. It reads the refusal and explains."""
    from app.agent import tools as T
    lending = (await make_transaction(client, kind="lent", direction="debit",
                                      amount_paise=50000, description="Dost ko diya",
                                      counterparty_name="Test Dost")).json()
    await make_transaction(client, kind="repayment", direction="credit",
                           amount_paise=20000, description="Wapas aaya",
                           counterparty_name="Test Dost", settles_id=lending["id"])
    out = await T.run(db_session, await _user(db_session), "delete_payment",
                      {"transaction_id": lending["id"]})
    assert "repayment" in str(out.get("error", "")).lower()
    assert (await client.get("/transactions",
                             params={"ids": lending["id"]})).json()[0]["deleted_at"] is None


async def test_an_invented_id_is_a_refusal_not_a_crash(client, db_session):
    from app.agent import tools as T
    user = await _user(db_session)
    for name, key in (("delete_payment", "transaction_id"), ("delete_meal", "meal_id"),
                      ("correct_payment", "transaction_id"), ("correct_meal", "meal_id")):
        out = await T.run(db_session, user, name, {key: "egg-roll-180"})
        assert "no such row" in str(out.get("error", "")), (name, out)


async def test_the_same_delete_twice_in_one_turn_happens_once(client, fake):
    row = (await make_transaction(client, description="Twice")).json()
    call = ("delete_payment", {"transaction_id": row["id"]})
    fake(_msg(calls=[call, call]), _msg("delete kar diya"))
    body = (await client.post("/chat", json={"message": "isko hata do",
                                             "local_day": "2026-08-20"})).json()
    assert len([c for c in body["cards"] if c["kind"] == "confirm"]) == 1


async def test_a_delete_turn_end_to_end(client, fake):
    row = (await make_transaction(client, description="Galat entry",
                                  amount_paise=18000)).json()
    fake(_msg(calls=[("paisa_report", {"to": "2026-08-20", "fields": ["rows"]})]),
         _msg(calls=[("delete_payment", {"transaction_id": row["id"]})]),
         _msg("Galat entry ₹180 hata di."))
    body = (await client.post("/chat", json={"message": "galat entry delete kar do",
                                             "local_day": "2026-08-20"})).json()
    card = next(c for c in body["cards"] if c["kind"] == "confirm")
    assert card["state"] == "deleted" and card["row_id"] == row["id"]


# ─── memory is about the person ──────────────────────────────────────────────

async def test_remember_refuses_a_bug_report(client, db_session):
    from app.agent import tools as T
    user = await _user(db_session)
    for text in ("Money log delete currently does not work; wrong entries cannot be deleted.",
                 "Meal suggestion card is wrong.",
                 "Remember this bug about the app.",
                 "Money log delete nahi kar pa raha."):
        out = await T.run(db_session, user, "remember",
                          {"slug": "test-refused", "kind": "reference", "text_": text})
        assert "error" in out, text
        assert "repo" in out["error"]
    assert not [m for m in (await client.get("/memories")).json()
                if m["slug"] == "test-refused"]


async def test_remember_still_takes_a_fact_about_the_person(client, db_session):
    """The guard must not eat a real memory. A broken laptop screen is a fact
    about the person; only Spica's own parts are off limits."""
    from app.agent import tools as T
    out = await T.run(db_session, await _user(db_session), "remember",
                      {"slug": "test-keeps-facts", "kind": "preference",
                       "text_": "Prefers dinner before 9pm. Old laptop, screen is broken."})
    await db_session.commit()
    assert not out.get("error"), out
    assert out["slug"] == "test-keeps-facts"


# ─── commitments the agent must not lose ─────────────────────────────────────

async def test_a_payment_the_agent_logs_settles_its_commitment(client, db_session):
    """The agent's `log_payment` goes through the same route as the UI, so a
    bill paid in chat clears the commitment the same way — and the link is a
    marked guess until the user confirms it. spec/done/commitments.md."""
    from app import commitments as K
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)
    today = K.today_local()
    made = await client.post("/commitments", json={
        "id": "01TESTAGENTEMI0000000000A", "name": "Test-EMI", "category": "Test-EMI",
        "amount_paise": 1000000})
    assert made.status_code == 201, made.text

    out = await T.run(db_session, user, "log_payment", {
        "amount_paise": 1000000, "direction": "debit", "kind": "expense",
        "category": "Test-EMI", "description": "EMI payment",
        "local_day": today.isoformat()})
    await db_session.commit()
    assert not out.get("error"), out
    assert out["commitment_id"] == "01TESTAGENTEMI0000000000A"
    assert out["commitment_inferred"] is True


async def test_the_agent_can_say_a_payment_is_not_a_commitment(client, db_session):
    """The link is a guess, so it can be undone: `commitment_id: null` is *Not a
    commitment*, and the payment is ordinary spending again."""
    from app import commitments as K
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)
    today = K.today_local()
    await client.post("/commitments", json={
        "id": "01TESTAGENTSUBS000000000A", "name": "Test-Subs", "category": "Test-Subs",
        "amount_paise": 300000})
    logged = await T.run(db_session, user, "log_payment", {
        "amount_paise": 50000, "direction": "debit", "kind": "expense",
        "category": "Test-Subs", "description": "one-off top-up",
        "local_day": today.isoformat()})
    await db_session.commit()
    assert logged["commitment_id"] == "01TESTAGENTSUBS000000000A"
    out = await T.run(db_session, user, "correct_payment", {
        "transaction_id": logged["id"], "commitment_id": None})
    await db_session.commit()
    assert out["commitment_id"] is None and out["commitment_inferred"] is False
