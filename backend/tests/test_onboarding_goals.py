"""spec/done/onboarding-goals.md — the answers, where they are kept and who reads them.

The data half: two columns on `users`, an estimate flag on `weigh_ins`, the
tools that write them, the migration's backfill, `/deck`'s flag, and the two
readers that make the questions' reasons true — the chat agent's prompt and
Home's meal plan. Then the agent that takes the answers: `POST
/onboarding/turn`, its six tools, one transaction a turn, its caps, and the
thread it stays out of — with the model faked, as everywhere in these tests.

Each test signs in as a brand-new account: the shared test user has rows from
every other test, and a gender or a diet set on it would leak into theirs.
"""

import importlib.util
import inspect
import json
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.agent import cards as C
from app.agent import prompt as P
from app.agent import tools as T
from app.auth import hash_token
from app.models.base import new_id
from app.models.diet import Habit
from app.models.users import Session, User
from tests.helpers import _msg, make_meal, make_transaction, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")

DAY = "2026-08-20"


def this_year() -> int:
    """The person's local year — an account's timezone defaults to Kolkata."""
    return datetime.now(ZoneInfo("Asia/Kolkata")).year


@asynccontextmanager
async def signed_in(db_session, name="New person"):
    """A new account with nothing in it, and a client signed in as it."""
    person = User(id=new_id(), display_name=name)
    raw = f"onboarding-goals-{person.id}"
    db_session.add(person)
    await db_session.flush()
    session = Session(user_id=person.id, token_hash=hash_token(raw),
                      expires_at=datetime.now(UTC) + timedelta(days=1))
    db_session.add(session)
    await db_session.commit()
    # Out of the identity map: the API writes this row from its own session,
    # and a stale copy here would answer every later read in this test.
    db_session.expunge(person)
    db_session.expunge(session)

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t",
                           headers={"Authorization": f"Bearer {raw}"}) as c:
        yield person.id, c


@pytest_asyncio.fixture(loop_scope="session")
async def fresh(client, db_session):
    async with signed_in(db_session) as account:
        yield account


async def me(c) -> dict:
    r = await c.get("/users/me")
    assert r.status_code == 200, r.text
    return r.json()


async def run(db_session, uid, name, args) -> dict:
    out = await T.run(db_session, uid, name, args)
    await db_session.commit()
    return out


# ─── 1 · the profile: two new columns, and update_profile reaches them ──────

async def test_the_first_answer_is_one_write_per_fact_each_with_its_card(fresh, db_session):
    """*"Sonu, male, 28. Five nine, around 72 kilo"*, as the agent writes it."""
    uid, c = fresh
    calls = [
        ("update_profile", {"field": "display_name", "value": "Sonu"}),
        ("update_profile", {"field": "gender", "value": "male"}),
        ("update_profile", {"field": "age", "value": 28}),
        ("update_profile", {"field": "height_cm", "value": 175.26}),
        ("log_day", {"local_day": DAY, "weight_kg": 72, "approximate": True}),
    ]
    cards = []
    for name, args in calls:
        out = await run(db_session, uid, name, args)
        assert not out.get("error"), (name, out)
        made = C.from_tool(name, args, out)
        assert len(made) == 1 and made[0].kind == "confirm", name
        cards.append(made[0])

    row = await me(c)
    assert (row["display_name"], row["gender"]) == ("Sonu", "male")
    # 28 said in 2026 is 1998-01-01: 1 January of the year it gives.
    assert row["dob"] == date(this_year() - 28, 1, 1).isoformat()
    assert float(row["height_cm"]) == 175.3, "stored at the column's precision"

    [w] = (await c.get("/weigh-ins")).json()
    assert (float(w["weight_kg"]), w["estimated"], w["local_day"]) == (72.0, True, DAY)

    age, height, weight = cards[2], cards[3], cards[4]
    assert age.lede == "Age → 28 years", "a date of birth is shown as an age"
    # Not `dob`: builds that know that key draw the live row as a date, and
    # the invented 1 January would read as a birthday.
    assert [(f.key, f.value) for f in age.fields] == [("age", "28 years")]
    assert height.fields[0].value == "175 cm"
    assert [f.guessed for f in weight.fields if f.key == "weight_kg"] == [True]
    assert not any(f.guessed for card in cards[:4] for f in card.fields), \
        "only the weight can be approximate"


async def test_update_profile_writes_city_diet_and_an_exact_date_of_birth(fresh, db_session):
    uid, c = fresh
    for field, value in (("city", "Delhi"), ("diet", "eggetarian"), ("dob", "1990-05-14"),
                         ("weight_target_kg", 67)):
        out = await run(db_session, uid, "update_profile", {"field": field, "value": value})
        assert not out.get("error"), (field, out)
    row = await me(c)
    assert (row["city"], row["diet"], row["dob"]) == ("Delhi", "eggetarian", "1990-05-14")
    assert float(row["weight_target_kg"]) == 67.0
    [card] = C.from_tool("update_profile", {}, {"diet": "eggetarian"})
    assert card.lede == "Diet → Eggetarian"
    [card] = C.from_tool("update_profile", {}, {"weight_target_kg": 67.0})
    assert card.lede == "Weight target → 67 kg"


async def test_an_age_is_turned_into_a_date_by_the_server_however_it_is_sent(fresh, db_session):
    """The model never does date arithmetic; it passes the age as said."""
    uid, c = fresh
    for said in (28, 28.0, "28"):
        out = await run(db_session, uid, "update_profile", {"field": "age", "value": said})
        assert out == {"dob": date(this_year() - 28, 1, 1).isoformat(), "age": 28}, said
    out = await run(db_session, uid, "update_profile", {"field": "age", "value": 29})
    assert (await me(c))["dob"] == date(this_year() - 29, 1, 1).isoformat(), \
        "'actually I'm 29' corrects the row"
    assert out["age"] == 29


async def test_update_profile_refuses_a_value_outside_each_check(fresh, db_session):
    uid, c = fresh
    for field, value in (("gender", "male"), ("diet", "veg"), ("height_cm", 170),
                         ("age", 30)):
        assert not (await run(db_session, uid, "update_profile",
                              {"field": field, "value": value})).get("error")
    before = await me(c)

    refused = [
        ("age", 12), ("age", 101), ("age", 28.5), ("age", "twenty"),
        ("gender", "unknown"), ("gender", "Male"),
        ("diet", "vegan"), ("diet", "non-veg"),
        ("height_cm", 0), ("height_cm", 300),
        # A person, not the column: "five nine" misread as 5.9 is refused.
        ("height_cm", 5.9), ("height_cm", 260),
        # An exact date is an age too, held to the same 13 to 100.
        ("dob", "not a date"), ("dob", "2030-05-01"), ("dob", f"{this_year() - 5}-06-01"),
        ("dob", "1900-01-01"),
        # Not the model's to set: the app owns the first-run flag and the clock.
        ("onboarding_done_at", "2026-08-20T10:00:00+05:30"), ("timezone", "UTC"),
    ]
    for field, value in refused:
        out = await run(db_session, uid, "update_profile", {"field": field, "value": value})
        assert out.get("error"), (field, value, out)
        assert C.from_tool("update_profile", {}, out) == [], "a refusal earns no card"
    after = await me(c)
    assert {k: after[k] for k in ("gender", "diet", "height_cm", "dob", "timezone",
                                  "onboarding_done_at")} == \
        {k: before[k] for k in ("gender", "diet", "height_cm", "dob", "timezone",
                                "onboarding_done_at")}


async def test_patch_accepts_gender_and_diet_to_their_checks_and_null_clears(fresh):
    _, c = fresh
    assert (await me(c))["gender"] is None and (await me(c))["diet"] is None, \
        "unanswered is absent — never a default gender, never 'any'"
    assert (await c.patch("/users/me", json={"gender": "x"})).status_code == 422
    assert (await c.patch("/users/me", json={"diet": "vegan"})).status_code == 422
    r = await c.patch("/users/me", json={"gender": "female", "diet": "veg"})
    assert r.status_code == 200 and (r.json()["gender"], r.json()["diet"]) == ("female", "veg")
    r = await c.patch("/users/me", json={"gender": None, "diet": None})
    assert (r.json()["gender"], r.json()["diet"]) == (None, None)
    # Every field clears but the name, which changes and is never removed —
    # a null for it is a 422, not the NOT NULL column's 500.
    r = await c.patch("/users/me", json={"display_name": None})
    assert r.status_code == 422, r.text
    assert (await c.patch("/users/me", json={"dob": "2030-05-01"})).status_code == 422
    assert ((await me(c))["display_name"], (await me(c))["dob"]) == ("New person", None)


# ─── 2 · the weight is a weigh-in, and it can be approximate ────────────────

async def test_log_day_writes_a_weigh_in_and_keeps_the_days_copy(fresh, db_session):
    uid, c = fresh
    out = await run(db_session, uid, "log_day", {"local_day": DAY, "weight_kg": 71.4})
    assert out["weigh_in"]["estimated"] is False, "a reading is not a guess"
    [w] = (await c.get("/weigh-ins")).json()
    assert (float(w["weight_kg"]), w["estimated"]) == (71.4, False)
    days = (await c.get("/deck", params={"to": DAY})).json()["diet"]["days"]
    assert [float(d["weight_kg"]) for d in days if d["local_day"] == DAY] == [71.4]
    [card] = C.from_tool("log_day", {}, out)
    assert not any(f.guessed for f in card.fields)


async def test_an_exact_reading_the_same_day_clears_the_estimate(fresh, db_session):
    uid, c = fresh
    await run(db_session, uid, "log_day",
              {"local_day": DAY, "weight_kg": 72, "approximate": True})
    assert [w["estimated"] for w in (await c.get("/weigh-ins")).json()] == [True]

    # Through the agent: the same day, a reading.
    await run(db_session, uid, "log_day", {"local_day": DAY, "weight_kg": 71.8})
    rows = (await c.get("/weigh-ins")).json()
    assert [(float(w["weight_kg"]), w["estimated"]) for w in rows] == [(71.8, False)], \
        "one row a day, replaced, its flag cleared"

    # Through the route: a guess again, then a reading.
    other = "2026-08-21"
    for weight, guess in ((70.5, True), (70.2, False)):
        r = await c.post("/weigh-ins", json={"id": ulid(), "local_day": other,
                                             "weight_kg": weight, "estimated": guess})
        assert r.status_code in (200, 201) and r.json()["estimated"] is guess
    rows = [w for w in (await c.get("/weigh-ins")).json() if w["local_day"] == other]
    assert [(float(w["weight_kg"]), w["estimated"]) for w in rows] == [(70.2, False)]


async def test_a_weigh_in_with_no_flag_is_exact(fresh):
    """Builds that predate the flag still post weigh-ins."""
    _, c = fresh
    r = await c.post("/weigh-ins", json={"id": ulid(), "local_day": DAY, "weight_kg": 80})
    assert r.status_code == 201 and r.json()["estimated"] is False


async def test_diet_report_says_when_the_latest_weight_is_a_guess(fresh, db_session):
    uid, _ = fresh
    report = {"to": DAY, "fields": ["weight"]}
    assert (await run(db_session, uid, "diet_report", report))["weight"]["latest_estimated"] \
        is None, "no weigh-in is unknown, not exact"
    await run(db_session, uid, "log_day", {"local_day": DAY, "weight_kg": 72,
                                           "approximate": True})
    weight = (await run(db_session, uid, "diet_report", report))["weight"]
    assert (weight["latest_kg"], weight["latest_estimated"]) == (72.0, True)
    await run(db_session, uid, "log_day", {"local_day": DAY, "weight_kg": 72.3})
    weight = (await run(db_session, uid, "diet_report", report))["weight"]
    assert (weight["latest_kg"], weight["latest_estimated"]) == (72.3, False)


# ─── 3 · habits: a name already tracked is reused ────────────────────────────

async def test_a_habit_already_tracked_is_reused_never_refused(fresh, db_session):
    uid, c = fresh
    first = await run(db_session, uid, "manage_habit", {"name": "Gym", "direction": "build"})
    assert not first.get("error") and "already_tracked" not in first
    assert C.from_tool("manage_habit", {}, first)[0].lede == "Gym · tracking build"

    for said in ({"name": "Gym", "direction": "build"}, {"name": "gym"}):
        again = await run(db_session, uid, "manage_habit", said)
        assert not again.get("error"), again
        assert again["habit_id"] == first["habit_id"] and again["already_tracked"] is True
        [card] = C.from_tool("manage_habit", said, again)
        assert card.kind == "confirm" and card.row_id == first["habit_id"]
        assert card.lede == "Gym · already tracked", "no write happened, and the card says so"
    assert [h["name"] for h in (await c.get("/habits")).json()] == ["Gym"]

    # A direction beside a name flips nothing — a name is "start one" — and
    # the result says what was left; changing it is habit_id.
    other = await run(db_session, uid, "manage_habit", {"name": "GYM", "direction": "break"})
    assert (other["habit_id"], other["direction"]) == (first["habit_id"], "build")
    assert "left as it is" in other["unchanged"]
    assert C.from_tool("manage_habit", {}, other)[0].lede == "Gym · already tracked"
    flipped = await run(db_session, uid, "manage_habit", {"habit_id": "Gym", "direction": "break"})
    assert flipped["direction"] == "break" and "already_tracked" not in flipped
    assert [(h["name"], h["direction"]) for h in (await c.get("/habits")).json()] == \
        [("Gym", "break")]


async def test_in_the_chat_a_habit_named_again_is_left_as_it_was(fresh, fake):
    """'cigarettes bhi track karo' with Cigarettes tracked to break: the
    direction the model put beside the name changes nothing, and the card says
    it was already there rather than claiming a habit started."""
    _, c = fresh
    r = await c.post("/habits", json={"id": ulid(), "name": "Cigarettes", "direction": "break"})
    assert r.status_code == 201, r.text
    fake(_msg(calls=[("manage_habit", {"name": "Cigarettes", "direction": "build"})]),
         _msg("Already tracking it."))
    body = (await c.post("/chat", json={"message": "cigarettes bhi track karo",
                                        "local_day": DAY})).json()
    [card] = [x for x in body["cards"] if x["kind"] == "confirm"]
    assert (card["lede"], card["row_id"]) == ("Cigarettes · already tracked", r.json()["id"])
    assert [(h["name"], h["direction"]) for h in (await c.get("/habits")).json()] == \
        [("Cigarettes", "break")]


async def test_a_habit_keeps_no_frequency(client):
    """'Gym every day' is a build habit named Gym: habits.md decided against
    per-habit targets, so there is nowhere to store 'every day'."""
    columns = set(Habit.__table__.columns.keys())
    assert not columns & {"frequency", "per_week", "target", "times", "period"}
    props = T.BY_NAME["manage_habit"]["schema"]["properties"]
    assert not set(props) & {"frequency", "per_week", "target", "times", "period"}


# ─── 4 · the flag: finished or skipped, set once ────────────────────────────

async def test_deck_sends_the_flag_and_no_steps(fresh):
    _, c = fresh
    onboarding = (await c.get("/deck", params={"to": DAY})).json()["onboarding"]
    assert onboarding == {"done_at": None, "steps": []}
    # Rows that used to tick Getting started's steps tick nothing now.
    assert (await make_transaction(c)).status_code == 201
    assert (await c.patch("/users/me", json={"savings_target_paise": 1500000})
            ).status_code == 200
    onboarding = (await c.get("/deck", params={"to": DAY})).json()["onboarding"]
    assert onboarding == {"done_at": None, "steps": []}


async def test_finished_is_stored_once_and_stays(fresh):
    """Get started, Skip or Skip for now: the client sets it, and the first run
    never returns."""
    _, c = fresh
    at = "2026-08-20T10:00:00+05:30"
    assert (await c.patch("/users/me", json={"onboarding_done_at": at})).status_code == 200
    onboarding = (await c.get("/deck", params={"to": DAY})).json()["onboarding"]
    assert onboarding["done_at"] is not None and onboarding["steps"] == []

    # Another profile edit, and an explicit null, both leave it finished.
    await c.patch("/users/me", json={"savings_target_paise": 500000})
    r = await c.patch("/users/me", json={"onboarding_done_at": None})
    assert r.status_code == 200 and r.json()["onboarding_done_at"] is not None
    onboarding = (await c.get("/deck", params={"to": DAY})).json()["onboarding"]
    assert onboarding["done_at"] is not None and onboarding["steps"] == []


def _migration():
    spec = importlib.util.spec_from_file_location(
        "mig", Path(__file__).parent.parent / "alembic/versions/20d535354209_onboarding_goals.py")
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    return mig


async def test_the_backfill_marks_every_account_with_a_row_and_leaves_empty_ones(
        client, db_session, fake):
    """A fresh test database has nothing to migrate, so the migration's own
    function runs against accounts seeded through the API — one per table, so
    each table is seen to count on its own — and is rolled back afterwards."""
    mig = _migration()

    async def chat(c):
        fake(_msg("ok"))
        return await c.post("/chat", json={"message": "hi", "local_day": DAY})

    async def soft_deleted_payment(c):
        pay = (await make_transaction(c)).json()
        return await c.delete(f"/transactions/{pay['id']}")

    writes = {
        "transactions": soft_deleted_payment,
        "meal_logs": make_meal,
        "tasks": lambda c: c.post("/tasks", json={"id": ulid(), "title": "Book the venue",
                                                  "source": "self"}),
        "habits": lambda c: c.post("/habits", json={"id": ulid(), "name": "Gym",
                                                    "direction": "build"}),
        "commitments": lambda c: c.post("/commitments", json={
            "id": ulid(), "name": "Rent", "category": "Rent", "amount_paise": 800000}),
        "weigh_ins": lambda c: c.post("/weigh-ins", json={"id": ulid(), "local_day": DAY,
                                                          "weight_kg": 72}),
        "memories": lambda c: c.post("/memories", json={
            "id": ulid(), "slug": "nights", "kind": "identity", "text": "Works nights"}),
        "messages": chat,
    }
    assert set(writes) == set(mig.LIVED_IN)
    used: dict[str, str] = {}
    for table, write in writes.items():
        async with signed_in(db_session) as (uid, c):
            r = await write(c)
            assert r.status_code in (200, 201, 204), (table, r.text)
            used[table] = uid

    async with signed_in(db_session) as (empty, c):
        assert (await c.get("/deck", params={"to": DAY})).status_code == 200
    at = datetime(2026, 8, 20, 4, 30, tzinfo=UTC)
    async with signed_in(db_session) as (done, c):
        await c.patch("/users/me", json={"onboarding_done_at": at.isoformat()})
        await make_meal(c)

    await db_session.run_sync(lambda s: mig.backfill(s.connection()))
    flags = dict((await db_session.execute(
        text("SELECT id, onboarding_done_at FROM users WHERE id = ANY(:ids)"),
        {"ids": [*used.values(), empty, done]})).all())
    await db_session.rollback()  # checked, not kept

    assert [t for t, uid in used.items() if flags[uid] is None] == [], \
        "every account with a row, deleted or not, is past its first run"
    assert flags[empty] is None, "an account with nothing in it still sees the first run"
    assert flags[done] == at, "a flag already set keeps its moment"


# ─── 5 · the chat agent reads the answers ────────────────────────────────────

def section(system: str, heading: str) -> str:
    return system.split(heading, 1)[1].split("\n## ", 1)[0]


async def test_who_they_are_carries_the_body_the_place_and_the_diet(fresh, db_session):
    uid, c = fresh
    r = await c.patch("/users/me", json={
        "gender": "male", "dob": "1998-01-01", "height_cm": 175.3, "city": "Delhi",
        "diet": "eggetarian", "weight_target_kg": 67})
    assert r.status_code == 200, r.text
    await c.post("/weigh-ins", json={"id": ulid(), "local_day": DAY, "weight_kg": 72,
                                     "estimated": True})
    await c.post("/memories", json={"id": ulid(), "slug": "no-beef", "kind": "preference",
                                    "text": "Never eats beef"})

    system = await P.build(db_session, uid)
    who = section(system, "## Who they are")
    for fact in ("gender: male", "born 1998", "height 175.3 cm", "approximately 72 kg",
                 "lives in Delhi", "diet: vegetarian, and eats eggs", "Never eats beef"):
        assert fact in who, fact
    assert "weight 67 kg" in section(system, "## Their targets")

    # An exact reading replaces the guess, and the word goes with it.
    await c.post("/weigh-ins", json={"id": ulid(), "local_day": DAY, "weight_kg": 71.6})
    who = section(await P.build(db_session, uid), "## Who they are")
    assert "weighs 71.6 kg" in who and "approximately" not in who


async def test_nothing_unanswered_reaches_the_prompt(fresh, db_session):
    uid, _ = fresh
    system = await P.build(db_session, uid)
    assert section(system, "## Who they are").strip() == "- (nothing recorded yet)"
    assert section(system, "## Their targets").strip() == "(none set)"


async def test_the_identity_line_is_goals_not_a_ledger(fresh, db_session):
    uid, _ = fresh
    system = await P.build(db_session, uid)
    assert system.startswith(
        "You are Spica — New person's personal agent for taking control of their money, "
        "health, habits and time, toward the goals they set. You log what they say and "
        "answer from their own data. You are not a chatbot with opinions.\n")
    assert "ledger with a voice" not in system


async def test_build_reads_no_date_and_gives_a_birth_year_not_an_age(fresh, db_session,
                                                                     monkeypatch):
    """An age depends on today, and nothing in the cached prefix may
    (spec/done/prompt-layout.md). The year is given; the model works the age
    out from the `[now]` line."""
    uid, c = fresh
    await c.patch("/users/me", json={"dob": "1998-01-01"})
    assert list(inspect.signature(P.build).parameters) == ["session", "user"]

    class NoToday(date):
        @classmethod
        def today(cls):
            raise AssertionError("build() read today's date")
    monkeypatch.setattr(P, "date", NoToday)
    system = await P.build(db_session, uid)
    assert "born 1998" in system
    assert "28 years" not in system and "age" not in section(system, "## Who they are")


# ─── 6 · Home's meal plan reads them ────────────────────────────────────────

class PlanModel:
    """Answers the planner and records what it was sent."""

    def __init__(self):
        self.calls, self.payload, self.instructions = 0, None, None
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **kw):
        self.calls += 1
        self.payload, self.instructions = json.loads(kw["input"]), kw["instructions"]
        answer = {"meals": [{"slot": "Breakfast", "dish_id": None, "name": "Besan chilla",
                             "kcal": 380, "protein_g": 20, "carbs_g": 30, "fat_g": 12,
                             "why": "20 g protein"}],
                  "workout": {"kind": "rest", "name": "Rest", "why": "a heavy week"}}
        return SimpleNamespace(output=[], output_text=json.dumps(answer),
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1))


async def test_the_meal_plan_is_given_the_diet_the_memories_and_the_body(fresh, monkeypatch):
    from app import images
    from app.agent import plan

    async def no_commons(_):
        return {}
    plan._cache.clear()
    monkeypatch.setattr(images, "_query", no_commons)
    model = PlanModel()
    monkeypatch.setattr("app.llm.client", lambda: model)
    monkeypatch.setattr("app.llm.model", lambda: "fake-model")

    _, c = fresh
    await c.patch("/users/me", json={"gender": "female", "dob": "1996-01-01",
                                     "height_cm": 162.5, "city": "Pune", "diet": "veg"})
    await c.post("/weigh-ins", json={"id": ulid(), "local_day": DAY, "weight_kg": 58,
                                     "estimated": True})
    await c.post("/memories", json={"id": ulid(), "slug": "no-mushrooms",
                                    "kind": "preference", "text": "Never eats mushrooms"})

    async def get_plan():
        r = await c.get("/plan/today", params={"local_day": DAY, "local_time": "08:00"})
        assert r.status_code == 200, r.text
        return r.json()

    assert (await get_plan())["available"]
    person = model.payload["person"]
    assert person == {
        "diet": "veg", "city": "Pune", "gender": "female", "dob": "1996-01-01",
        "height_cm": 162.5, "weight_kg": 58.0, "weight_estimated": True,
        "memories": [{"kind": "preference", "text": "Never eats mushrooms"}],
    }
    assert "Never plan a food the person does not eat" in model.instructions

    # A diet changed on Profile is a different plan, not today's cached one.
    await c.patch("/users/me", json={"diet": "eggetarian"})
    await get_plan()
    assert model.calls == 2 and model.payload["person"]["diet"] == "eggetarian"

    # What the planner is not given is not a new plan: the first-run flag, the
    # step target and the timezone all touch `users`, and none is a billed call.
    r = await c.patch("/users/me", json={"onboarding_done_at": "2026-08-20T10:00:00+05:30",
                                         "step_target": 9000, "timezone": "Asia/Kolkata"})
    assert r.status_code == 200, r.text
    await get_plan()
    assert model.calls == 2


async def test_an_unanswered_person_is_null_in_the_plan_never_a_default(fresh, monkeypatch):
    from app import images
    from app.agent import plan

    async def no_commons(_):
        return {}
    plan._cache.clear()
    monkeypatch.setattr(images, "_query", no_commons)
    model = PlanModel()
    monkeypatch.setattr("app.llm.client", lambda: model)
    monkeypatch.setattr("app.llm.model", lambda: "fake-model")

    _, c = fresh
    r = await c.get("/plan/today", params={"local_day": DAY, "local_time": "08:00"})
    assert r.status_code == 200, r.text
    assert model.payload["person"] == {
        "diet": None, "city": None, "gender": None, "dob": None, "height_cm": None,
        "weight_kg": None, "weight_estimated": None, "memories": []}


# ─── 7 · the onboarding agent: POST /onboarding/turn ───────────────────────

ABOUT = [
    ("update_profile", {"field": "display_name", "value": "Sonu"}),
    ("update_profile", {"field": "gender", "value": "male"}),
    ("update_profile", {"field": "age", "value": 28}),
    ("update_profile", {"field": "height_cm", "value": 175.26}),
    ("log_day", {"local_day": DAY, "weight_kg": 72, "approximate": True}),
]
SAID = "Sonu, male, 28. Five nine, around 72 kilo"


async def answer(c, text=SAID, question="about"):
    return await c.post("/onboarding/turn",
                        json={"question": question, "text": text, "local_day": DAY})


async def count(db_session, table: str, uid: str) -> int:
    return (await db_session.execute(
        text(f"SELECT count(*) FROM {table} WHERE user_id = :u"), {"u": uid})).scalar()


async def test_a_turn_writes_the_first_answer_with_one_card_per_write(fresh, fake, db_session):
    uid, c = fresh
    fake(_msg(calls=ABOUT), _msg(calls=[("next_question", {"status": "answered"})]),
         _msg("Got it."))
    r = await answer(c)
    assert r.status_code == 200, r.text
    body = r.json()

    row = await me(c)
    assert (row["display_name"], row["gender"]) == ("Sonu", "male")
    assert row["dob"] == date(this_year() - 28, 1, 1).isoformat()
    assert float(row["height_cm"]) == 175.3
    [w] = (await c.get("/weigh-ins")).json()
    assert (float(w["weight_kg"]), w["estimated"]) == (72.0, True)

    cards = body["cards"]
    assert len(cards) == 5 and {x["kind"] for x in cards} == {"confirm"}, cards
    assert [x["source"] for x in cards] == ["profile"] * 4 + ["body"]
    assert [x["lede"] for x in cards[:3]] == ["Name → Sonu", "Gender → Male", "Age → 28 years"]
    assert [f["guessed"] for f in cards[4]["fields"] if f["key"] == "weight_kg"] == [True]
    # Moved on: the screen asks the next question, so what the model said
    # beside that is not a second voice over it.
    assert (body["next"], body["reply"]) == (True, None)

    # The weight's card holds the weigh-in — the row screen 4, Profile and the
    # BMI read — so Undo on it is the weigh-in's own delete, and the day's
    # copy of the reading goes with it.
    assert cards[4]["row_id"] == w["id"], "the weigh-in, not the day"
    day_weight = text("SELECT weight_kg FROM days WHERE user_id = :u AND local_day = :d")
    params = {"u": uid, "d": date.fromisoformat(DAY)}
    assert (await db_session.execute(day_weight, params)).scalar() == 72.0
    assert (await c.delete(f"/weigh-ins/{cards[4]['row_id']}")).status_code == 204
    assert (await c.get("/weigh-ins")).json() == []
    assert (await db_session.execute(day_weight, params)).scalar() is None


async def test_a_turn_with_no_write_and_no_next_question_returns_the_reply(fresh, fake,
                                                                          db_session):
    uid, c = fresh
    before = await me(c)

    fake(_msg("Say that again?"))
    body = (await answer(c, "hmm brr")).json()
    assert body == {"cards": [], "reply": "Say that again?", "next": False}

    # A skip writes nothing and moves on, with no line of its own.
    fake(_msg(calls=[("next_question", {"status": "skipped"})]), _msg(""))
    body = (await answer(c, "nahi batana")).json()
    assert body == {"cards": [], "reply": None, "next": True}

    # A follow-up: what was given is written, and the question stays open.
    fake(_msg(calls=[("update_profile", {"field": "display_name", "value": "Sonu"})]),
         _msg("And your height?"))
    body = (await answer(c, "Sonu")).json()
    assert (len(body["cards"]), body["reply"], body["next"]) == (1, "And your height?", False)

    after = await me(c)
    assert {k: after[k] for k in ("gender", "dob", "height_cm")} == \
        {k: before[k] for k in ("gender", "dob", "height_cm")}
    assert await count(db_session, "weigh_ins", uid) == 0


async def test_a_write_that_fails_mid_turn_leaves_nothing_from_that_turn(fresh, fake,
                                                                        monkeypatch):
    """The routes commit for themselves; inside a turn those commits are
    savepoints, and the turn commits once. A tool that raises after two
    writes leaves neither."""
    uid, c = fresh

    async def boom(*a, **kw):
        raise RuntimeError("the weigh-in broke")
    monkeypatch.setitem(T.BY_NAME["log_day"], "fn", boom)
    fake(_msg(calls=[("update_profile", {"field": "display_name", "value": "Sonu"}),
                     ("update_profile", {"field": "city", "value": "Delhi"}),
                     ("log_day", {"local_day": DAY, "weight_kg": 72})]))
    with pytest.raises(RuntimeError):
        await answer(c)
    row = await me(c)
    assert (row["display_name"], row["city"]) == ("New person", None)


async def test_a_failed_model_call_writes_nothing_and_says_so(fresh, fake, db_session):
    """Round one wrote; round two's call timed out. The answer is still in
    the bar to send again, so nothing of it may be kept."""
    uid, c = fresh
    llm = fake(_msg(calls=ABOUT[:2]))
    create = llm.responses.create

    async def second_call_times_out(**kw):
        if llm.sent:
            raise TimeoutError("the model timed out")
        return await create(**kw)
    llm.responses.create = second_call_times_out
    r = await answer(c)
    assert r.status_code == 502, r.text
    assert "nothing was written" in r.json()["detail"]
    row = await me(c)
    assert (row["display_name"], row["gender"]) == ("New person", None)

    # The provider refusing the prompt is a failure here too — there is no
    # agent line for it on this screen.
    async def refused(**kw):
        raise RuntimeError("Error code: 400 — invalid_prompt")
    llm.responses.create = refused
    assert (await answer(c)).status_code == 502

    # Both calls were billed, so both count against the day.
    assert (await db_session.execute(text(
        "SELECT onboarding_turns FROM users WHERE id = :u"), {"u": uid})).scalar() == 2


async def test_a_refused_write_undoes_itself_and_the_rest_of_the_answer_stands(fresh, fake):
    """A refusal is data the model reads, as in the chat: its savepoint is
    undone, the turn goes on, and the reply can say what was refused."""
    uid, c = fresh
    fake(_msg(calls=[("update_profile", {"field": "display_name", "value": "Sonu"}),
                     ("update_profile", {"field": "age", "value": 12})]),
         _msg("Ages start at 13 — how old are you?"))
    body = (await answer(c)).json()
    assert [x["lede"] for x in body["cards"]] == ["Name → Sonu"]
    assert body["reply"] == "Ages start at 13 — how old are you?" and body["next"] is False
    row = await me(c)
    assert (row["display_name"], row["dob"]) == ("Sonu", None)


async def test_the_same_answer_sent_twice_writes_the_same_rows_once(fresh, fake, db_session):
    """No replay store: every tool the agent writes through is safe to
    repeat — the profile and the day's weigh-in overwrite, a habit and a
    memory are reused by name and slug, and save_task refuses a twin."""
    uid, c = fresh
    calls = [*ABOUT,
             ("update_profile", {"field": "city", "value": "Delhi"}),
             ("manage_habit", {"name": "Gym", "direction": "build"}),
             ("remember", {"slug": "never-eats-beef", "kind": "preference",
                           "text_": "Never eats beef"}),
             ("save_task", {"title": "Book the venue"}),
             ("next_question", {"status": "answered"})]
    fake(_msg(calls=calls), _msg(""), _msg(calls=calls), _msg(""))
    first = (await answer(c)).json()
    second = (await answer(c)).json()

    assert len(first["cards"]) == len(second["cards"]) == 9
    assert [x["row_id"] for x in first["cards"]] == [x["row_id"] for x in second["cards"]]
    for table in ("weigh_ins", "habits", "memories", "tasks"):
        assert await count(db_session, table, uid) == 1, table
    row = await me(c)
    assert (row["display_name"], row["city"]) == ("Sonu", "Delhi")
    assert row["dob"] == date(this_year() - 28, 1, 1).isoformat()


async def test_the_turn_is_refused_once_the_first_run_is_done(fresh, fake):
    _, c = fresh
    await c.patch("/users/me", json={"onboarding_done_at": "2026-08-20T10:00:00+05:30"})
    llm = fake(_msg(calls=ABOUT))
    r = await answer(c)
    assert r.status_code == 409, r.text
    assert llm.sent == [], "no model call once the questions are over"
    assert (await me(c))["display_name"] == "New person"


async def test_past_the_days_cap_the_turn_is_refused_and_no_model_is_called(
        fresh, fake, db_session, monkeypatch):
    from app.config import settings
    uid, c = fresh
    monkeypatch.setattr(settings(), "onboarding_turn_limit", 2)
    llm = fake(*[_msg("Say that again?") for _ in range(4)])
    assert [(await answer(c, "hmm")).status_code for _ in range(3)] == [200, 200, 429]
    assert len(llm.sent) == 2, "the refused turn reached no model"

    # A new day where they are starts a new count.
    await db_session.execute(text(
        "UPDATE users SET onboarding_turns_day = onboarding_turns_day - 1 WHERE id = :u"),
        {"u": uid})
    await db_session.commit()
    assert (await answer(c, "hmm")).status_code == 200
    assert (await db_session.execute(text(
        "SELECT onboarding_turns FROM users WHERE id = :u"), {"u": uid})).scalar() == 1

    # Nought is a switch that stops every turn, a new day's first one too.
    monkeypatch.setattr(settings(), "onboarding_turn_limit", 0)
    await db_session.execute(text(
        "UPDATE users SET onboarding_turns_day = onboarding_turns_day - 1 WHERE id = :u"),
        {"u": uid})
    await db_session.commit()
    sent = len(llm.sent)
    assert (await answer(c, "hmm")).status_code == 429
    assert len(llm.sent) == sent, "no model call at a cap of nought"


async def test_no_turn_reaches_the_thread_and_no_payment_or_meal_is_written(fresh, fake,
                                                                           db_session):
    """Its six tools are all it can run: a payment or a meal it reaches for is
    a tool it does not have, and nothing lands in the conversation."""
    uid, c = fresh
    llm = fake(_msg(calls=[
        ("log_payment", {"amount_paise": 2000, "direction": "debit", "kind": "expense",
                         "category": "Other", "description": "chai", "local_day": DAY}),
        ("log_meal", {"text_said": "dal chawal", "meal_type": "Lunch", "local_day": DAY}),
        ("update_profile", {"field": "city", "value": "Delhi"})]), _msg(""))
    body = (await answer(c, "Delhi. chai 20, lunch mein dal chawal", "place")).json()
    assert [x["lede"] for x in body["cards"]] == ["City → Delhi"]

    assert [t["name"] for t in llm.sent[0]["tools"]] == [
        "update_profile", "log_day", "remember", "manage_habit", "save_task", "next_question"]
    outputs = [i["output"] for i in llm.sent[1]["input"]
               if isinstance(i, dict) and i.get("type") == "function_call_output"]
    assert "no tool called 'log_payment'" in outputs[0]
    assert "no tool called 'log_meal'" in outputs[1]
    for table in ("transactions", "meal_logs", "messages", "conversations"):
        assert await count(db_session, table, uid) == 0, table


async def test_what_the_first_run_remembers_is_the_persons_own_word(fresh, fake, db_session):
    """Source `user`, confirmed — the question asked, the card showed it
    back. The chat agent's own memories stay `cortex`, unconfirmed."""
    uid, c = fresh
    fake(_msg(calls=[("remember", {"slug": "never-eats-beef", "kind": "preference",
                                   "text_": "Never eats beef"})]), _msg(""))
    body = (await answer(c, "Delhi, non-veg, no beef", "place")).json()
    [card] = body["cards"]
    assert (card["source"], card["lede"]) == ("memory", "Remembered")
    [m] = (await c.get("/memories")).json()
    assert (m["slug"], m["source"]) == ("never-eats-beef", "user")
    assert m["confirmed_at"] is not None

    await run(db_session, uid, "remember", {"slug": "works-nights", "kind": "identity",
                                            "text_": "Works nights"})
    chat = next(x for x in (await c.get("/memories")).json() if x["slug"] == "works-nights")
    assert (chat["source"], chat["confirmed_at"]) == ("cortex", None)


async def test_next_question_belongs_to_the_onboarding_agent_alone(client, fake):
    assert "next_question" not in T.BY_NAME
    assert "next_question" not in [s["name"] for s in T.schemas()]
    llm = fake(_msg("ok"))
    await client.post("/chat", json={"message": "hi", "local_day": DAY})
    assert "next_question" not in [t["name"] for t in llm.sent[0]["tools"]]
    r = await client.post("/chat/act", json={"name": "next_question",
                                             "args": {"status": "answered"}})
    assert r.status_code == 404


async def test_the_turn_tells_the_model_the_question_and_what_is_known(fresh, fake):
    """Read live each turn, so coming back mid-flow never asks again — and the
    prompt and tools ahead of it are the same for every account."""
    from app.agent import onboarding as O
    _, c = fresh
    fake(_msg(calls=ABOUT), _msg(""))
    await answer(c)
    llm = fake(_msg(""))
    await answer(c, "lose 5 kilo", "health")

    sent = llm.sent[0]
    assert sent["instructions"] == O.SKILL_FILE.read_text()
    assert sent["prompt_cache_key"] == "cortex-onboarding"
    said = sent["input"][0]["content"]
    assert said.startswith(f"[today] {DAY} (Thursday)\n[question] health\n[already known]\n")
    for fact in ("- name: Sonu", "- gender: male", f"- born {this_year() - 28}",
                 "- height 175.3 cm", "- weighs approximately 72 kg"):
        assert fact in said, fact
    assert said.endswith("\n\nlose 5 kilo")


async def test_a_new_account_is_known_by_its_name_alone(fresh, fake):
    _, c = fresh
    llm = fake(_msg("Say that again?"))
    await answer(c, "?")
    said = llm.sent[0]["input"][0]["content"]
    assert "[already known]\n- name: New person\n\n?" in said


async def test_lose_five_counts_from_the_weigh_in_and_with_none_is_remembered(
        fresh, fake, db_session):
    """*"Lose 5 kilo"*: with a weigh-in of 72 the target is the weight to
    reach, 67; with none there is nothing to count from, so the goal is kept
    in their words and no target is invented. The subtraction is the model's
    — `n2n_eval` holds it to it — so here the server is held to what it tells
    the model and to what lands."""
    _, c = fresh
    await c.post("/weigh-ins", json={"id": ulid(), "local_day": DAY, "weight_kg": 72})
    llm = fake(_msg(calls=[("update_profile", {"field": "weight_target_kg", "value": 67}),
                           ("next_question", {"status": "answered"})]), _msg(""))
    body = (await answer(c, "lose 5 kilo", "health")).json()
    assert "- weighs 72 kg (their latest weigh-in)" in llm.sent[0]["input"][0]["content"]
    assert ([x["lede"] for x in body["cards"]], body["next"]) == (["Weight target → 67 kg"], True)
    assert float((await me(c))["weight_target_kg"]) == 67.0
    assert (await c.get("/memories")).json() == [], "the target is the goal — no sentence beside it"

    async with signed_in(db_session) as (_, unweighed):
        llm = fake(_msg(calls=[("remember", {"slug": "goal-lose-5-kg", "kind": "project",
                                             "text_": "Lose 5 kg"}),
                               ("next_question", {"status": "answered"})]), _msg(""))
        body = (await answer(unweighed, "lose 5 kilo", "health")).json()
        assert "weighs" not in llm.sent[0]["input"][0]["content"], "no weight to count from"
        assert [(x["source"], x["lede"]) for x in body["cards"]] == [("memory", "Remembered")]
        assert (await me(unweighed))["weight_target_kg"] is None, "no target invented"
        [m] = (await unweighed.get("/memories")).json()
        assert (m["kind"], m["text"], m["source"]) == ("project", "Lose 5 kg", "user")


async def test_two_answers_at_once_run_one_after_the_other(fresh, fake):
    """An answer resent while the first is still with the model: the second
    turn waits for the first to land — so the two cannot take the same rows
    in opposite orders and deadlock — and then reads what it wrote."""
    import asyncio
    _, c = fresh
    city = [("update_profile", {"field": "city", "value": "Delhi"})]
    llm = fake(_msg(calls=city), _msg(""), _msg(calls=city), _msg(""))
    create, calls = llm.responses.create, []

    async def first_is_slow(**kw):
        calls.append("in")
        if len(calls) == 1:
            await asyncio.sleep(0.3)  # the first answer, still with the model
        out = await create(**kw)
        calls.append("out")
        return out
    llm.responses.create = first_is_slow
    first, second = await asyncio.gather(answer(c, "Delhi", "place"),
                                         answer(c, "Delhi", "place"))
    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert calls == ["in", "out"] * 4, "no model call of the second began inside the first"
    assert "- lives in Delhi" in llm.sent[2]["input"][0]["content"], \
        "the second read what the first wrote"
