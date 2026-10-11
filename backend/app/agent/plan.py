"""
Today's plan: the rest of the day's meals and one workout.
spec/in-progress/today-plan.md, reasoning from spec/in-progress/meal-suggestion.md.

A suggestion is a gap-closing calculation, not a recipe lookup: what is left of
today's protein and calories, over the meals still ahead, from what this person
eats and has at home. One model call does the calculation with all of that in
front of it; this module gathers the state, checks the answer against the rows,
and keeps it until a write it was built on changes.

Checked, not trusted. A `dish_id` the model names must be one it was given, and
a library dish's numbers are the library's, not the model's. Anything else is an
**idea** — marked as one, its macros an estimate. The same for exercises.

Not stored. The plan is regenerated from rows, so it cannot go on claiming a
gap the user has since closed; the cache dies with any write it read.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import images, llm
from app.diet_summary import diet_summary
from app.models.diet import Dish, Exercise
from app.models.users import Memory, User, WeighIn

log = logging.getLogger(__name__)

SKILL_FILE = Path(__file__).with_name("skills") / "plan.md"

#: The day's slots, and the local hour each stops being ahead. A slot already
#: logged is never planned again, whatever the hour.
SLOT_ENDS = {"Breakfast": 11, "Lunch": 16, "Snack": 19, "Dinner": 23}
KINDS = ("gym", "run", "ride", "walk", "yoga", "rest")
#: What Commons is searched for when a workout has no library picture.
KIND_PICTURE = {"run": "jogging", "ride": "road cycling", "walk": "walking path",
                "yoga": "yoga asana", "gym": "dumbbell workout"}
#: How many dishes and exercises go into the context: enough to choose from,
#: few enough that the prompt stays the size of a conversation turn.
DISHES = 40
EXERCISES = 40

#: (user, day) → (fingerprint, plan). One process, one user; a restart costs
#: one model call, which is the price of not storing a plan as a row.
_cache: dict[tuple[str, str], tuple[str, dict]] = {}


def _f(x) -> float | None:
    return None if x is None else float(x)


def _clock(local_time: str | None, tz: str) -> tuple[int, int]:
    if local_time:
        try:
            h, m = local_time.split(":")[:2]
            return int(h), int(m)
        except ValueError:
            pass
    now = datetime.now(ZoneInfo(tz))
    return now.hour, now.minute


def slots_ahead(logged_types: set[str], hour: int) -> list[str]:
    """The slots still to eat: not logged today, and not over by the clock."""
    return [s for s, end in SLOT_ENDS.items() if s.lower() not in logged_types and hour < end]


async def _fingerprint(session: AsyncSession, user: str, day: date, ahead: list[str],
                       targets: dict, person: dict) -> str:
    """Everything the plan read that can change during a day. Same print, same
    plan: opening Home twice makes one model call.

    Who they are goes in as the planner is given it, not as row timestamps: a
    diet set, a food never eaten or a new weight is a different plan, and a
    sign-in, a timezone or the first-run flag — which all touch `users` — is
    not one more billed call."""
    row = (await session.execute(text("""
        SELECT
          (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM meal_logs
            WHERE user_id = :u AND local_day = :d),
          (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM habit_logs
            WHERE user_id = :u AND local_day = :d),
          (SELECT coalesce(max(updated_at)::text, '') FROM exercises WHERE user_id = :u),
          (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM dish_saves
            WHERE user_id = :u),
          (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM pantry_moves
            WHERE user_id = :u)
    """), {"u": user, "d": day})).one()
    raw = json.dumps([list(row), ahead, targets, person], default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _parse(raw: str) -> dict | None:
    try:
        body = raw.strip()
        return json.loads(body[body.find("{"):body.rfind("}") + 1])
    except (ValueError, AttributeError):
        return None


def _num(x, lo: float = 0, hi: float = 5000) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if lo < v <= hi else None


async def _context(session: AsyncSession, user: str, day: date, ahead: list[str],
                   clock: tuple[int, int], targets: dict,
                   person: dict) -> tuple[dict, dict, dict]:
    """The engine spec's state, from rows. Returns the payload and the two
    libraries by id, which the answer is checked against."""
    from app.agent import tools as T

    today = await diet_summary(session, user, day, day, {"today", "rows"})
    week = await diet_summary(session, user, day - timedelta(days=7), day - timedelta(days=1),
                              {"top_dishes", "by_day"})
    monday = day - timedelta(days=day.weekday())
    habits = await diet_summary(session, user, monday, day, {"habits_week", "pantry"})
    dishes = (await T.t_suggest_dishes(session, user, local_day=day.isoformat()))["candidates"]
    dishes.sort(key=lambda d: (not d["cookable_now"], -(d["tried"] or 0)))
    dishes = dishes[:DISHES]
    exercises = (await T.t_exercises(session, user))["exercises"][:EXERCISES]

    payload = {
        "local_day": day.isoformat(),
        "local_time": f"{clock[0]:02d}:{clock[1]:02d}",
        "slots_ahead": ahead,
        "person": person,
        "targets": targets,
        "logged_today": [{"slot": r["meal_type"], "dish": r["dish"], "kcal": r["kcal"],
                          "protein_g": r["protein_g"]} for r in today.get("rows", [])],
        "left": {"protein_g": today["today"]["protein_left_g"], "kcal": today["today"]["kcal_left"]},
        "last_7_days": {"top_dishes": week.get("top_dishes", []),
                        "by_day": [{"day": str(d["local_day"]), "protein_g": d["protein_g"],
                                    "kcal": d["kcal"]} for d in week.get("by_day", [])]},
        "pantry": [p["food"] for p in habits.get("pantry", []) if p["status"] in ("ok", "soon", "staple")],
        "pantry_out": [p["food"] for p in habits.get("pantry", []) if p["status"] == "out"],
        "dish_library": [{k: d[k] for k in ("dish_id", "name", "meal_type", "kcal", "protein_g",
                                            "minutes", "cookable_now", "tried", "last_had_days_ago")}
                         for d in dishes],
        "exercise_library": [{k: e[k] for k in ("id", "name", "kind", "muscle_group", "equipment",
                                                "typical_minutes", "tried", "last_tried")}
                             for e in exercises],
        "workouts_this_week": [
            {"habit": h["habit"], "days": [str(x["local_day"]) for x in h["days"]]}
            for h in habits.get("habits_week", [])
            if any(w in h["habit"].lower() for w in ("workout", "gym", "run", "walk", "yoga", "cycl"))
        ],
    }
    return payload, {d["dish_id"]: d for d in dishes}, {e["id"]: e for e in exercises}


async def _person(session: AsyncSession, user: str) -> dict:
    """Who the plan is for: what they eat, where, and their body — the diet and
    the foods they never eat are limits, the body sizes a serving
    (spec/done/onboarding-goals.md § What reads the answers). Unanswered is null,
    never a default."""
    profile = await session.get(User, user)
    weight = await session.scalar(
        select(WeighIn).where(WeighIn.user_id == user, WeighIn.deleted_at.is_(None))
        .order_by(WeighIn.local_day.desc()).limit(1))
    memories = (await session.scalars(
        select(Memory).where(Memory.user_id == user, Memory.deleted_at.is_(None))
        .order_by(Memory.kind, Memory.slug))).all()
    return {
        "diet": profile.diet if profile else None,
        "memories": [{"kind": m.kind, "text": m.text} for m in memories],
        "city": profile.city if profile else None,
        "gender": profile.gender if profile else None,
        "dob": profile.dob.isoformat() if profile and profile.dob else None,
        "height_cm": _f(profile.height_cm) if profile else None,
        "weight_kg": _f(weight.weight_kg) if weight else None,
        "weight_estimated": weight.estimated if weight else None,
    }


def _meals(answer: dict, ahead: list[str], library: dict) -> list[dict]:
    """One meal per slot ahead, each either a library dish with the library's
    numbers, or an idea with the model's, marked."""
    out, seen = [], set()
    for m in answer.get("meals") or []:
        if not isinstance(m, dict):
            continue
        slot = next((s for s in ahead if s.lower() == str(m.get("slot", "")).lower()), None)
        if slot is None or slot in seen:
            continue
        lib = library.get(m.get("dish_id"))
        name = (lib["name"] if lib else str(m.get("name") or "").strip())[:80]
        kcal = (lib and lib["kcal"]) or _num(m.get("kcal"))
        protein = (lib and lib["protein_g"]) or _num(m.get("protein_g"), -1, 500)
        if not name or not kcal or protein is None:
            continue
        seen.add(slot)
        out.append({
            "slot": slot, "dish_id": lib["dish_id"] if lib else None, "name": name,
            "kcal": int(round(float(kcal))), "protein_g": round(float(protein), 1),
            "carbs_g": _num(m.get("carbs_g"), -1, 1000), "fat_g": _num(m.get("fat_g"), -1, 500),
            "why": str(m.get("why") or "")[:90], "idea": lib is None,
            # A library dish's carbs and fat are filled from its row with its
            # picture; an idea's numbers are all the model's — estimates.
            "estimated": lib is None, "image_url": None, "image_credit": None,
        })
    order = {s: i for i, s in enumerate(ahead)}
    return sorted(out, key=lambda m: order[m["slot"]])


def _workout(answer: dict, library: dict) -> dict | None:
    w = answer.get("workout")
    if not isinstance(w, dict) or w.get("kind") not in KINDS:
        return None
    items = []
    for x in (w.get("exercises") or [])[:6]:
        if not isinstance(x, dict):
            continue
        lib = library.get(x.get("exercise_id"))
        name = (lib["name"] if lib else str(x.get("name") or "").strip())[:60]
        if name:
            items.append({"exercise_id": lib["id"] if lib else None, "name": name,
                          "detail": str(x.get("detail") or "")[:40], "idea": lib is None})
    minutes = _num(w.get("minutes"), 0, 240)
    return {
        "kind": w["kind"], "name": str(w.get("name") or w["kind"].title())[:40],
        "minutes": int(minutes) if minutes else None, "why": str(w.get("why") or "")[:90],
        "exercises": items,
        "idea": w["kind"] != "rest" and not any(i["exercise_id"] for i in items),
        "image_url": None, "image_credit": None,
    }


async def _pictures(session: AsyncSession, meals: list[dict], workout: dict | None) -> None:
    """Library rows get theirs stored; ideas get one by name. Never fatal."""
    dish_rows = {d.id: d for d in (await session.scalars(select(Dish).where(
        Dish.id.in_([m["dish_id"] for m in meals if m["dish_id"]])))).all()}
    ideas = [m["name"] for m in meals if not m["dish_id"]]
    found = await images.fill(list(dish_rows.values()), ideas, "food")
    for m in meals:
        row = dish_rows.get(m["dish_id"])
        if row is not None:
            # The library's own carbs and fat; unknown there stays unknown here.
            m["carbs_g"], m["fat_g"] = _f(row.carbs_g), _f(row.fat_g)
        pic = found.get(m["name"]) if row is None else None
        m["image_url"] = row.image_url if row else (pic.url if pic else None)
        m["image_credit"] = row.image_credit if row else (pic.credit if pic else None)

    if workout and workout["kind"] != "rest":
        ids = [i["exercise_id"] for i in workout["exercises"] if i["exercise_id"]]
        rows = list((await session.scalars(select(Exercise).where(Exercise.id.in_(ids)))).all())
        if rows:
            await images.fill(rows, [], "exercise")
        shown = next((r for r in rows if r.image_url), None)
        if shown:
            workout["image_url"], workout["image_credit"] = shown.image_url, shown.image_credit
        else:
            word = KIND_PICTURE.get(workout["kind"], "workout")
            pic = (await images.fill([], [word], ""))[word]
            if pic:
                workout["image_url"], workout["image_credit"] = pic.url, pic.credit
    await session.commit()


async def today(session: AsyncSession, user: str, day: date, local_time: str | None = None) -> dict:
    profile = await session.get(User, user)
    clock = _clock(local_time, profile.timezone if profile else "Asia/Kolkata")
    targets = {"protein_g": _f(profile.protein_g_target) if profile else None,
               "kcal": profile.kcal_target if profile else None}

    logged_rows = (await diet_summary(session, user, day, day, {"rows", "today"}))
    logged = {"protein_g": logged_rows["today"]["protein_g"], "kcal": logged_rows["today"]["kcal"]}
    ahead = slots_ahead({r["meal_type"].lower() for r in logged_rows.get("rows", [])}, clock[0])

    # No slot left: the meals are done for the day; the workout may not be.
    base = {"local_day": day.isoformat(), "targets": targets, "logged": logged,
            "slots_ahead": ahead, "done": not ahead}
    person = await _person(session, user)
    fp = await _fingerprint(session, user, day, ahead, targets, person)
    hit = _cache.get((user, day.isoformat()))
    if hit and hit[0] == fp:
        return hit[1]

    payload, dishes, exercises = await _context(session, user, day, ahead, clock, targets,
                                                person)
    try:
        raw, used = await llm.categorise(SKILL_FILE.read_text(), json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:  # noqa: BLE001 — the rest of Home does not depend on this
        log.exception("plan failed for %s", day)
        return {**base, "available": False, "meals": [], "workout": None,
                "planned": {"protein_g": 0, "kcal": 0}}
    answer = _parse(raw)
    if answer is None:
        log.warning("plan unusable: %r", (raw or "")[:200])
        return {**base, "available": False, "meals": [], "workout": None,
                "planned": {"protein_g": 0, "kcal": 0}}

    meals = _meals(answer, ahead, dishes)
    workout = _workout(answer, exercises)
    try:
        await _pictures(session, meals, workout)
    except Exception:  # noqa: BLE001 — a picture is never load-bearing
        log.warning("pictures failed", exc_info=True)
        await session.rollback()

    plan = {
        **base, "available": True, "model": used, "meals": meals, "workout": workout,
        "planned": {"protein_g": round(sum(m["protein_g"] for m in meals), 1),
                    "kcal": sum(m["kcal"] for m in meals)},
    }
    _cache[(user, day.isoformat())] = (fp, plan)
    return plan
