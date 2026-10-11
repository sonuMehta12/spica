"""
Import the reviewed CSVs in backend/data/diet/ into the database.

The CSVs are the contract: they were read, argued over and corrected before any
of this ran (spec/in-progress/diet-data-model.md § CSV first). This script adds
no judgement of its own — it types the columns and nothing else.

Idempotent. Reference rows carry stable ids from the CSVs; ledger rows carry a
per-user dedupe_key. Re-running inserts nothing.

    uv run python scripts/import_diet_csv.py
"""

import asyncio
import csv
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models.diet import (
    Day,
    Food,
    Habit,
    HabitLog,
    MealLog,
    Measure,
    PantryItem,
    PantryMove,
    Recipe,
    RecipeItem,
)
from scripts._user import pick_user

DATA = Path(__file__).resolve().parent.parent / "data" / "diet"
USER = ""  # the one user's id, read from the users table in main()

added = skipped = 0


def rows(name):
    with (DATA / f"{name}.csv").open() as f:
        return list(csv.DictReader(f))


def txt(v):
    return v.strip() if v and v.strip() else None


def num(v, cast):
    return cast(v) if v not in (None, "") else None


def dec(v):
    return Decimal(v) if v not in (None, "") else None


def day(v):
    return date.fromisoformat(v)


def ts(v):
    return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(UTC)


def keep(obj, session, key, seen):
    global added, skipped
    if key in seen:
        skipped += 1
        return False
    session.add(obj)
    seen.add(key)
    added += 1
    return True


async def main():
    global USER
    async with SessionLocal() as s:
        USER = await pick_user(s)
        # Everything already imported, one set per table, keyed the same way
        # the CSVs key their rows.
        have = {
            "foods": set((await s.scalars(select(Food.id))).all()),
            "measures": set((await s.scalars(select(Measure.id))).all()),
            "recipes": set((await s.scalars(select(Recipe.id))).all()),
            "habits": set((await s.scalars(select(Habit.id))).all()),
            "pantry": set((await s.scalars(select(PantryItem.food_id).where(
                PantryItem.user_id == USER))).all()),
            "days": set((await s.scalars(select(Day.local_day).where(
                Day.user_id == USER))).all()),
            "meal_dedupe": set((await s.scalars(select(MealLog.dedupe_key).where(
                MealLog.user_id == USER, MealLog.dedupe_key.is_not(None)))).all()),
            "move_dedupe": set((await s.scalars(select(PantryMove.dedupe_key).where(
                PantryMove.user_id == USER, PantryMove.dedupe_key.is_not(None)))).all()),
            "habit_dedupe": set((await s.scalars(select(HabitLog.dedupe_key).where(
                HabitLog.user_id == USER, HabitLog.dedupe_key.is_not(None)))).all()),
        }
        # recipe_items has no natural key in the CSV; key on the triple.
        have["items"] = {
            (r.recipe_id, r.food_id, r.component_recipe_id)
            for r in (await s.scalars(select(RecipeItem))).all()
        }

        for r in rows("foods"):
            keep(Food(
                id=r["id"], name=r["name"], brand=txt(r["brand"]),
                category=txt(r["category"]),
                aliases=r["aliases"].split("|") if r["aliases"] else [],
                kcal_100g=num(r["kcal_100g"], lambda v: int(float(v))),
                protein_g_100g=dec(r["protein_g_100g"]), carbs_g_100g=dec(r["carbs_g_100g"]),
                fat_g_100g=dec(r["fat_g_100g"]), fibre_g_100g=dec(r["fibre_g_100g"]),
                nutrition_source=txt(r["nutrition_source"]),
                confidence=num(r["confidence"], float),
            ), s, r["id"], have["foods"])

        for r in rows("measures"):
            keep(Measure(
                id=r["id"], phrase=r["phrase"], grams=int(r["grams"]),
                created_by_id=USER if txt(r["created_by_id"]) else None,
            ), s, r["id"], have["measures"])

        for r in rows("recipes"):
            keep(Recipe(
                id=r["id"], name=r["name"],
                aliases=r["aliases"].split("|") if r["aliases"] else [],
                meal_type=txt(r["meal_type"]), serving_label=txt(r["serving_label"]),
                kcal=int(float(r["kcal"])), protein_g=dec(r["protein_g"]),
                carbs_g=dec(r["carbs_g"]), fat_g=dec(r["fat_g"]),
                prep_minutes=num(r["prep_minutes"], int),
                needs_prep_ahead=r["needs_prep_ahead"] == "true",
                confidence=float(r["confidence"]),
                created_by_id=USER if txt(r["created_by_id"]) else None, visibility=r["visibility"],
                note=txt(r["note"]),
            ), s, r["id"], have["recipes"])
        await s.flush()

        for r in rows("recipe_items"):
            key = (r["recipe_id"], txt(r["food_id"]), txt(r["component_recipe_id"]))
            keep(RecipeItem(
                recipe_id=r["recipe_id"], food_id=txt(r["food_id"]),
                component_recipe_id=txt(r["component_recipe_id"]),
                grams=num(r["grams"], int), servings=num(r["servings"], int) or 1,
            ), s, key, have["items"])

        for r in rows("habits"):
            keep(Habit(id=r["id"], user_id=USER, name=r["name"],
                       direction=r["direction"], unit=txt(r["unit"])),
                 s, r["id"], have["habits"])
        await s.flush()

        meal_ids = {}  # dedupe_key -> row id, for pantry_moves to point at
        for r in rows("meal_logs"):
            m = MealLog(
                user_id=USER, dedupe_key=r["dedupe_key"],
                occurred_at=ts(r["occurred_at"]), local_day=day(r["local_day"]),
                meal_type=r["meal_type"], dish=r["dish"],
                recipe_id=txt(r["recipe_id"]), ingredients=txt(r["ingredients"]),
                kcal=int(float(r["kcal"])), protein_g=dec(r["protein_g"]),
                carbs_g=dec(r["carbs_g"]), fat_g=dec(r["fat_g"]),
                cooked_home=None if r["cooked_home"] == "" else r["cooked_home"] == "true",
                source=r["source"], confidence=float(r["confidence"]),
                note=txt(r["note"]), tags=r["tags"].split("|") if r["tags"] else [],
            )
            if keep(m, s, r["dedupe_key"], have["meal_dedupe"]):
                meal_ids[r["dedupe_key"]] = m
        await s.flush()
        # Already-imported meals still need their ids for move references.
        for k in (await s.execute(select(MealLog.dedupe_key, MealLog.id).where(
                MealLog.user_id == USER, MealLog.dedupe_key.is_not(None)))).all():
            meal_ids.setdefault(k[0], None)
            if meal_ids[k[0]] is None:
                meal_ids[k[0]] = k[1]

        for r in rows("habit_logs"):
            # The CSV has no key of its own; one habit row per habit per day is
            # what the source sheet could express, so that is the key.
            k = f"xlsx:habit:{r['habit_id']}:{r['local_day']}"
            keep(HabitLog(
                user_id=USER, habit_id=r["habit_id"], dedupe_key=k,
                occurred_at=ts(r["occurred_at"]), local_day=day(r["local_day"]),
                amount=num(r["amount"], float), note=txt(r["note"]), source=r["source"],
            ), s, k, have["habit_dedupe"])

        for r in rows("days"):
            keep(Day(
                user_id=USER, local_day=day(r["local_day"]),
                log_complete=None if r["log_complete"] == "" else r["log_complete"] == "true",
                weight_kg=num(r["weight_kg"], float),
                sleep_hours=num(r["sleep_hours"], float), note=txt(r["note"]),
            ), s, day(r["local_day"]), have["days"])

        for r in rows("pantry"):
            keep(PantryItem(
                user_id=USER, food_id=r["food_id"],
                reorder_at_g=num(r["reorder_at_g"], lambda v: int(float(v))),
                shelf_life_days=num(r["shelf_life_days"], int), note=txt(r["note"]),
            ), s, r["food_id"], have["pantry"])

        for r in rows("pantry_moves"):
            ref = meal_ids.get(r["meal_log_id"]) if r["meal_log_id"] else None
            keep(PantryMove(
                user_id=USER, dedupe_key=r["dedupe_key"], food_id=r["food_id"],
                local_day=day(r["local_day"]), occurred_at=ts(r["occurred_at"]),
                quantity_g=int(r["quantity_g"]), kind=r["kind"],
                meal_log_id=ref.id if hasattr(ref, "id") else ref, note=txt(r["note"]),
            ), s, r["dedupe_key"], have["move_dedupe"])

        await s.commit()
        print(f"added {added}, skipped {skipped} (already imported)")


if __name__ == "__main__":
    asyncio.run(main())
