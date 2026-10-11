"""spec/chat-cards.md — what the agent's replies look like on the wire.

The model is mocked (see test_agent.py). What is ours to test: that every write
earns a card and every card's copy is English; that a rows read returns a table
of ids with a number-first heading; that dishes named in the prose become a
suggest card carrying the dish's display fields; that a guessed category is
below full confidence until confirmed; and that rows can be read back by id,
deleted ones included.
"""

import pytest

from tests.helpers import _msg, make_meal, make_transaction, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")

HINGLISH = ("andaaza", "bacha", "kar diya", "nahi")


def _english(card: dict) -> None:
    text = " ".join([card["lede"], *(f["label"] + " " + f["value"] for f in card["fields"])])
    assert not any(w in text.lower() for w in HINGLISH), text


# ─── the ledger card ─────────────────────────────────────────────────────────

async def test_a_rows_read_returns_a_table_of_ids_with_a_number_first(client, fake):
    a = (await make_transaction(client, local_day="2026-07-03", amount_paise=12000)).json()["id"]
    b = (await make_transaction(client, local_day="2026-07-04", amount_paise=8000)).json()["id"]
    fake(_msg(calls=[("paisa_report", {"from": "2026-07-03", "to": "2026-07-04",
                                       "fields": ["rows", "spent"], "show": True})]),
         _msg("do payments the"))
    body = (await client.post("/chat", json={"message": "3-4 july ke payments?",
                                             "local_day": "2026-08-20"})).json()
    table = next(c for c in body["cards"] if c["kind"] == "table")
    assert table["source"] == "paisa" and {a, b} <= set(table["ids"])
    assert table["heading"] == "₹200 out · 2 payments · 2 days"


async def test_a_page_of_rows_says_it_is_a_page(client, fake):
    from app.agent import cards as C
    rows = [{"id": f"r{i}", "amount_paise": 1000, "direction": "debit", "kind": "expense"}
            for i in range(3)]
    [card] = C.from_tool("paisa_report", {"to": "2026-08-28", "show": True},
                         {"rows": rows, "total_matching": 94, "days_in_range": 28})
    # The rupees are what the three rows add up to, not the month's total.
    assert card.heading == "₹30 out · 3 of 94 payments · 28 days"


async def test_money_coming_in_is_counted_apart_from_spending(client):
    """A salary is not a payment. Summed with the spending it gave a heading
    that matched nothing on the card, and the row itself was drawn −red."""
    from app.agent import cards as C
    rows = [
        {"id": "a", "amount_paise": 65100, "direction": "debit", "kind": "expense"},
        {"id": "b", "amount_paise": 4000000, "direction": "credit", "kind": "income"},
        {"id": "c", "amount_paise": 200000, "direction": "credit", "kind": "repayment"},
    ]
    [card] = C.from_tool("paisa_report", {"to": "2026-09-13", "show": True},
                         {"rows": rows, "days_in_range": 13})
    assert card.heading == "₹651 out, ₹42,000 in · 3 rows · 13 days"


async def test_a_totals_only_read_returns_no_table(client, fake):
    fake(_msg(calls=[("paisa_report", {"to": "2026-08-20", "fields": ["spent"]})]),
         _msg("₹0"))
    body = (await client.post("/chat", json={"message": "kitna?",
                                             "local_day": "2026-08-20"})).json()
    assert [c["kind"] for c in body["cards"]] == ["agent"]


# ─── confidence ──────────────────────────────────────────────────────────────

async def test_a_category_is_a_guess_until_the_user_names_it(client, db_session):
    from app.agent import cards as C
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)
    base = {"amount_paise": 4400, "direction": "debit", "kind": "expense",
            "category": "Other", "description": "chai", "local_day": "2026-08-20"}

    guessed = await T.run(db_session, user, "log_payment", base)
    assert guessed["confidence"] == 0.7
    card = C.from_tool("log_payment", base, guessed)[0]
    assert next(f for f in card.fields if f.key == "category").guessed

    stated = await T.run(db_session, user, "log_payment", {**base, "category_stated": True})
    assert stated["confidence"] == 1.0
    card = C.from_tool("log_payment", base, stated)[0]
    assert not next(f for f in card.fields if f.key == "category").guessed
    await db_session.commit()


async def test_confirm_raises_confidence_to_one(client):
    row = (await make_transaction(client, confidence=0.7)).json()
    assert row["confidence"] == 0.7
    r = await client.patch(f"/transactions/{row['id']}", json={"confidence": 1})
    assert r.status_code == 200 and r.json()["confidence"] == 1.0


# ─── every write earns a card ────────────────────────────────────────────────

async def test_every_write_earns_an_english_confirm_card(client, db_session):
    from app.agent import cards as C
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)
    tx = (await make_transaction(client, description="Swiggy", amount_paise=35000)).json()

    calls = [
        ("correct_payment", {"transaction_id": tx["id"], "category": "Khana/Grocery"}, "paisa"),
        ("log_day", {"local_day": "2026-08-20", "sleep_hours": 6.5, "weight_kg": 71.2}, "body"),
        ("keep_dish", {"name": "Test paneer bhurji", "protein_g": 32, "kcal": 410}, "diet"),
        ("file_person", {"raw_name": "Test Mohan", "kind": "person", "relation": "friend"},
         "people"),
        ("save_place", {"name": "Test Tokai", "lat": 28.55, "lng": 77.19, "kind": "eat"},
         "places"),
        ("remember", {"slug": "test-veg", "kind": "preference", "text_": "veg on Tuesdays"},
         "memory"),
        ("update_profile", {"field": "protein_g_target", "value": 140}, "profile"),
    ]
    for name, args, source in calls:
        result = await T.run(db_session, user, name, args)
        assert not result.get("error"), (name, result)
        cards = C.from_tool(name, args, result)
        # log_day's weight is a weigh-in — a write of its own, with its own card
        # (spec/done/onboarding-goals.md § Data).
        assert len(cards) == (2 if name == "log_day" else 1), name
        for card in (c.model_dump() for c in cards):
            assert card["kind"] == "confirm" and card["source"] == source and card["lede"], name
            _english(card)
    await db_session.commit()


async def test_the_day_card_leads_with_the_numbers(client):
    from app.agent import cards as C
    day, weight = C.from_tool("log_day", {}, {
        "day": {"id": "d1", "sleep_hours": 6.5, "weight_kg": 71.2},
        "weigh_in": {"id": "w1", "weight_kg": 71.2, "estimated": False},
        "habits": [{"habit": "Workout", "logged": True}]})
    assert day.lede == "6 h 30 m sleep · 1 habit"
    assert [f.label for f in day.fields] == ["Sleep", "Workout"]
    # The weight holds its weigh-in, so Undo and a delete on Profile both reach it.
    assert (weight.row_id, weight.lede, [f.label for f in weight.fields]) == \
        ("w1", "71.2 kg", ["Weight"])
    assert C.from_tool("log_day", {}, {"nothing": "no facts given"}) == []


async def test_the_pantry_card_leads_with_what_is_left(client):
    from app.agent import cards as C
    [card] = C.from_tool("pantry_move", {}, {"id": "m1", "food": "Paneer", "unit": "g",
                                             "quantity": 200, "kind": "purchase",
                                             "food_id": "f1", "_stock_after": 700})
    assert card.source == "pantry" and card.lede == "700 g Paneer left"
    assert next(f for f in card.fields if f.key == "kind").value == "bought"


async def test_the_profile_card_formats_the_unit(client):
    from app.agent import cards as C
    assert C.from_tool("update_profile", {}, {"protein_g_target": 140})[0].lede \
        == "Protein target → 140 g"
    assert C.from_tool("update_profile", {}, {"savings_target_paise": 1500000})[0].lede \
        == "Savings target → ₹15,000"
    assert C.from_tool("update_profile", {}, {"sleep_target_min": 450})[0].lede \
        == "Sleep target → 7 h 30 m"


async def test_a_tool_error_earns_no_card(client):
    from app.agent import cards as C
    assert C.from_tool("log_payment", {}, {"error": "refused"}) == []
    assert C.from_tool("paisa_report", {"to": "2026-08-20"}, {"error": "x"}) == []


# ─── suggestions, matched from the prose ─────────────────────────────────────

CANDS = [
    {"dish_id": "a", "name": "Paneer bhurji", "aliases": [], "protein_g": 32, "kcal": 410,
     "minutes": 15, "meal_type": "Dinner", "cookable_now": False, "missing": ["capsicum"],
     "image_url": None, "saved": False, "tried": 0},
    {"dish_id": "b", "name": "Whey shake", "aliases": ["protein shake"], "protein_g": 24,
     "kcal": 120, "cookable_now": True, "missing": [], "saved": True, "tried": 3},
    {"dish_id": "c", "name": "Dal chawal", "aliases": [], "protein_g": 18, "kcal": 520},
]


async def test_dishes_named_in_the_prose_become_a_card_first_two_in_order(client):
    from app.agent import cards as C
    [card] = C.suggest_from_text(
        "Aaj **protein shake** lo, ya Paneer bhurji; dal chawal bhi chalega.", CANDS)
    assert [i.ref for i in card.items] == ["b", "a"]
    whey, paneer = card.items
    assert whey.saved and whey.protein_g == 24 and "cookable now" in whey.why
    assert paneer.missing == ["capsicum"] and paneer.minutes == 15 and "missing" in paneer.why


async def test_a_name_that_is_not_in_the_prose_is_not_suggested(client):
    from app.agent import cards as C
    assert C.suggest_from_text("Kuch bhi kha lo.", CANDS) == []
    # Half a name is not the name: "paneer" alone does not pick Paneer bhurji.
    assert C.suggest_from_text("paneer hai ghar pe?", CANDS) == []
    assert C.suggest_from_text("", CANDS) == [] and C.suggest_from_text("Whey shake", []) == []


async def test_a_suggest_turn_carries_the_dish_card(client, fake, library):
    fake(_msg(calls=[("suggest_dishes", {"local_day": "2026-08-20"})]),
         _msg("Whey shake le lo — 24 g protein."))
    body = (await client.post("/chat", json={"message": "kya khau?",
                                             "local_day": "2026-08-20"})).json()
    card = next(c for c in body["cards"] if c["kind"] == "suggest")
    [item] = card["items"]
    assert item["ref"] == "t-dish-whey" and item["type"] == "dish"
    assert item["protein_g"] == 24 and item["kcal"] == 120
    assert "image_url" in item and "missing" in item


# ─── rows by id ──────────────────────────────────────────────────────────────

async def test_rows_by_id_come_back_deleted_ones_included(client):
    a = (await make_transaction(client)).json()["id"]
    b = (await make_transaction(client)).json()["id"]
    assert (await client.delete(f"/transactions/{b}")).status_code == 204
    r = await client.get("/transactions", params={"ids": f"{a},{b},nope"})
    assert r.status_code == 200
    rows = {x["id"]: x for x in r.json()}
    assert set(rows) == {a, b}
    assert rows[a]["deleted_at"] is None and rows[b]["deleted_at"] is not None

    m = (await make_meal(client)).json()["meal"]["id"]
    n = (await make_meal(client)).json()["meal"]["id"]
    assert (await client.delete(f"/meals/{n}")).status_code == 204
    rows = {x["id"]: x for x in (await client.get("/meals", params={"ids": f"{m},{n}"})).json()}
    assert rows[m]["deleted_at"] is None and rows[n]["deleted_at"] is not None


async def test_rows_by_id_are_capped(client):
    assert (await client.get("/transactions", params={"ids": ""})).status_code == 422
    too_many = ",".join(ulid() for _ in range(51))
    assert (await client.get("/transactions", params={"ids": too_many})).status_code == 422


async def test_the_deck_still_hides_deleted_rows(client):
    """The by-id read is the exception; the deck stays a read of what is live."""
    row = (await make_transaction(client, local_day="2026-08-19")).json()
    await client.delete(f"/transactions/{row['id']}")
    deck = (await client.get("/deck", params={"to": "2026-08-20"})).json()
    assert row["id"] not in {t["id"] for t in deck["paisa"]["transactions"]}


# ─── a tap: the tool without the model ───────────────────────────────────────

ACT_MEAL = {"name": "log_meal", "args": {
    "dish_id": "t-dish-whey", "text_said": "Whey shake", "meal_type": "Snack",
    "local_day": "2026-08-20"}}


async def test_a_tap_runs_the_tool_and_returns_a_receipt_not_a_turn(client, library):
    before = len((await client.get("/chat")).json()["messages"])
    r = await client.post("/chat/act", json=ACT_MEAL)
    assert r.status_code == 200, r.text
    body = r.json()
    confirm = next(c for c in body["cards"] if c["kind"] == "confirm")
    assert confirm["source"] == "diet" and confirm["row_id"]
    # Resolved by id, nothing guessed: no dot on the macros.
    assert not next(f for f in confirm["fields"] if f["key"] == "protein_g")["guessed"]
    assert body["reply"].startswith("Whey shake ·")
    # The meal is in the ledger; the thread is untouched — a receipt is not
    # something that was said.
    assert len((await client.get("/chat")).json()["messages"]) == before
    rows = (await client.get("/meals", params={"ids": confirm["row_id"]})).json()
    assert rows and rows[0]["deleted_at"] is None


async def test_a_recorded_act_joins_the_thread(client, library):
    r = await client.post("/chat/act", json={**ACT_MEAL, "record": True})
    confirm = next(c for c in r.json()["cards"] if c["kind"] == "confirm")
    last = (await client.get("/chat")).json()["messages"][-1]
    assert last["role"] == "agent" and last["text"].startswith("Whey shake ·")
    assert any(c["kind"] == "confirm" and c["row_id"] == confirm["row_id"] for c in last["cards"])


async def test_a_tap_on_an_unknown_tool_is_refused(client):
    r = await client.post("/chat/act", json={"name": "drop_everything", "args": {}})
    assert r.status_code == 404


async def test_a_tap_whose_tool_refuses_returns_the_refusal(client):
    r = await client.post("/chat/act", json={"name": "log_meal", "args": {
        "dish_id": "no-such-dish", "text_said": "x", "meal_type": "Snack",
        "local_day": "2026-08-20"}})
    assert r.status_code == 422 and "no dish" in r.json()["detail"]
    r = await client.post("/chat/act", json={"name": "log_payment", "args": {
        "amount_paise": 500, "direction": "debit", "kind": "lent", "category": "Other",
        "description": "udhaar", "local_day": "2026-08-20"}})
    assert r.status_code == 422  # a lending must name the person — the route's rule


# ─── exercises get the same card ─────────────────────────────────────────────

async def test_exercises_named_in_the_prose_become_a_card(client):
    from app.agent import cards as C
    cands = [
        {"_type": "exercise", "id": "e1", "name": "Goblet squat", "aliases": [],
         "kind": "strength", "muscle_group": "legs", "typical_minutes": 10, "tried": 2},
        {"_type": "exercise", "id": "e2", "name": "Brisk walk", "aliases": ["walk"],
         "kind": "cardio", "muscle_group": None, "typical_minutes": 30, "tried": 0},
    ]
    [card] = C.suggest_from_text("Aaj legs: **Goblet squat** 3 sets, phir 20 min walk.", cands)
    assert [(i.type, i.ref) for i in card.items] == [("exercise", "e1"), ("exercise", "e2")]
    squat, walk = card.items
    assert squat.muscle_group == "legs" and squat.tried == 2 and "done 2×" in squat.why
    assert walk.minutes == 30 and "not tried yet" in walk.why


async def test_an_exercise_turn_carries_the_card(client, fake):
    made = (await client.post("/exercises", json={
        "id": ulid(), "name": "Test goblet squat", "kind": "strength",
        "muscle_group": "legs", "typical_minutes": 10, "source": "chat"})).json()
    fake(_msg(calls=[("exercises", {"muscle_group": "legs"})]),
         _msg("Test goblet squat karo, 3 sets."))
    body = (await client.post("/chat", json={"message": "legs ke liye kya karu?",
                                             "local_day": "2026-08-20"})).json()
    card = next(c for c in body["cards"] if c["kind"] == "suggest")
    [item] = card["items"]
    assert item["type"] == "exercise" and item["ref"] == made["id"]
    assert item["muscle_group"] == "legs" and item["exercise_kind"] == "strength"
