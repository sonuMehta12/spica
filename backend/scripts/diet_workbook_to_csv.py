"""
Healthy_Eating_Tracker.xlsx -> one CSV per table, for review before any import.

No profile.csv: the profile model is designed after kaam, not one mode at a time.

Nothing is written to the database. The point is to see the data in the shape
the schema expects, so a wrong column shows up as a wrong CSV rather than as a
migration.

Rules, same as the Paisa import: where the workbook does not say something the
cell stays empty. Nothing is defaulted, nothing is invented.

    uv run python scripts/diet_workbook_to_csv.py ~/Downloads/Healthy_Eating_Tracker.xlsx
"""

import csv
import re
import sys
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

OUT = Path(__file__).resolve().parent.parent / "data" / "diet"

# Free text on purpose, but the sheet says "Rest" as often as it says "Gym", and
# a rest day is not a row. Only these count as a workout happening.
DID_WORKOUT = re.compile(r"gym|workout", re.I)
NOT_A_WORKOUT = re.compile(r"^\s*(rest|no)\b", re.I)

# The sheets write a weight on either side of the name: 'Rolled oats 60 g' in
# Recipes, '30 g sukhi dal' in Portion Defaults. Both, or two thirds is lost.
NAME_THEN_G = re.compile(r"([A-Za-z][A-Za-z \-()']{2,}?)\s*~?(\d+)\s*(?:g|ml)\b", re.I)
G_THEN_NAME = re.compile(r"~?(\d+)\s*(?:g|ml)\s+([A-Za-z][A-Za-z \-']{2,})", re.I)

# Sheets carry footnotes in the first column. An item name is short and is not
# a sentence; anything else is prose that leaked into the item list.
def is_item_name(v):
    v = str(v or "").strip()
    return bool(v) and len(v) <= 40 and ". " not in v and not v.endswith(".")


# The workbook writes food names in English and portions in Hindi. Without this
# every portion default fails to resolve — 'dahi' and 'Curd' are one food.
ALIASES = {
    "Curd": ["dahi"], "Milk": ["doodh"], "Banana": ["kela"], "Apple": ["seb"],
    "Cooking oil": ["tel"], "Atta (whole wheat)": ["atta", "roti"],
    "Rice (white)": ["chawal"], "Dal (family stock)": ["dal", "daal"],
    "Green moong (whole)": ["moong"], "Eggs": ["anda", "ande"],
    "Paneer (branded)": ["paneer"], "Whey protein": ["whey"],
    "Baingan / seasonal sabzi": ["sabzi"], "Rajma": ["rajma", "chole"],
}

# A default made of other defaults. 'Ghar ka dinner' spends atta and dal through
# the recipes it is built from, so it has to point at them, not at foods.
COMPOSITES = {
    "Office thali": [("1 katori chawal", 1), ("1 katori dal", 1), ("1 katori sabzi", 1)],
    "Ghar ka dinner (default)": [("1 roti", 2), ("1 katori dal", 1), ("1 katori sabzi", 1)],
}


def norm(v):
    """'Curd (dahi)' and 'Curd' are the same food written twice."""
    return re.sub(r"\s*\(.*?\)", "", str(v)).strip().lower()


def sheet_rows(wb, name, first_header_cell):
    ws = wb[name]
    rows = list(ws.iter_rows(values_only=True))
    h = next(i for i, r in enumerate(rows) if r and str(r[0]).strip() == first_header_cell)
    cols = [str(c).strip() if c is not None else "" for c in rows[h]]
    out = []
    for r in rows[h + 1 :]:
        if r[0] is None:
            continue
        out.append(dict(zip(cols, r, strict=False)))
    return out


def write(name, fieldnames, rows):
    path = OUT / f"{name}.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    print(f"  {name + '.csv':22} {len(rows):>4} rows")
    return rows


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).strip().lower()).strip("-")


def d(v):
    return v.date().isoformat() if hasattr(v, "date") else (v or "")


def main(path):
    wb = load_workbook(path, data_only=True)
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"writing to {OUT}\n")

    # ---------- foods ----------
    nutrition = {}
    for r in sheet_rows(wb, "Nutrition Ref", "Item"):
        if not r["Item"]:
            continue
        nutrition[r["Item"].strip()] = r

    # Every item named anywhere, so purchases and pantry always have a food to
    # point at. Nutrition is left empty where the workbook never gave it —
    # owning a thing does not require knowing its macros.
    named, seen_norm = {}, {}
    def remember(name, category):
        name = str(name).strip()
        if not is_item_name(name):
            return
        # The workbook warns that names must match across sheets; they do not.
        # Fold 'Curd (dahi)' onto 'Curd' rather than creating two foods.
        key = seen_norm.setdefault(norm(name), name)
        if named.get(key) is None:
            named[key] = category

    for k, v in nutrition.items():
        remember(k, v.get("Category"))
    for sheet, col in (("Purchases", "Item"), ("Pantry Stock", "Item"), ("Staples", "Item")):
        for r in sheet_rows(wb, sheet, "Date" if sheet == "Purchases" else "Item"):
            remember(r[col], r.get("Category"))

    foods = []
    for name, category in sorted(named.items()):
        n = next((v for k, v in nutrition.items() if norm(k) == norm(name)), {})
        foods.append(
            {
                "id": f"food-{slug(name)}",
                "name": name,
                "brand": "",
                "category": category or "",
                "kcal_100g": n.get("kcal /100g", ""),
                "protein_g_100g": n.get("Protein g", ""),
                "carbs_g_100g": n.get("Carbs g", ""),
                "fat_g_100g": n.get("Fat g", ""),
                "fibre_g_100g": n.get("Fibre g", ""),
                "aliases": "|".join(ALIASES.get(name, [])),
                "nutrition_source": "reference" if n else "",
                "confidence": 1.0 if n else "",
            }
        )
    write("foods", list(foods[0].keys()), foods)
    by_norm = {norm(f["name"]): f for f in foods}
    for f in foods:
        for a in ALIASES.get(f["name"], []):
            by_norm.setdefault(a, f)

    def find_food(text):
        t = norm(text)
        if t in by_norm:
            return by_norm[t]
        hits = [f for k, f in by_norm.items() if k in t or t in k]
        return min(hits, key=lambda f: len(f["name"])) if hits else None

    # ---------- measures + recipes from Portion Defaults ----------
    prows = [r for r in sheet_rows(wb, "Portion Defaults", "User kya kehta hai")
             if r["User kya kehta hai"] and not str(r["User kya kehta hai"]).startswith("Anumaan")]
    measures, portion_recipes = [], []
    for r in prows:
        phrase = str(r["User kya kehta hai"]).strip().strip("'")
        assumed = str(r["Maana jayega"] or "").strip()
        kcal = r["kcal"] or 0
        if str(phrase).startswith("---"):
            continue
        if not kcal:  # zero kcal == a unit of measurement, not food
            g = re.search(r"(\d+)", assumed)
            measures.append(
                {"id": f"measure-{slug(phrase)}", "phrase": phrase,
                 "grams": g.group(1) if g else "", "created_by_id": ""}
            )
        else:
            portion_recipes.append(
                {"id": f"recipe-{slug(phrase)}", "name": phrase, "aliases": "",
                 "meal_type": "", "serving_label": phrase, "kcal": kcal,
                 "protein_g": r["Protein g"], "carbs_g": "", "fat_g": "",
                 "prep_minutes": "", "needs_prep_ahead": "false", "steps": "",
                 "image_url": "", "confidence": 1.0, "created_by_id": "",
                 "visibility": "public", "assumed": assumed, "note": r.get("Note") or ""}
            )
    write("measures", ["id", "phrase", "grams", "created_by_id"], measures)

    # ---------- recipes from the Recipes sheet ----------
    recipes = list(portion_recipes)
    user_made = {"Chana salad", "Moongphali keema"}
    for r in sheet_rows(wb, "Recipes", "Recipe"):
        name = r["Recipe"]
        if not name or str(name).startswith("Peeli"):
            continue
        name = str(name).strip()
        prep = r["Prep pehle se?"] or ""
        recipes.append(
            {"id": f"recipe-{slug(name)}", "name": name, "aliases": "",
             "meal_type": r["Meal slot"] or "", "serving_label": "1 serving",
             "kcal": r["kcal"], "protein_g": r["Protein g"], "carbs_g": "", "fat_g": "",
             "prep_minutes": re.sub(r"\D", "", str(r["Time"] or "")) or "",
             "needs_prep_ahead": str(prep).lower().startswith("haan") and "true" or "false",
             "steps": "", "image_url": "", "confidence": 1.0,
             "created_by_id": "me" if name in user_made else "",
             "visibility": "private" if name in user_made else "public",
             "assumed": r["Ingredients"] or "", "note": ""}
        )
    write("recipes", list(recipes[0].keys()), recipes)

    # ---------- recipe_items, parsed from the ingredient text ----------
    items, unparsed = [], 0
    for rec in recipes:
        found = False
        pairs = [(n, g) for n, g in NAME_THEN_G.findall(rec["assumed"])]
        pairs += [(n, g) for g, n in G_THEN_NAME.findall(rec["assumed"])]
        # '1 katori dahi -> 150 g' names the food in the phrase, not the value.
        if not pairs:
            bare = re.fullmatch(r"~?(\d+)\s*(?:g|ml)\b", rec["assumed"].strip())
            if bare:
                pairs = [(rec["name"], bare.group(1))]
        for raw_name, grams in pairs:
            f = find_food(raw_name)
            if f:
                items.append({"recipe_id": rec["id"], "food_id": f["id"],
                              "food_name": f["name"], "grams": grams, "servings": 1})
                found = True
        if not found:
            unparsed += 1
    # Composite defaults point at recipes rather than foods.
    by_name = {r["name"]: r for r in recipes}
    for parent, parts in COMPOSITES.items():
        if parent not in by_name:
            continue
        for part, count in parts:
            if part in by_name:
                items.append({"recipe_id": by_name[parent]["id"], "food_id": "",
                              "food_name": "", "component_recipe_id": by_name[part]["id"],
                              "grams": "", "servings": count})
    write("recipe_items",
          ["recipe_id", "food_id", "food_name", "component_recipe_id", "grams", "servings"],
          items)
    print(f"  {'':22}      ({unparsed} recipes had no ingredient that matched a food)")

    # ---------- meal_logs ----------
    meals = []
    for i, r in enumerate(sheet_rows(wb, "Meal Log", "Date")):
        if not r["Dish"]:
            continue
        day = d(r["Date"])
        meals.append(
            {"dedupe_key": f"xlsx:meal:{i}", "local_day": day,
             "occurred_at": f"{day}T12:00:00Z", "meal_type": r["Meal"],
             "dish": r["Dish"], "recipe_id": "", "ingredients": r["Ingredients used (qty)"],
             "kcal": r["Calories (kcal)"], "protein_g": r["Protein (g)"],
             "carbs_g": r["Carbs (g)"], "fat_g": r["Fat (g)"],
             "cooked_home": {"Yes": "true", "No": "false"}.get(r["Cooked at home?"], ""),
             "source": "manual", "confidence": 1.0, "note": r["Notes"], "tags": ""}
        )
    write("meal_logs", list(meals[0].keys()), meals)

    # ---------- habits, habit_logs, days ----------
    habits = [
        {"id": "habit-workout", "name": "Workout", "direction": "build", "unit": "minutes"},
        {"id": "habit-cigarettes", "name": "Cigarettes", "direction": "break", "unit": ""},
        {"id": "habit-alcohol", "name": "Alcohol", "direction": "break", "unit": "units"},
    ]
    write("habits", list(habits[0].keys()), habits)

    logs, days = [], []
    partial = {date(2026, 8, 7)}  # Research Log marks this PARTIAL
    for r in sheet_rows(wb, "Daily Summary", "Date"):
        if not r["Day"]:
            continue
        day = d(r["Date"])
        w = str(r["Workout"] or "").strip()
        if w and DID_WORKOUT.search(w) and not NOT_A_WORKOUT.match(w):
            logs.append({"habit_id": "habit-workout", "local_day": day,
                         "occurred_at": f"{day}T12:00:00Z", "amount": "", "note": w,
                         "source": "manual"})
        for hid, col in (("habit-cigarettes", "Cigarettes"), ("habit-alcohol", "Alcohol (units)")):
            v = r.get(col)
            if v:  # a zero is not a row — absence already means it did not happen
                logs.append({"habit_id": hid, "local_day": day,
                             "occurred_at": f"{day}T12:00:00Z", "amount": v, "note": "",
                             "source": "manual"})
        lc = "false" if (r["Date"] and r["Date"].date() in partial) else ""
        if r["Weight (kg)"] or r["Sleep (h)"] or r["Notes"] or lc:
            days.append({"local_day": day, "log_complete": lc,
                         "weight_kg": r["Weight (kg)"] or "",
                         "sleep_hours": r["Sleep (h)"] or "", "note": r["Notes"] or ""})
    write("habit_logs", list(logs[0].keys()), logs)
    write("days", list(days[0].keys()), days)

    # ---------- pantry + pantry_moves ----------
    pantry, moves = [], []
    for r in sheet_rows(wb, "Pantry Stock", "Item"):
        if not r["Item"] or str(r["Item"]).startswith("Update"):
            continue
        f = find_food(r["Item"])
        if not f:
            continue
        note = r["Notes"] or ""
        shelf = 3 if "2-3 days" in note else (5 if "~5 days" in note else "")
        pantry.append({"food_id": f["id"], "food_name": f["name"],
                       "reorder_at_g": r["Re-order at"], "shelf_life_days": shelf,
                       "note": note})
        # The sheet's 'Remaining' is NOT imported as an opening move. An opening
        # is meant to be an observation — someone looked in the cupboard. This
        # column was a hand-maintained counter that drifted: it claims 740 g of
        # tofu where the meal log accounts for 540, and 780 g of curd where 430
        # was eaten. Importing it would launder a number we can prove wrong.
    known = {norm(p["food_name"]) for p in pantry}
    for r in sheet_rows(wb, "Staples", "Item"):
        name = str(r["Item"] or "").strip()
        if not is_item_name(name) or norm(name) in known:
            continue
        if str(r["Available now?"] or "").strip().lower() not in ("yes", "bahar"):
            continue
        f = find_food(name)
        if not f:
            continue
        known.add(norm(name))
        # No grams, and none can be had: 'gram me track nahi karte'.
        pantry.append({"food_id": f["id"], "food_name": f["name"], "reorder_at_g": "",
                       "shelf_life_days": "", "note": r["Notes"] or ""})
    write("pantry", list(pantry[0].keys()), pantry)

    # Consumption, read out of what each meal says it used. This is the move the
    # agent will write at log time; here it is recovered from the text after the
    # fact, which is why some rows cannot be matched.
    unmatched = 0
    for mi, r in enumerate(sheet_rows(wb, "Meal Log", "Date")):
        if not r["Dish"]:
            continue
        ing = str(r["Ingredients used (qty)"] or "")
        for part in ing.split(","):
            hit = NAME_THEN_G.search(part) or None
            g_first = G_THEN_NAME.search(part)
            if hit:
                raw, grams = hit.group(1), hit.group(2)
            elif g_first:
                grams, raw = g_first.group(1), g_first.group(2)
            else:
                if part.strip():
                    unmatched += 1
                continue
            f = find_food(raw)
            if not f:
                unmatched += 1
                continue
            moves.append({"dedupe_key": f"xlsx:consumption:{mi}:{f['id']}",
                          "food_id": f["id"], "food_name": f["name"],
                          "local_day": d(r["Date"]),
                          "occurred_at": f"{d(r['Date'])}T12:00:00Z",
                          "quantity_g": -int(grams), "kind": "consumption",
                          "meal_log_id": f"xlsx:meal:{mi}", "note": part.strip()})

    # Purchases are the incoming moves. No price columns: money is Paisa's.
    for i, r in enumerate(sheet_rows(wb, "Purchases", "Date")):
        if not r["Item"]:
            continue
        note = str(r["Notes"] or "")
        f = find_food(r["Item"])
        if not f or r["Total qty"] is None:
            continue
        moves.append({"dedupe_key": f"xlsx:purchase:{i}", "food_id": f["id"],
                      "food_name": f["name"], "local_day": d(r["Date"]),
                      "occurred_at": f"{d(r['Date'])}T12:00:00Z",
                      "quantity_g": int(r["Total qty"]), "kind": "purchase",
                      "meal_log_id": "", "note": note})
    moves.sort(key=lambda m: (m["local_day"], m["food_name"]))
    write("pantry_moves", ["dedupe_key", "food_id", "food_name", "local_day",
                           "occurred_at", "quantity_g", "kind", "meal_log_id", "note"], moves)
    print(f"  {'':22}      ({unmatched} ingredient phrases matched no known food)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Healthy_Eating_Tracker.xlsx")
