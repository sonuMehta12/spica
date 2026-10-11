"""
The pantry item corrections of 2026-09-04, as the user made them.

A one-off data pass, kept because the import would otherwise recreate the old
shape. Idempotent: run it twice and nothing changes.

    PYTHONPATH=. uv run python scripts/fix_pantry_items.py

- Curd, green vegetable and baingan become staples: they arrive without being
  bought, so a quantity would be meaningless.
- Apple, banana and mango stop being tracked separately. Fruit is seasonal and
  interchangeable; per-fruit grams go stale within days. One `Fruit` row is
  counted instead, starting empty — no number is carried over from the old
  rows, because none of them was still true.
- The duplicate `Whey protein` row goes; `Whey protein powder` has the moves.
- `Eggs / chicken (bahar)` becomes `Eggs`: 'bahar' means eaten out, which is
  not a fact about this kitchen.

Every one of these leaves the moves in the ledger. Untracking is not deleting.
"""

import asyncio

from sqlalchemy import text

from app.db import SessionLocal
from scripts._user import pick_user

BECOME_STAPLE = ("Curd", "Green vegetable (1-2)", "Baingan / seasonal sabzi")
STOP_TRACKING = ("Apple", "Banana", "Mango", "Whey protein")
FRUIT_NOTE = "Whatever is in season — apple, kela, aam. Bought by the kilo, counted as one."


async def main() -> None:
    async with SessionLocal() as s:
        user = await pick_user(s)
        staple = await s.execute(text("""
            UPDATE pantry SET staple = true, updated_at = now()
            WHERE user_id = :u AND deleted_at IS NULL AND staple = false
              AND food_id IN (SELECT id FROM foods WHERE name = ANY(:n))"""),
            {"u": user, "n": list(BECOME_STAPLE)})
        dropped = await s.execute(text("""
            UPDATE pantry SET deleted_at = now()
            WHERE user_id = :u AND deleted_at IS NULL
              AND food_id IN (SELECT id FROM foods WHERE name = ANY(:n))"""),
            {"u": user, "n": list(STOP_TRACKING)})
        renamed = await s.execute(
            text("UPDATE foods SET name = 'Eggs' WHERE name = 'Eggs / chicken (bahar)'"))

        fruit = (await s.execute(text("SELECT id FROM foods WHERE name = 'Fruit'"))).scalar()
        if fruit is None:
            fruit = (await s.execute(text(
                "INSERT INTO foods (id, name) VALUES (gen_random_uuid()::text, 'Fruit') "
                "RETURNING id"))).scalar()
        tracked = (await s.execute(text(
            "SELECT 1 FROM pantry WHERE user_id = :u AND food_id = :f AND deleted_at IS NULL"),
            {"u": user, "f": fruit})).first()
        if not tracked:
            await s.execute(text("""
                INSERT INTO pantry (id, user_id, food_id, staple, reorder_at_g, note)
                VALUES (gen_random_uuid()::text, :u, :f, false, 300, :note)"""),
                {"u": user, "f": fruit, "note": FRUIT_NOTE})
        await s.commit()
        print(f"staples +{staple.rowcount} · untracked {dropped.rowcount} · "
              f"renamed {renamed.rowcount} · fruit {'added' if not tracked else 'already there'}")


if __name__ == "__main__":
    asyncio.run(main())
