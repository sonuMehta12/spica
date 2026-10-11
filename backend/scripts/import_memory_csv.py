"""
Import a reviewed memory CSV into the one user's rows.

    PYTHONPATH=. uv run python scripts/import_memory_csv.py data/memory/import_proposal.csv

The CSV is the review surface (spec/done/users-profile.md): the user reads it,
corrects it, and only then does it land. Every imported row is therefore
confirmed at import time — the review is the confirmation. Idempotent: a slug
already present is updated, a profile column is set, a weigh-in for a day that
already has one is left alone.

Actions: import (a memory) · profile (a users column) · weigh-in · skip.
"""

import asyncio
import csv
import sys
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models.users import Memory, User, WeighIn
from scripts._user import pick_user

NUMERIC_COLS = {"height_cm", "weight_target_kg", "protein_g_target", "carbs_g_target",
                "fat_g_target", "fibre_g_target"}
INT_COLS = {"kcal_target", "sleep_target_min", "step_target", "savings_target_paise"}


async def main(path: str) -> None:
    now = datetime.now(UTC)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    async with SessionLocal() as s:
        uid = await pick_user(s)
        user = await s.get(User, uid)
        added = updated = cols = weighed = skipped = 0
        for r in rows:
            action = r["action"]
            if action == "import":
                found = await s.scalar(select(Memory).where(
                    Memory.user_id == uid, Memory.slug == r["slug"], Memory.deleted_at.is_(None)))
                if found:
                    found.text, found.kind, found.source, found.confirmed_at = (
                        r["text"], r["kind"], r["source"], now)
                    updated += 1
                else:
                    s.add(Memory(user_id=uid, slug=r["slug"], kind=r["kind"], text=r["text"],
                                 source=r["source"], confirmed_at=now))
                    added += 1
            elif action == "profile":
                col, raw = r["slug"], r["text"]
                value = (Decimal(raw) if col in NUMERIC_COLS
                         else int(raw) if col in INT_COLS else raw)
                setattr(user, col, value)
                cols += 1
            elif action == "weigh-in":
                day = date.fromisoformat(r["slug"])
                exists = await s.scalar(select(WeighIn.id).where(
                    WeighIn.user_id == uid, WeighIn.local_day == day, WeighIn.deleted_at.is_(None)))
                if exists is None:
                    s.add(WeighIn(user_id=uid, local_day=day, weight_kg=Decimal(r["text"]),
                                  note=r.get("note") or None))
                    weighed += 1
            else:
                skipped += 1
        await s.commit()
    print(f"memories: {added} added, {updated} updated · profile columns set: {cols} · "
          f"weigh-ins: {weighed} · skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "data/memory/import_proposal.csv"))
