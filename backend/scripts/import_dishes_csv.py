"""
Import the reviewed dish CSVs, and backfill the meal lines they resolve.

    PYTHONPATH=. uv run python scripts/import_dishes_csv.py

Three passes, each idempotent:

1. `dishes.csv`      → one `dishes` row per line, keyed by `key`
2. `dish_items.csv`  → what each dish is made of, foods by name
3. backfill          → for every meal log whose text matches a dish name or
                       alias, one `meal_items` line

The backfill matches **exactly**, on the normalised name or alias, and never
guesses: an unmatched log keeps its words and gets no line. That is the honest
outcome — "din bhar chabana" is not a dish.
"""

import asyncio
import csv
import re
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, text

from app.db import SessionLocal
from app.models.diet import Dish, DishItem, Food, MealItem, MealLog
from scripts._user import pick_user

DATA = Path("data/dishes")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def num(v: str):
    return Decimal(v) if v.strip() else None


async def main() -> None:
    dishes = list(csv.DictReader((DATA / "dishes.csv").open()))
    items = list(csv.DictReader((DATA / "dish_items.csv").open()))

    async with SessionLocal() as s:
        user = await pick_user(s)
        foods = {norm(f.name): f.id for f in (await s.scalars(
            select(Food).where(Food.deleted_at.is_(None)))).all()}

        # ── 1. dishes, keyed by the CSV's own key so a re-run updates ──
        by_key: dict[str, str] = {}
        added = updated = 0
        for r in dishes:
            dish_id = f"dish-{r['key']}"
            by_key[r['key']] = dish_id
            row = await s.get(Dish, dish_id)
            fields = dict(
                name=r["name"],
                aliases=[a.strip() for a in r["aliases"].split(";") if a.strip()],
                meal_type=r["meal_type"] or None,
                serving_label=r["serving_label"],
                kcal=int(r["kcal"]) if r["kcal"] else None,
                protein_g=num(r["protein_g"]),
                carbs_g=num(r["carbs_g"]), fat_g=num(r["fat_g"]),
                minutes=int(r["minutes"]) if r["minutes"] else None,
                needs_prep_ahead=r["needs_prep_ahead"] == "true",
                tags=[t.strip() for t in r["tags"].split(";") if t.strip()],
                note=r["note"] or None,
                # 'mine' marks the ones this user wrote; the rest came with the app.
                created_by_id=user if r["mine"] == "yes" else None,
                visibility="private" if r["mine"] == "yes" else "public",
            )
            if row is None:
                s.add(Dish(id=dish_id, **fields))
                added += 1
            else:
                for k, v in fields.items():
                    setattr(row, k, v)
                updated += 1

        await s.flush()

        # ── 2. what each dish is made of ──
        await s.execute(text("DELETE FROM dish_items WHERE dish_id LIKE 'dish-%'"))
        missing: set[str] = set()
        lines = 0
        for r in items:
            dish_id = by_key.get(r["dish_key"])
            if dish_id is None:
                continue
            if r["food_name"]:
                food_id = foods.get(norm(r["food_name"]))
                if food_id is None:
                    missing.add(r["food_name"])
                    continue
                s.add(DishItem(dish_id=dish_id, food_id=food_id,
                               grams=int(r["grams"]) if r["grams"] else None,
                               note=r["note"] or None))
            elif r["component_dish_key"]:
                s.add(DishItem(dish_id=dish_id,
                               component_dish_id=by_key[r["component_dish_key"]],
                               servings=num(r["servings"]) or 1,
                               note=r["note"] or None))
            lines += 1

        # ── 3. backfill: a meal log's words → one line, when they match ──
        lookup: dict[str, str] = {}
        for r in dishes:
            for key in [r["name"], *[a for a in r["aliases"].split(";") if a.strip()]]:
                lookup.setdefault(norm(key), by_key[r["key"]])

        await s.execute(text(
            "DELETE FROM meal_items WHERE id IN ("
            "  SELECT mi.id FROM meal_items mi JOIN meal_logs ml ON ml.id = mi.meal_log_id"
            "  WHERE ml.user_id = :u)"), {"u": user})
        meals = (await s.scalars(select(MealLog).where(
            MealLog.user_id == user, MealLog.deleted_at.is_(None)))).all()
        linked = 0
        for meal in meals:
            dish_id = lookup.get(norm(meal.dish))
            if dish_id is None:
                continue
            s.add(MealItem(meal_log_id=meal.id, dish_id=dish_id, servings=1, said=meal.dish))
            linked += 1

        await s.commit()

    print(f"dishes: {added} added, {updated} updated · items: {lines} · "
          f"meal lines: {linked} of {len(meals)} logs")
    if missing:
        print("  foods not found (skipped):", ", ".join(sorted(missing)))


if __name__ == "__main__":
    asyncio.run(main())
