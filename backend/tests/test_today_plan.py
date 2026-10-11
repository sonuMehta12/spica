"""spec/in-progress/today-plan.md — the rest of today's meals, and one workout.

The model is faked: whether its plans are good is n2n_eval's question. These
assert what the server owes around it — the plan is checked against the rows
(a library dish keeps its own numbers; an id the model invents makes an idea),
only the slots still ahead are planned, the plan is reused until a write it read
changes, a failure is said rather than cached, and pictures come from Commons
under a free licence, looked for once.

Commons is faked too, for every test here: the suite never touches the network.
"""

import json
from types import SimpleNamespace

import pytest

from tests.helpers import make_meal, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")

DAY = "2026-05-20"


class FakeModel:
    """Answers the planner with `plan`, and anything else (a meal's estimate)
    with a plain price. Counts the planner's calls."""

    def __init__(self, plan):
        self.plan, self.plan_calls, self.payload = plan, 0, None
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **kw):
        if "Today's plan" in kw.get("instructions", ""):
            self.plan_calls += 1
            self.payload = kw.get("input")
            if isinstance(self.plan, Exception):
                raise self.plan
            text = self.plan if isinstance(self.plan, str) else json.dumps(self.plan)
        else:
            text = json.dumps({"kcal": 400, "protein_g": 20, "carbs_g": 40, "fat_g": 12, "fibre_g": 3})
        return SimpleNamespace(output=[], output_text=text,
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1))


COMMONS_HIT = {"query": {"pages": {
    "1": {"index": 1, "title": "File:Rajma chawal plate.jpg", "imageinfo": [{"mime": "image/jpeg", "thumburl": "https://upload.example/nc.jpg",
                                     "extmetadata": {"LicenseShortName": {"value": "CC BY-NC 2.0"},
                                                     "Artist": {"value": "Someone"}}}]},
    "2": {"index": 2, "title": "File:Rajma Chawal Rajma Rice.jpg", "imageinfo": [{"mime": "image/jpeg", "thumburl": "https://upload.example/rajma.jpg",
                                     "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"},
                                                     "Artist": {"value": '<a href="/u/x">Jane Doe</a>'}}}]},
}}}


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    """No network, a cold cache, and the whole library in the context."""
    from app import images
    from app.agent import plan
    plan._cache.clear()
    images._ideas.clear()
    monkeypatch.setattr(plan, "DISHES", 1000)
    queries = []

    async def no_commons(text):
        queries.append(text)
        return {}
    monkeypatch.setattr(images, "_query", no_commons)
    return queries


@pytest.fixture
def model(monkeypatch):
    def install(plan):
        fake = FakeModel(plan)
        monkeypatch.setattr("app.llm.client", lambda: fake)
        monkeypatch.setattr("app.llm.model", lambda: "fake-model")
        return fake
    return install


async def dish(client, name, **over):
    body = {"id": ulid(), "name": name, "serving_label": "1 plate", "protein_g": "30",
            "kcal": 450, "carbs_g": "50", "fat_g": "12", "meal_type": "Lunch"}
    body.update(over)
    r = await client.post("/dishes", json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


async def get_plan(client, local_time="08:00", day=DAY):
    r = await client.get("/plan/today", params={"local_day": day, "local_time": local_time})
    assert r.status_code == 200, r.text
    return r.json()


# ─── checked, not trusted ────────────────────────────────────────────────────

async def test_a_library_dish_keeps_its_own_numbers_and_an_invented_id_is_an_idea(client, model):
    rajma = await dish(client, "Plan rajma chawal", kcal=520, protein_g="22", carbs_g="80", fat_g="11")
    fake = model({"meals": [
        {"slot": "Breakfast", "dish_id": None, "name": "Besan chilla with dahi",
         "kcal": 380, "protein_g": 24, "carbs_g": 30, "fat_g": 14, "why": "24 g protein"},
        # The model misremembers the library's numbers: the library wins.
        {"slot": "Lunch", "dish_id": rajma["id"], "name": "Rajma", "kcal": 999, "protein_g": 99,
         "carbs_g": 1, "fat_g": 1, "why": "rajma is in"},
        {"slot": "Dinner", "dish_id": "01NOTADISHTHEMODELMADEUP", "name": "Paneer tikka",
         "kcal": 420, "protein_g": 30, "carbs_g": 12, "fat_g": 26, "why": "30 g protein"},
    ]})
    p = await get_plan(client)
    assert p["available"] and fake.plan_calls == 1
    by_slot = {m["slot"]: m for m in p["meals"]}
    lunch = by_slot["Lunch"]
    assert lunch["dish_id"] == rajma["id"] and not lunch["idea"] and not lunch["estimated"]
    assert (lunch["name"], lunch["kcal"], lunch["protein_g"]) == ("Plan rajma chawal", 520, 22.0)
    assert (lunch["carbs_g"], lunch["fat_g"]) == (80.0, 11.0)
    assert by_slot["Breakfast"]["idea"] and by_slot["Breakfast"]["estimated"]
    dinner = by_slot["Dinner"]
    assert dinner["dish_id"] is None and dinner["idea"] and dinner["name"] == "Paneer tikka"
    # In the day's order, and the sum is the meals'.
    assert [m["slot"] for m in p["meals"]] == ["Breakfast", "Lunch", "Dinner"]
    assert p["planned"] == {"protein_g": 76.0, "kcal": 1320}


async def test_a_meal_with_no_name_or_no_calories_is_dropped(client, model):
    model({"meals": [{"slot": "Lunch", "dish_id": None, "name": "", "kcal": 300, "protein_g": 10},
                     {"slot": "Dinner", "dish_id": None, "name": "Air", "kcal": 0, "protein_g": 0}]})
    assert (await get_plan(client))["meals"] == []


async def test_only_the_slots_still_ahead_are_planned(client, model):
    await make_meal(client, local_day=DAY, occurred_at=f"{DAY}T09:00:00+05:30",
                    meal_type="Breakfast", dish="Oats", kcal=300, protein_g="15")
    fake = model({"meals": [
        {"slot": "Breakfast", "dish_id": None, "name": "Poha", "kcal": 300, "protein_g": 8},
        {"slot": "Lunch", "dish_id": None, "name": "Dal roti", "kcal": 500, "protein_g": 20},
        {"slot": "Lunch", "dish_id": None, "name": "A second lunch", "kcal": 500, "protein_g": 20},
        {"slot": "Dinner", "dish_id": None, "name": "Egg curry", "kcal": 450, "protein_g": 25},
    ]})
    p = await get_plan(client, local_time="12:30")
    assert p["slots_ahead"] == ["Lunch", "Snack", "Dinner"]
    assert [m["name"] for m in p["meals"]] == ["Dal roti", "Egg curry"]
    assert p["logged"]["kcal"] >= 300
    # What the model was told is what was checked: the same slots.
    assert json.loads(fake.payload)["slots_ahead"] == ["Lunch", "Snack", "Dinner"]


async def test_late_at_night_the_meals_are_done(client, model):
    model({"meals": [{"slot": "Dinner", "dish_id": None, "name": "Late dinner", "kcal": 500, "protein_g": 20}],
           "workout": {"kind": "walk", "name": "Walk", "minutes": 20, "why": "a light end"}})
    p = await get_plan(client, local_time="23:30", day="2026-05-21")
    assert p["done"] and p["meals"] == [] and p["workout"]["kind"] == "walk"


# ─── one call per change ─────────────────────────────────────────────────────

async def test_opening_twice_is_one_call_and_a_meal_logged_replans(client, model):
    fake = model({"meals": [{"slot": "Dinner", "dish_id": None, "name": "Khichdi", "kcal": 400, "protein_g": 15}]})
    day = "2026-05-22"
    await get_plan(client, local_time="17:00", day=day)
    await get_plan(client, local_time="17:05", day=day)
    assert fake.plan_calls == 1
    await make_meal(client, local_day=day, occurred_at=f"{day}T17:30:00+05:30",
                    meal_type="Snack", dish="Chana", kcal=200, protein_g="10")
    await get_plan(client, local_time="17:35", day=day)
    assert fake.plan_calls == 2


async def test_a_failure_is_said_and_not_kept(client, model):
    day = "2026-05-23"
    fake = model(RuntimeError("provider down"))
    p = await get_plan(client, day=day)
    assert p["available"] is False and p["meals"] == []
    fake.plan = "not json at all"
    assert (await get_plan(client, day=day))["available"] is False
    fake.plan = {"meals": [{"slot": "Lunch", "dish_id": None, "name": "Dal chawal", "kcal": 500, "protein_g": 18}]}
    p = await get_plan(client, day=day)
    assert p["available"] and fake.plan_calls == 3


# ─── the workout ─────────────────────────────────────────────────────────────

async def test_the_workout_names_library_exercises_and_marks_the_rest(client, model):
    ex = (await client.post("/exercises", json={"id": ulid(), "name": "Plan goblet squat",
                                                "kind": "strength", "muscle_group": "legs"})).json()
    model({"meals": [], "workout": {"kind": "gym", "name": "Legs", "minutes": 40, "why": "no legs since Monday",
                                    "exercises": [{"exercise_id": ex["id"], "name": "Squat", "detail": "3 × 10"},
                                                  {"exercise_id": "01INVENTED", "name": "Lunges", "detail": "3 × 12"}]}})
    w = (await get_plan(client, day="2026-05-24"))["workout"]
    assert w["kind"] == "gym" and w["minutes"] == 40 and not w["idea"]
    assert [(i["name"], i["idea"]) for i in w["exercises"]] == [("Plan goblet squat", False), ("Lunges", True)]


async def test_an_unknown_workout_kind_is_no_workout(client, model):
    model({"meals": [], "workout": {"kind": "skydiving", "minutes": 30}})
    assert (await get_plan(client, day="2026-05-25"))["workout"] is None


# ─── pictures ────────────────────────────────────────────────────────────────

async def test_a_dish_gets_a_free_picture_with_its_credit_and_no_match_is_not_retried(
        client, model, monkeypatch, quiet):
    from app import images
    from app.agent import plan
    found = await dish(client, "Plan pictured rajma")
    bare = await dish(client, "Plan nothing on commons")

    async def commons(text):
        quiet.append(text)
        return COMMONS_HIT if "rajma" in text.lower() else {}
    monkeypatch.setattr(images, "_query", commons)
    model({"meals": [{"slot": "Lunch", "dish_id": found["id"]},
                     {"slot": "Dinner", "dish_id": bare["id"]}]})
    p = await get_plan(client, day="2026-05-26")
    lunch, dinner = p["meals"]
    # The non-commercial photo ranked first is passed over for the free one.
    assert lunch["image_url"] == "https://upload.example/rajma.jpg"
    assert lunch["image_credit"] == "Photo: Jane Doe, CC BY-SA 4.0 · Wikimedia Commons"
    assert dinner["image_url"] is None
    looked = [q for q in quiet if "nothing on commons" in q.lower()]
    assert looked

    # Stored on the rows: the next plan reads them, and does not search again.
    plan._cache.clear()
    quiet.clear()
    p = await get_plan(client, day="2026-05-26", local_time="08:05")
    assert p["meals"][0]["image_url"] == "https://upload.example/rajma.jpg"
    assert quiet == []
    got = (await client.get("/dishes", params={"q": "Plan pictured rajma", "mine": "false"})).json()
    assert any(d.get("image_url") == "https://upload.example/rajma.jpg" for d in got)


async def test_a_photo_sharing_no_word_with_the_name_is_no_match():
    """Commons ranks loosely: *chicken curry with roti* once came back as peas."""
    from app.images import pick
    peas = {"query": {"pages": {"1": {"index": 1, "title": "File:Peas pulao.jpg", "imageinfo": [{
        "mime": "image/jpeg", "thumburl": "https://upload.example/peas.jpg",
        "extmetadata": {"LicenseShortName": {"value": "CC0"}, "Artist": {"value": "A"}}}]}}}}
    assert pick(peas, "Chicken curry with rice and roti") is None
    assert pick(COMMONS_HIT, "Rajma chawal").url == "https://upload.example/rajma.jpg"


async def test_only_free_licences_are_shown():
    from app.images import free
    assert free("CC BY-SA 4.0") and free("CC0") and free("Public domain") and free("CC BY 2.0")
    assert not free("CC BY-NC 2.0") and not free("CC BY-ND 3.0") and not free("All rights reserved")
