"""
The meal-estimate loop, end to end, against the real model and the real
database. spec/in-progress/meal-estimates.md § Definition of done, row 9.

Runs the cases by hand, prints what happened, and **deletes every row it
wrote** — including the pantry moves the logs caused — so the ledger is exactly
as it was. Nothing here is left behind on purpose; `--keep` is for inspecting a
failure.

    PYTHONPATH=. uv run python scripts/smoke_estimates.py
    PYTHONPATH=. uv run python scripts/smoke_estimates.py --keep
"""

import argparse
import asyncio

from sqlalchemy import text

from app.agent import tools as T
from app.db import SessionLocal
from app.models.diet import MealLog
from scripts._user import pick_user

# The plates that motivated this: two that used to log as zero, one with a
# qualifier that should move the number, one already in the library.
CASES = [
    ("I eat 2 roti and 2 egg omletes", "Breakfast"),
    ("3 roti", "Dinner"),
    ("chicken fried rice jisme chicken na ke barabar thi", "Dinner"),
    ("Whey shake", "Snack"),
]
DAY = "2026-09-19"


async def purge(s, ids: list[str]) -> None:
    """Remove the rows and everything that points at them.

    A hard delete, not the app's soft one: these are test rows and a
    tombstone would show up in Your data as a meal the person never ate. The
    children go first or the foreign keys refuse.
    """
    if not ids:
        return
    await s.execute(text("DELETE FROM pantry_moves WHERE meal_log_id = ANY(:i)"), {"i": ids})
    await s.execute(text("DELETE FROM meal_items WHERE meal_log_id = ANY(:i)"), {"i": ids})
    await s.execute(text("DELETE FROM meal_logs WHERE id = ANY(:i)"), {"i": ids})
    await s.commit()


async def main(keep: bool, user_id: str | None) -> None:
    written: list[str] = []
    async with SessionLocal() as s:
        user = await pick_user(s, user_id)
        try:
            await run(s, user, written, keep)
        finally:
            if not keep:
                await s.rollback()
                await purge(s, written)
                print(f"  cleaned up {len(written)} smoke meals")


async def run(s, user, written: list[str], keep: bool) -> None:
    if True:
        print("=== 1. plates that used to log at 0 kcal ===")
        for said, meal in CASES:
            out = await T.run(s, user, "log_meal", {
                "text_said": said, "meal_type": meal, "local_day": DAY})
            await s.commit()
            if out.get("error"):
                print(f"  FAIL {said!r}: {out['error']}")
                continue
            m = out["meal"]
            written.append(m["id"])
            print(f"  {said[:44]:<44} {m['kcal']:>5} kcal  "
                  f"{float(m['protein_g']):>5.0f} p  "
                  f"{float(m['fibre_g'] or 0):>4.0f} fibre  conf {m['confidence']}")
            print(f"      frozen estimate: {m['estimated_kcal']} kcal   "
                  f"assumed: {out.get('assumption') or '—'}")
            if out.get("ingredients"):
                made = ", ".join(f"{i['food']} ×{i['quantity']}" for i in out["ingredients"])
                print(f"      pantry spends: {made}")
            else:
                print("      pantry spends: nothing")
            if out.get("unresolved"):
                print(f"      ladder could not name: {out['unresolved']}")

        print("\n=== 2. correcting one, and what it leaves behind ===")
        target = written[0]
        row = await s.get(MealLog, target)
        before = row.kcal
        from app.routes import writes as W
        from app.schemas.writes import MealPatch
        await W.patch_meal(target, MealPatch(kcal=310, protein_g=18), s, user)
        await s.refresh(row)
        print(f"  was {before} → settled {row.kcal}; "
              f"estimate still {row.estimated_kcal}; corrected_at "
              f"{'set' if row.corrected_at else 'MISSING'}")

        print("\n=== 3. does the correction reach the next estimate? ===")
        from app.agent.estimate import _context
        ctx = await _context(s, user, [])
        line = next((x for x in ctx.splitlines() if str(row.kcal) in x and "corrected" not in x),
                    None)
        print("  corrections section present:", "They corrected these" in ctx)
        print("  our corrected row is in it:", bool(line), f"→ {line.strip() if line else ''}")

        again = await T.run(s, user, "log_meal", {
            "text_said": CASES[0][0], "meal_type": "Breakfast", "local_day": DAY})
        await s.commit()
        if not again.get("error"):
            written.append(again["meal"]["id"])
            print(f"  same plate re-logged: {again['meal']['kcal']} kcal "
                  f"(was {before} cold, they said 310)")

        print("\n=== 4. the library was not touched ===")
        dishes = await s.scalar(text("SELECT count(*) FROM dishes WHERE deleted_at IS NULL"))
        print(f"  dishes still: {dishes}")

        if keep:
            print(f"\nKEPT {len(written)} rows: {written}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--keep", action="store_true", help="leave the rows for inspection")
    ap.add_argument("--user", default=None, help="which user, when the database holds several")
    a = ap.parse_args()
    asyncio.run(main(a.keep, a.user))
