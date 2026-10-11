"""spec/done/card-redesign.md — the server half of the fixes from the 2026-10-01
test run, each one a thing the user saw go wrong on a card.

The model is mocked where a turn is needed (tests/helpers.py). What the real
model does with the same sentences is evals/n2n_eval.py, run by hand.
"""

import pytest

from tests.helpers import _msg, make_meal, make_transaction, the_user, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")

DAY = "2026-09-10"
PAY = {"direction": "debit", "kind": "expense", "local_day": DAY}


# ─── categories ──────────────────────────────────────────────────────────────

async def test_naming_the_category_confirms_it(client, db_session):
    """After "it's transport not food" the card still asked "…, I guessed ·
    Right": the correction kept the logged 0.7."""
    from app.agent import tools as T
    user = await the_user(db_session)
    row = await T.run(db_session, user, "log_payment",
                      {**PAY, "amount_paise": 9000, "category": "Other",
                       "description": "Snacks at the station"})
    assert row["confidence"] == 0.7
    fixed = await T.run(db_session, user, "correct_payment",
                        {"transaction_id": row["id"], "category": "Khana/Grocery"})
    assert fixed["category"] == "Khana/Grocery" and fixed["confidence"] == 1.0
    await db_session.commit()


async def test_a_ride_is_transport_until_the_user_says_otherwise(client, db_session):
    """"auto 80" was filed as food."""
    from app.agent import tools as T
    user = await the_user(db_session)
    ride = await T.run(db_session, user, "log_payment",
                       {**PAY, "amount_paise": 8000, "category": "food", "description": "Auto"})
    # Still a guess — the card keeps its dot until the user confirms it.
    assert ride["category"] == "Transport" and ride["confidence"] == 0.7
    told = await T.run(db_session, user, "log_payment",
                       {**PAY, "amount_paise": 8000, "category": "food", "description": "auto",
                        "category_stated": True})
    assert told["category"] == "food" and told["confidence"] == 1.0
    parts = await T.run(db_session, user, "log_payment",
                        {**PAY, "amount_paise": 50000, "category": "Shopping",
                         "description": "auto parts"})
    assert parts["category"] == "Shopping"
    await db_session.commit()


async def test_money_going_out_is_never_income(client, db_session):
    from app.agent import tools as T
    user = await the_user(db_session)
    row = await T.run(db_session, user, "log_payment",
                      {**PAY, "amount_paise": 20000, "category": "income",
                       "description": "Gift card"})
    assert row["category"] == "Other"
    await db_session.commit()


async def test_a_loan_is_filed_as_udhaar_whatever_was_passed(client, db_session):
    """Amit's ₹4,000 udhaar was filed as "income", Rohit's as "other" — and
    the card then asked to confirm a category a loan does not have."""
    from app.agent import tools as T
    user = await the_user(db_session)
    lent = await T.run(db_session, user, "log_payment", {
        "amount_paise": 400000, "direction": "debit", "kind": "lent", "category": "income",
        "description": "Amit ko udhaar", "counterparty_name": "Amit CR", "local_day": DAY})
    assert lent["category"] == "Udhaar" and lent["confidence"] == 1.0
    back = await T.run(db_session, user, "log_payment", {
        "amount_paise": 150000, "direction": "credit", "kind": "repayment",
        "category": "Salary", "description": "Amit ne wapas diye",
        "counterparty_name": "Amit CR", "settles_id": lent["id"], "local_day": DAY})
    assert back["category"] == "Udhaar"
    # A correction cannot file a loan under anything else either.
    fixed = await T.run(db_session, user, "correct_payment",
                        {"transaction_id": lent["id"], "category": "Other"})
    assert fixed["category"] == "Udhaar"
    await db_session.commit()


# ─── the pantry ──────────────────────────────────────────────────────────────

async def test_buying_a_food_the_pantry_does_not_track_starts_tracking_it(client, db_session):
    """"200g paneer aur laya" was refused four times: "Paneer is not tracked
    in the pantry", and nothing could track it."""
    from sqlalchemy import select, text

    from app.agent import tools as T
    from app.models.diet import Food, PantryItem
    user = await the_user(db_session)
    await db_session.execute(text(
        "INSERT INTO foods (id, name, aliases, unit, created_at, updated_at) "
        "VALUES ('t-food-cr-paneer', 'Paneer (CR test)', ARRAY['cr paneer'], 'g', now(), now()) "
        "ON CONFLICT (id) DO NOTHING"))
    await db_session.commit()

    first = await T.run(db_session, user, "pantry_move", {
        "food_name": "cr paneer", "quantity": 200, "kind": "purchase", "local_day": DAY})
    assert "error" not in first and first.get("now_tracked") is True
    assert first["quantity"] == 200
    tracked = await db_session.scalar(select(PantryItem).where(
        PantryItem.user_id == user, PantryItem.food_id == "t-food-cr-paneer",
        PantryItem.deleted_at.is_(None)))
    assert tracked is not None

    again = await T.run(db_session, user, "pantry_move", {
        "food_name": "cr paneer", "quantity": 200, "kind": "purchase", "local_day": DAY})
    assert "error" not in again and "now_tracked" not in again

    # A food nobody has heard of is made, with its nutrition unknown — not zero.
    new = await T.run(db_session, user, "pantry_move", {
        "food_name": "Sattu CR", "quantity": 500, "kind": "purchase", "local_day": DAY})
    assert new.get("now_tracked") is True
    food = await db_session.scalar(select(Food).where(Food.name == "Sattu CR"))
    assert food is not None and food.kcal_100g is None and food.protein_g_100g is None

    # Waste is not the user saying a food is in the house.
    refused = await T.run(db_session, user, "pantry_move", {
        "food_name": "Never tracked CR", "quantity": 100, "kind": "waste", "local_day": DAY})
    assert "error" in refused
    await db_session.commit()


# ─── tasks ───────────────────────────────────────────────────────────────────

async def test_the_same_task_in_other_words_is_already_on_the_list(client, db_session):
    """Asked twice for the db migration tomorrow, the model titled it two ways
    and the second became a second task."""
    from app.agent import tools as T
    user = await the_user(db_session)
    a = await T.run(db_session, user, "save_task",
                    {"title": "Cardtest migration par kaam karna", "due": "2026-10-05"})
    assert a.get("added") is True
    b = await T.run(db_session, user, "save_task",
                    {"title": "Work on cardtest migration", "due": "2026-10-05"})
    assert b.get("already") is True and b["task_id"] == a["task_id"]
    c = await T.run(db_session, user, "save_task",
                    {"title": "Cardtest migration review", "due": "2026-10-05"})
    assert c.get("added") is True and c["task_id"] != a["task_id"]
    await db_session.commit()


async def test_a_task_question_sends_the_live_list(client):
    """"mere saare tasks dikhao" came back as a paragraph of bullets."""
    from app.agent import cards as C
    [card] = C.from_tool("work_report", {"status": "open", "show": True},
                         {"count": 3, "tasks": []})
    assert card.kind == "todos" and card.scope == "all" and card.project is None
    [one] = C.from_tool("work_report", {"project": "Garden", "show": True},
                        {"count": 1, "tasks": []})
    assert one.project == "Garden"
    # Read to answer a question, not to be seen: no card (2026-10-10).
    assert C.from_tool("work_report", {"status": "open"}, {"count": 3, "tasks": []}) == []
    # What got done is said in the sentence; the live list is what is owed.
    assert C.from_tool("work_report", {"status": "done"}, {"count": 2, "tasks": []}) == []


# ─── the meal card ───────────────────────────────────────────────────────────

async def test_the_meal_card_carries_carbs_and_fat_when_known(client):
    from app.agent import cards as C
    meal = {"id": "m-cr", "dish": "Rajma chawal", "meal_type": "Lunch", "kcal": 520,
            "protein_g": 18, "carbs_g": 80, "fat_g": 12, "confidence": 0.8}
    card = C.from_tool("log_meal", {}, {"meal": meal, "nutrition_known": True})[0]
    fields = {f.key: f.value for f in card.fields}
    assert fields["carbs_g"] == "80 g" and fields["fat_g"] == "12 g"
    bare = C.from_tool("log_meal", {}, {"meal": {**meal, "carbs_g": None, "fat_g": None},
                                        "nutrition_known": True})[0]
    assert not {"carbs_g", "fat_g"} & {f.key for f in bare.fields}


# ─── reads made only to check ────────────────────────────────────────────────

def _table(source):
    return {"kind": "table", "source": source, "heading": "h", "ids": ["x"]}


def _confirm(source, state="written"):
    return {"kind": "confirm", "source": source, "state": state, "row_id": "r", "lede": "l",
            "fields": []}


async def test_reads_made_only_to_check_do_not_become_cards(client):
    """One card for each thing that changed — never for what the agent read on
    the way. spec/done/chat-quality.md § What a right reply is."""
    from app.agent.cards import curate
    # A correction shows the corrected receipt only, not the day's payments.
    kept = curate([_table("paisa"), _confirm("paisa")], ["paisa_report", "correct_payment"])
    assert [c["kind"] for c in kept] == ["confirm"]
    # A meal's turn shows neither table.
    meal = curate([_table("paisa"), _table("diet"), _confirm("diet")],
                  ["paisa_report", "diet_report", "correct_meal"])
    assert [(c["kind"], c["source"]) for c in meal] == [("confirm", "diet")]
    # A new task is its own card, not the To-do list read on the way.
    task = curate([{"kind": "todos", "scope": "all", "project": None}, _confirm("work")],
                  ["work_report", "save_task"])
    assert [c["kind"] for c in task] == ["confirm"]
    # A review question read in passing is not a card; the categoriser's is.
    assert curate([_confirm("paisa", "proposed")], ["paisa_report"]) == []
    # A suggestion turn shows no table at all.
    assert curate([_table("diet")], ["diet_report", "suggest_dishes"]) == []
    # A turn that only read keeps what was asked for — proposals are not writes.
    assert len(curate([_table("paisa"), _confirm("paisa", "proposed")],
                      ["categorise_now"])) == 2
    # One task list, however many times the tasks were read.
    two = curate([{"kind": "todos", "scope": "all", "project": None}] * 2, ["work_report"] * 2)
    assert len(two) == 1


async def test_a_meal_turn_drops_the_money_table(client, fake):
    """The turn the user saw: a meal fixed, a paisa table nobody asked for."""
    await make_transaction(client, local_day="2026-09-11", description="CR chai")
    fake(_msg(calls=[("paisa_report", {"from": "2026-09-11", "to": "2026-09-11",
                                       "fields": ["rows"]}),
                     ("log_meal", {"text_said": "cr khichdi", "meal_type": "Lunch",
                                   "local_day": "2026-09-11"})]),
         _msg("Lunch log ho gaya."))
    body = (await client.post("/chat", json={"message": "lunch mein khichdi",
                                             "local_day": "2026-09-11"})).json()
    kinds = [(c["kind"], c.get("source")) for c in body["cards"]]
    assert ("confirm", "diet") in kinds and not any(k == "table" for k, _ in kinds)


# ─── undo a delete ───────────────────────────────────────────────────────────

async def test_a_deleted_payment_can_be_restored(client):
    row = (await make_transaction(client, description="CR restore me")).json()
    assert (await client.delete(f"/transactions/{row['id']}")).status_code == 204
    back = await client.post(f"/transactions/{row['id']}/restore")
    assert back.status_code == 200 and back.json()["id"] == row["id"]
    # Live again, so there is nothing left to restore.
    assert (await client.post(f"/transactions/{row['id']}/restore")).status_code == 404
    assert (await client.post(f"/transactions/{ulid()}/restore")).status_code == 404


async def test_a_repayment_cannot_come_back_without_its_lending(client):
    lent = (await make_transaction(client, kind="lent", category="Udhaar",
                                   description="CR lent", counterparty_name="Sonu CR")).json()
    back = (await make_transaction(client, kind="repayment", direction="credit",
                                   category="Udhaar", description="CR repaid",
                                   counterparty_name="Sonu CR", settles_id=lent["id"],
                                   amount_paise=5000)).json()
    assert (await client.delete(f"/transactions/{back['id']}")).status_code == 204
    assert (await client.delete(f"/transactions/{lent['id']}")).status_code == 204
    r = await client.post(f"/transactions/{back['id']}/restore")
    assert r.status_code == 409


async def test_a_deleted_meal_can_be_restored(client):
    meal = (await make_meal(client, dish="CR restore meal")).json()["meal"]
    assert (await client.delete(f"/meals/{meal['id']}")).status_code == 204
    back = await client.post(f"/meals/{meal['id']}/restore")
    assert back.status_code == 200 and back.json()["meal"]["id"] == meal["id"]
    assert (await client.post(f"/meals/{meal['id']}/restore")).status_code == 404


# ─── the categories the model may use ────────────────────────────────────────

async def test_a_new_ledger_is_offered_the_default_categories(client, db_session):
    from app.agent import prompt as P
    user = await the_user(db_session)
    system = await P.build(db_session, user)
    line = system.split("## The categories this ledger uses\n", 1)[1].split("\n", 1)[0]
    names = [c.strip() for c in line.split(",")]
    assert "Transport" in names and "Udhaar" in names
    # A name the ledger already uses is never offered twice.
    assert len(names) == len({n.casefold() for n in names})
