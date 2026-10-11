"""spec/in-progress/meal-estimates.md — the model prices the plate.

A meal used to be worth whatever the library matched, so a plate the library
had never seen was logged at 0 kcal. These assert the split: the ladder still
answers *what is this* and spends the pantry, while *what is it worth* comes
from an estimate that is never silent, freezes what it said, and learns from
being corrected.

The model is faked. Whether its numbers are good is `scripts/estimate_eval.py`'s
question — measured before this was built.
"""

import json
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

DAY = "2026-04-12"


class FakeModel:
    """The seam, scripted. Records the system prompt so a test can assert on
    what the estimator was told about this person."""

    def __init__(self, text):
        self.text, self.sent = text, []
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **kw):
        self.sent.append(kw)
        return SimpleNamespace(output=[], output_text=self.text,
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1))


@pytest.fixture
def priced(monkeypatch):
    """Install a scripted estimate and hand back the fake."""
    def install(**over):
        body = {"kcal": 460, "protein_g": 23, "carbs_g": 52, "fat_g": 18,
                "fibre_g": 4, "why": "3 rotis at ~110 each",
                "assumption": "2 roti ~40g each"}
        body.update(over)
        fake = FakeModel(json.dumps(body))
        monkeypatch.setattr("app.llm.client", lambda: fake)
        monkeypatch.setattr("app.llm.model", lambda: "fake-model")
        return fake
    return install


async def _user(db_session):
    from tests.helpers import the_user
    return await the_user(db_session)


async def log(db_session, user, said, meal_type="Breakfast", day=DAY):
    from app.agent import tools as T
    return await T.run(db_session, user, "log_meal",
                       {"text_said": said, "meal_type": meal_type, "local_day": day})


# ─── the gap this closes ─────────────────────────────────────────────────────

async def test_a_plate_the_library_has_never_seen_gets_real_numbers(
        client, db_session, priced):
    """"2 roti and 2 egg omletes" logged at 0 kcal / 0 protein is the whole
    reason this exists. Nothing in that sentence resolves to a priced row."""
    from app.agent.estimate import ESTIMATED
    user = await _user(db_session)
    priced()
    out = await log(db_session, user, "2 roti and 2 egg omletes")
    await db_session.commit()

    assert not out.get("error"), out
    meal = out["meal"]
    assert meal["kcal"] == 460 and float(meal["protein_g"]) == 23
    assert float(meal["fibre_g"]) == 4, "fibre is estimated and stored"
    assert meal["confidence"] == ESTIMATED, "an estimate is never certain"
    assert out["nutrition_known"] is True
    # The ladder still did its half: one line matched, one did not.
    assert "egg omletes" in out["unresolved"]


async def test_the_estimate_is_frozen_and_a_correction_does_not_touch_it(
        client, db_session, priced):
    """The gap between the two IS the error. If a correction overwrote the
    estimate there would be nothing left to measure, and it cannot be
    recomputed later."""
    user = await _user(db_session)
    priced(kcal=420, protein_g=6)
    out = await log(db_session, user, "KitKat (2 bars)", "Snack")
    await db_session.commit()
    meal_id = out["meal"]["id"]
    assert out["meal"]["estimated_kcal"] == 420

    r = await client.patch(f"/meals/{meal_id}", json={"kcal": 186, "protein_g": "3"})
    assert r.status_code == 200, r.text
    fixed = r.json()["meal"]
    assert fixed["kcal"] == 186, "what they settled on"
    assert fixed["estimated_kcal"] == 420, "what we had said, untouched"
    assert fixed["corrected_at"] is not None


async def test_only_a_macro_change_counts_as_a_correction(client, db_session, priced):
    """Moving a meal to another day is not the user overruling the estimate."""
    user = await _user(db_session)
    priced()
    out = await log(db_session, user, "Test moved plate", "Lunch")
    await db_session.commit()
    meal_id = out["meal"]["id"]

    r = await client.patch(f"/meals/{meal_id}", json={"note": "office mein"})
    assert r.json()["meal"]["corrected_at"] is None, "a note is not a correction"

    r = await client.patch(f"/meals/{meal_id}", json={"protein_g": "31"})
    assert r.json()["meal"]["corrected_at"] is not None


async def test_a_correction_reaches_the_next_estimates_context(
        client, db_session, priced):
    """The pair is the calibration set. A KitKat corrected to 186 has to be in
    front of the model the next time a KitKat is logged."""
    user = await _user(db_session)
    priced(kcal=420)
    out = await log(db_session, user, "Test KitKat calibration", "Snack")
    await db_session.commit()
    await client.patch(f"/meals/{out['meal']['id']}", json={"kcal": 186})

    fake = priced(kcal=190)
    await log(db_session, user, "Test KitKat calibration", "Snack")
    await db_session.commit()

    system = fake.sent[0]["instructions"]
    assert "They corrected these" in system
    assert "Test KitKat calibration: 186 kcal" in system
    assert "we had said 420" in system, "the miss is shown, not just the answer"


async def test_correcting_a_meal_writes_nothing_to_the_library(
        client, db_session, priced):
    """Promoting corrections into `dishes` would fill the menu with "KitKat
    (2 bars)" and "chai aur 2 biscuit". The user's star is the only door in."""
    from sqlalchemy import func, select

    from app.models.diet import Dish
    user = await _user(db_session)
    before = await db_session.scalar(select(func.count()).select_from(Dish))
    priced()
    out = await log(db_session, user, "Test never-a-dish plate", "Snack")
    await db_session.commit()
    await client.patch(f"/meals/{out['meal']['id']}", json={"kcal": 111})
    await db_session.commit()
    assert await db_session.scalar(select(func.count()).select_from(Dish)) == before


# ─── the ladder's half is untouched ──────────────────────────────────────────

async def test_the_ladder_still_names_the_plate_and_spends_the_pantry(
        client, db_session, priced, library):
    """Identity is still a database question, and the pantry still moves."""
    user = await _user(db_session)
    priced()
    out = await log(db_session, user, "Whey shake", "Snack")
    await db_session.commit()
    [line] = out["lines"]
    assert line["matched"] and line["rung"] == "exact"
    assert out["meal"]["kcal"] == 460, "identity resolved, worth still estimated"


async def test_a_tap_on_a_known_dish_is_not_an_estimate(client, db_session, priced,
                                                        library):
    """`dish_id` means they picked that row at its stated serving. Estimating
    over it would put an amber dot on a number nobody guessed."""
    from app.agent import tools as T
    fake = priced()
    user = await _user(db_session)
    out = await T.run(db_session, user, "log_meal", {
        "text_said": "Whey shake", "meal_type": "Snack",
        "local_day": DAY, "dish_id": "t-dish-whey", "servings": 1})
    await db_session.commit()
    assert not out.get("error"), out
    assert out["meal"]["confidence"] == 1.0
    assert out["meal"]["estimated_kcal"] is None
    assert fake.sent == [], "the estimator was never called"


# ─── what stands between the model and the ledger ────────────────────────────

async def test_a_model_that_fails_does_not_lose_the_log(client, db_session,
                                                        monkeypatch, library):
    """The log matters more than the number. The library becomes the fallback
    it always should have been."""
    async def broken(**kw):
        raise RuntimeError("the model is down")
    monkeypatch.setattr("app.llm.client", lambda: SimpleNamespace(
        responses=SimpleNamespace(create=broken)))
    user = await _user(db_session)
    out = await log(db_session, user, "Whey shake", "Snack")
    await db_session.commit()
    assert not out.get("error"), out
    assert out["meal"]["kcal"] > 0, "the library caught it"
    assert out["meal"]["estimated_kcal"] is None, "nothing was estimated"


@pytest.mark.parametrize("answer", [
    "sorry, I cannot help with that",
    '{"kcal": 0, "protein_g": 0}',
    '{"kcal": "a lot"}',
])
async def test_an_unusable_answer_is_no_answer(client, db_session, priced, answer):
    """A zero would be read as "this food has no calories", which is worse
    than being wrong by a fifth. Unparseable and zero are both refusals."""
    from app.agent.estimate import parse
    assert parse(answer) is None

    priced(**{"kcal": 0})          # a zero body, which parse() refuses
    user = await _user(db_session)
    out = await log(db_session, user, "Test unusable answer plate", "Snack")
    await db_session.commit()
    assert not out.get("error"), out
    assert out["meal"]["estimated_kcal"] is None, "nothing unusable is written"


async def test_the_skill_file_is_the_static_half_plus_their_rows(
        client, db_session, priced):
    from app.agent.estimate import SKILL_FILE
    user = await _user(db_session)
    fake = priced()
    await log(db_session, user, "Test context plate", "Lunch")
    await db_session.commit()

    system = fake.sent[0]["instructions"]
    static = SKILL_FILE.read_text()
    assert system.startswith("# You price a plate of food")
    assert "ghar ka" in static, "how to read the words lives in the repo"
    assert "# What this person's food has been worth" in system
    assert "Their usual portions" in system, "generated from their own rows"
    # Nothing about this user is baked into the file on disk.
    assert "KitKat" not in static and "Whey shake" not in static


# ─── what may move a shelf ───────────────────────────────────────────────────

async def test_a_fuzzy_match_never_takes_food_off_the_shelf(client, db_session):
    """A trigram hit is a guess about identity. It may be drawn on a card and
    handed to the estimator; it may not empty a shelf. A missing subtraction is
    visible — "pantry still says I have eggs" — and a wrong one is silent."""
    from tests.helpers import ulid
    food = (await client.post("/pantry", json={
        "id": ulid(), "food_name": "Test fuzzy paneer", "unit": "g"})).json()
    await client.post("/pantry-moves", json={
        "id": ulid(), "food_id": food["food_id"], "quantity": 500, "kind": "purchase",
        "local_day": "2026-04-12", "occurred_at": "2026-04-12T10:00:00+05:30"})

    def stock():
        return next(r for r in shelf if r["name"] == "Test fuzzy paneer")["stock_g"]

    shelf = (await client.get("/pantry")).json()
    assert stock() == 500

    # Named by trigram — refused.
    await client.post("/meals", json={
        "id": ulid(), "occurred_at": "2026-04-12T13:00:00+05:30", "local_day": "2026-04-12",
        "meal_type": "Lunch", "dish": "panir", "kcal": 300, "protein_g": "20",
        "source": "manual",
        "items": [{"food_id": food["food_id"], "quantity": 100,
                   "said": "panir", "rung": "similar"}]})
    shelf = (await client.get("/pantry")).json()
    assert stock() == 500, "a guess must not spend"

    # Named exactly — spends.
    await client.post("/meals", json={
        "id": ulid(), "occurred_at": "2026-04-12T14:00:00+05:30", "local_day": "2026-04-12",
        "meal_type": "Snack", "dish": "Test fuzzy paneer", "kcal": 300, "protein_g": "20",
        "source": "manual",
        "items": [{"food_id": food["food_id"], "quantity": 100,
                   "said": "Test fuzzy paneer", "rung": "exact"}]})
    shelf = (await client.get("/pantry")).json()
    assert stock() == 400, "an exact name spends"


async def test_a_food_named_by_id_spends_even_without_a_rung(client, db_session):
    """NULL is not "uncertain" — it is *nobody guessed*. A client POSTing a
    `food_id` is the caller naming the food, not the ladder matching a word."""
    from app.models.diet import MealItem
    from app.routes.writes import may_spend
    assert may_spend(MealItem(food_id="f", quantity=10, rung=None))
    assert may_spend(MealItem(food_id="f", quantity=10, rung="alias"))
    assert not may_spend(MealItem(food_id="f", quantity=10, rung="similar"))


# ─── the model says how much, the database says what ─────────────────────────

async def test_an_ingredient_resolves_by_name_and_spends_in_the_foods_own_unit(
        client, db_session, library):
    """Names, never ids — that is what makes this safe. And 100 g of egg is
    2 pieces, because `grams_per_unit` says an egg is 50 g."""
    from app.agent.estimate import resolve_ingredients
    user = await _user(db_session)
    got = await resolve_ingredients(db_session, user, [
        {"food": "anda", "grams": 100},          # alias → Egg, 2 pieces
        {"food": "roti", "grams": 80},           # alias → Atta, 80 g
        {"food": "unobtainium", "grams": 500},   # invented → nothing
        {"food": "anda", "grams": 0},            # no amount → nothing
    ])
    by = {i.said: i for i in got}
    assert set(by) == {"anda", "roti"}, "only names the ledger knows survive"
    assert by["anda"].quantity == 2, "100 g of egg is two pieces"
    assert by["roti"].quantity == 80, "a food sold in grams takes the grams"
    assert all(i.rung in ("exact", "alias") for i in got)


async def test_a_fuzzy_ingredient_name_is_refused(client, db_session, library):
    """A trigram hit on an ingredient is the same guess the ladder makes, and
    it may not move a shelf either."""
    from app.agent.estimate import resolve_ingredients
    from app.agent.ladder import resolve_one
    user = await _user(db_session)
    typo = "dal famly stock"
    fuzzy = await resolve_one(db_session, user, typo)
    assert fuzzy["matched"] and fuzzy["rung"] == "similar", f"precondition: {fuzzy}"
    assert await resolve_ingredients(db_session, user, [{"food": typo, "grams": 80}]) == []


async def test_ingredients_replace_the_ladders_lines_never_add_to_them(
        client, db_session, priced, library):
    """One source or the plate is subtracted twice. The ladder finds "roti"
    with no quantity at all; the model says what it weighed."""
    from sqlalchemy import select

    from app.models.diet import MealItem
    user = await _user(db_session)
    priced(ingredients=[{"food": "roti", "grams": 80}, {"food": "ande", "grams": 100}])
    out = await log(db_session, user, "2 roti and 2 ande")
    await db_session.commit()

    rows = (await db_session.scalars(select(MealItem).where(
        MealItem.meal_log_id == out["meal"]["id"]))).all()
    assert sorted(r.said for r in rows) == ["ande", "roti"]
    assert {r.quantity for r in rows} == {80, 2}, "grams for atta, pieces for egg"
    assert all(r.rung in ("exact", "alias") for r in rows)
    assert len(rows) == 2, "the ladder's own lines were replaced, not added to"


async def test_without_ingredients_the_ladder_still_supplies_the_lines(
        client, db_session, priced, library):
    """The fallback is the old path, unchanged — so a model that returns no
    ingredients costs the new coverage, not the old."""
    from sqlalchemy import select

    from app.models.diet import MealItem
    user = await _user(db_session)
    priced(ingredients=[])
    out = await log(db_session, user, "Whey shake", "Snack")
    await db_session.commit()
    rows = (await db_session.scalars(select(MealItem).where(
        MealItem.meal_log_id == out["meal"]["id"]))).all()
    assert [r.said for r in rows] == ["Whey shake"]
