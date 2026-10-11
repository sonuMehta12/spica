"""
Import the reviewed CSVs in backend/data/work/ into the database.

Same contract as the diet import: the CSVs were reviewed before this ran, so
this script types columns and adds no judgement. `came_from` is review-only
provenance and is deliberately not imported.

Idempotent: every row carries a stable id, so re-running inserts nothing.

    uv run python scripts/import_work_csv.py
"""

import asyncio
import csv
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models.work import Project, Task
from scripts._user import pick_user

DATA = Path(__file__).resolve().parent.parent / "data" / "work"
USER = ""  # the one user's id, read from the users table in main()


def rows(name):
    with (DATA / f"{name}.csv").open() as f:
        return list(csv.DictReader(f))


def txt(v):
    return v.strip() if v and v.strip() else None


async def main():
    global USER
    added = skipped = 0
    async with SessionLocal() as s:
        USER = await pick_user(s)
        have_p = set((await s.scalars(select(Project.id))).all())
        have_t = set((await s.scalars(select(Task.id))).all())

        for r in rows("projects"):
            if r["id"] in have_p:
                skipped += 1
                continue
            s.add(Project(id=r["id"], user_id=USER, key=r["key"],
                          name=r["name"], color=r["color"]))
            added += 1
        await s.flush()

        for r in rows("tasks"):
            if r["id"] in have_t:
                skipped += 1
                continue
            s.add(Task(
                id=r["id"], user_id=USER, title=r["title"], status=r["status"],
                done_at=datetime.fromisoformat(r["done_at"].replace("Z", "+00:00"))
                        .astimezone(UTC) if r["done_at"] else None,
                done_by=txt(r["done_by"]),
                due=date.fromisoformat(r["due"]) if r["due"] else None,
                priority=int(r["priority"]) if r["priority"] else None,
                labels=r["labels"].split("|") if r["labels"] else [],
                project_id=txt(r["project_id"]),
                source=r["source"], source_ref=txt(r["source_ref"]),
                doc_ref=txt(r["doc_ref"]), blocked_by=txt(r["blocked_by"]),
                repo=txt(r["repo"]), path=txt(r["path"]),
            ))
            added += 1

        await s.commit()
        print(f"added {added}, skipped {skipped} (already imported)")


if __name__ == "__main__":
    asyncio.run(main())
