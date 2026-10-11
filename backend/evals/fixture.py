"""
The lived-in week every case starts from — one fresh account per case.

A read can only be checked against data, and the turns that went wrong were
mostly reads: what is left, what is due, what was eaten. So every account is
given a week the questions can be asked of — payments in five categories, a
fixed cost, a salary, a lending; three meals; two habits with ticks; tasks in
three projects, one late and one done; a pantry; a weigh-in and a night's
sleep; two memories; a place.

Everything goes through the API the app uses, so a seeded row is a row the app
could have written. Only the account and its session are made in SQL, because
signing in needs Google. The library the sentences match against — foods, a
portion word, two public dishes — is shared, and seeded once per run.

Dates are relative to the run's today, so "kal" and "is hafte" mean the same
thing on any day the eval is run. Today itself is left to the conversation — it
logs the day as a person would — except one payment a notification brought in
this morning, filed as Other and unsure, for the doubtful-payments question.
Figures a case checks are computed from these rows with SQL at check time,
never written into the case.

The first run's cases start emptier still: an account just signed in, with the
name Google gave and nothing else (`new_account`), and only what a case's
`seed` puts there through the API (`SEEDS`).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import text

IST = ZoneInfo("Asia/Kolkata")

# ─── the shared library, once per run ────────────────────────────────────────

FOODS = [
    # id, name, aliases, unit, grams_per_unit, kcal, protein, carbs, fat (per 100 g)
    ("n2n-atta", "Atta (whole wheat)", ["atta", "roti", "chapati"], "g", None, 340, 12, 72, 2),
    ("n2n-dal", "Dal (cooked)", ["dal", "daal"], "g", None, 116, 9, 20, 0.4),
    ("n2n-egg", "Egg", ["egg", "eggs", "anda", "ande", "boiled egg"], "piece", 50,
     155, 13, 1.1, 11),
    ("n2n-paneer", "Paneer", ["paneer"], "g", None, 265, 18, 3.4, 21),
    ("n2n-rice", "Rice (cooked)", ["rice", "chawal"], "g", None, 130, 2.7, 28, 0.3),
    ("n2n-soya", "Soya chunks", ["soya", "soya chunks", "nutrela"], "g", None, 345, 52, 33, 0.5),
]
DISHES = [
    # id, name, aliases, serving, protein, kcal, meal type, minutes
    ("n2n-bhurji", "Paneer bhurji", ["bhurji"], "1 plate", 24, 320, "Dinner", 15),
    ("n2n-whey", "Whey shake", ["protein shake"], "1 glass", 24, 120, "Snack", 2),
    ("n2n-soya-keema", "Soya keema", ["soya keema"], "1 bowl", 30, 360, "Dinner", 20),
    ("n2n-egg-bhurji", "Egg bhurji", ["anda bhurji"], "1 plate", 18, 280, "Breakfast", 10),
]


async def seed_library(session) -> None:
    for fid, name, aliases, unit, gpu, kcal, p, c, f in FOODS:
        await session.execute(text(
            "INSERT INTO foods (id, name, aliases, unit, grams_per_unit, kcal_100g, "
            "protein_g_100g, carbs_g_100g, fat_g_100g, created_at, updated_at) VALUES "
            "(:i, :n, :a, :u, :g, :k, :p, :c, :f, now(), now())"),
            {"i": fid, "n": name, "a": aliases, "u": unit, "g": gpu, "k": kcal, "p": p,
             "c": c, "f": f})
    await session.execute(text("INSERT INTO measures (id, phrase, grams, created_at, updated_at) "
                               "VALUES ('n2n-katori', '1 katori', 150, now(), now())"))
    for did, name, aliases, serving, p, kcal, meal_type, minutes in DISHES:
        await session.execute(text(
            "INSERT INTO dishes (id, name, aliases, serving_label, protein_g, kcal, meal_type, "
            "minutes, visibility, created_at, updated_at) VALUES (:i, :n, :a, :s, :p, :k, :m, "
            ":t, 'public', now(), now())"),
            {"i": did, "n": name, "a": aliases, "s": serving, "p": p, "k": kcal,
             "m": meal_type, "t": minutes})


# ─── one account ─────────────────────────────────────────────────────────────

async def make_account(session, token: str) -> str:
    """A signed-in person with targets, and nothing else yet."""
    from app.models.base import new_id

    uid = new_id()
    await session.execute(text(
        "INSERT INTO users (id, display_name, timezone, protein_g_target, kcal_target, "
        "sleep_target_min, savings_target_paise) VALUES (:id, 'Sonu', 'Asia/Kolkata', "
        "120, 2000, 450, 1000000)"), {"id": uid})
    await _sign_in(session, uid, token)
    return uid


async def new_account(session, token: str) -> str:
    """Just signed in, the first run ahead: the name Google gave — the full one,
    which the first answer corrects to what they go by — and nothing else. No
    targets, no rows (spec/done/onboarding-goals.md)."""
    from app.models.base import new_id

    uid = new_id()
    await session.execute(text(
        "INSERT INTO users (id, display_name, timezone) VALUES (:id, 'Sonu Kumar', "
        "'Asia/Kolkata')"), {"id": uid})
    await _sign_in(session, uid, token)
    return uid


async def _sign_in(session, uid: str, token: str) -> None:
    from app.auth import hash_token
    from app.models.base import new_id

    await session.execute(text(
        "INSERT INTO sessions (id, user_id, token_hash, expires_at, scope) VALUES "
        "(:id, :u, :h, :e, 'app')"),
        {"id": new_id(), "u": uid, "h": hash_token(token),
         "e": datetime.now(UTC) + timedelta(days=1)})


def _at(day: date, hh: int, mm: int = 0) -> str:
    return datetime.combine(day, time(hh, mm), IST).isoformat()


async def _post(client: AsyncClient, path: str, body: dict, method: str = "POST") -> dict:
    r = await client.request(method, path, json=body)
    if r.status_code >= 300:
        raise RuntimeError(f"seeding {path} failed: {r.status_code} {r.text[:300]}")
    return r.json() if r.content else {}


async def lived_in_week(client: AsyncClient, today: date) -> None:
    """The week, through the API. `client` carries the account's token."""
    from app.models.base import new_id

    def d(n: int) -> date:
        return today - timedelta(days=n)

    async def post(path: str, body: dict, method: str = "POST") -> dict:
        return await _post(client, path, body, method)

    # ── money ──
    amit = await post("/counterparties", {"id": new_id(), "raw_name": "Amit",
                                           "display_name": "Amit", "kind": "person",
                                           "relation": "friend"})
    pays = [
        # day, hh, paise, direction, kind, category, description, extra
        (1, 18, 23000, "debit", "expense", "Transport", "Uber", {}),
        # How this person buys cigarettes: one at a time, ₹25, the day's ticks
        # beside them — the history the agent judges "spent 25 on cigarette" by.
        (1, 19, 2500, "debit", "expense", "Other", "Cigarette", {}),
        (2, 20, 2500, "debit", "expense", "Other", "Cigarette", {}),
        (1, 21, 45000, "debit", "expense", "Khana/Grocery", "Swiggy", {}),
        (2, 11, 64000, "debit", "expense", "Khana/Grocery", "Blinkit", {}),
        (3, 16, 120000, "debit", "expense", "Shopping", "Amazon", {}),
        (0, 11, 30000, "debit", "expense", "Other", "UPI 98xxxx4410", {"confidence": 0.4}),
        (4, 19, 400000, "debit", "lent", "Udhaar", "Amit ko udhaar",
         {"counterparty_name": "Amit", "counterparty_id": amit["id"]}),
        (5, 9, 9000000, "credit", "income", "Salary", "Salary", {}),
        (5, 10, 1500000, "debit", "expense", "Rent", "Rent", {}),
    ]
    for n, hh, paise, direction, kind, category, desc, extra in pays:
        await post("/transactions", {
            "id": new_id(), "occurred_at": _at(d(n), hh), "local_day": d(n).isoformat(),
            "amount_paise": paise, "direction": direction, "kind": kind, "category": category,
            "description": desc, "source": "manual", **extra})

    # ── food ──
    meals = [
        (1, 8, "Breakfast", "2 eggs and toast", 300, 16),
        (1, 13, "Lunch", "Rajma chawal", 650, 22),
        (1, 21, "Dinner", "Paneer bhurji with 2 roti", 560, 30),
    ]
    for n, hh, slot, dish, kcal, protein in meals:
        await post("/meals", {
            "id": new_id(), "occurred_at": _at(d(n), hh), "local_day": d(n).isoformat(),
            "meal_type": slot, "dish": dish, "kcal": kcal, "protein_g": protein,
            "source": "manual"})
    for food_id, grams in (("n2n-atta", 2000), ("n2n-egg", 6), ("n2n-soya", 500)):
        await post("/pantry", {"id": new_id(), "food_id": food_id,
                               "unit": "piece" if food_id == "n2n-egg" else "g"})
        await post("/pantry-moves", {"id": new_id(), "food_id": food_id,
                                     "occurred_at": _at(d(6), 10),
                                     "local_day": d(6).isoformat(),
                                     "quantity": grams, "kind": "opening"})

    # ── body ──
    cig = await post("/habits", {"id": new_id(), "name": "Cigarette", "direction": "break",
                                 "unit": "cigarettes"})
    gym = await post("/habits", {"id": new_id(), "name": "Workout", "direction": "build"})
    for habit, n, amount in ((cig, 1, 3), (cig, 2, 2), (gym, 1, None)):
        await post("/habit-logs", {"id": new_id(), "habit_id": habit["id"],
                                   "occurred_at": _at(d(n), 20), "local_day": d(n).isoformat(),
                                   "source": "manual", "amount": amount})
    await post(f"/days/{d(1).isoformat()}", {"sleep_hours": 7}, method="PUT")
    await post("/weigh-ins", {"id": new_id(), "local_day": d(3).isoformat(), "weight_kg": 71.0})
    for name, minutes in (("Goblet squat", 10), ("Walking lunges", 8)):
        await post("/exercises", {"id": new_id(), "name": name, "kind": "strength",
                                  "muscle_group": "legs", "typical_minutes": minutes})

    # ── work ──
    spica = await post("/projects", {"id": new_id(), "name": "PersonaOS",
                                     "description": "Spica, the personal OS app — side project"})
    office = await post("/projects", {
        "id": new_id(), "name": "Novacart", "aliases": ["novacart-chan", "office"],
        "description": "Office work: NovaCart-chan, the pet health chat app"})
    tasks = [
        ("Fix chat hallucinations", spica["id"], 0, "open"),
        ("Write the deploy spec", spica["id"], -1, "open"),
        ("Landing page copy", spica["id"], None, "open"),
        ("Grafana dashboards", office["id"], 3, "open"),
        ("Veg filter for recipes", office["id"], -3, "open"),
        ("Renew gym membership", None, -1, "open"),
        ("Pay electricity bill", None, None, "done"),
    ]
    for title, project, due_in, status in tasks:
        body = {"id": new_id(), "title": title, "source": "self", "status": status}
        if project:
            body["project_id"] = project
        if due_in is not None:
            body["due"] = d(due_in).isoformat()
        await post("/tasks", body)

    # ── people, places, memory ──
    await post("/memories", {"id": new_id(), "slug": "no-chai-late", "kind": "preference",
                             "text": "Doesn't drink chai after 10 pm"})
    await post("/memories", {
        "id": new_id(), "slug": "work", "kind": "identity",
        "text": "Applied AI engineer in Delhi; the office project is NovaCart-chan"})
    await post("/places", {"id": new_id(), "name": "Blue Tokai", "lat": 28.5494,
                           "lng": 77.2001, "kind": "eat"})


# ─── the first run's seeds ───────────────────────────────────────────────────

async def weighed(client: AsyncClient, today: date) -> None:
    """A reading already on the account, from a scale this morning — what a
    weight goal counts from."""
    from app.models.base import new_id

    await _post(client, "/weigh-ins", {"id": new_id(), "local_day": today.isoformat(),
                                       "weight_kg": 72.0})


#: A first-run case's `seed`, by name: state made through the API before
#: anything is said, for a fact the case must not leave to a model's turn.
SEEDS = {"weighed": weighed}


async def veg_kitchen(client: AsyncClient, today: date) -> None:
    """A veg person in Delhi whose kitchen is shared: atta and soya chunks, and
    eggs that someone else in the house eats. So the library's Egg bhurji is
    cookable this morning and sorted first, and Home's plan must leave it out
    all the same (spec/done/onboarding-goals.md § What reads the answers)."""
    from app.models.base import new_id

    await _post(client, "/users/me", {"diet": "veg", "city": "Delhi"}, method="PATCH")
    for food_id, quantity in (("n2n-atta", 2000), ("n2n-egg", 6), ("n2n-soya", 500)):
        await _post(client, "/pantry", {"id": new_id(), "food_id": food_id,
                                        "unit": "piece" if food_id == "n2n-egg" else "g"})
        await _post(client, "/pantry-moves", {
            "id": new_id(), "food_id": food_id, "occurred_at": _at(today - timedelta(days=2), 10),
            "local_day": (today - timedelta(days=2)).isoformat(), "quantity": quantity,
            "kind": "opening"})
