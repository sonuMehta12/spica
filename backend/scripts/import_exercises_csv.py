"""
Seed the exercise library from data/workouts/exercises.csv.

Idempotent on name — re-running corrects a row rather than adding a second one,
so the CSV stays the source of truth while it is being reviewed.

`steps` is deliberately not in the CSV. Writing forty form guides from memory is
forty chances to teach a lift wrongly; they arrive per exercise, from a real
source, with the link beside them. spec/done/workouts.md.
"""

import asyncio
import csv
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402
from app.models.diet import Exercise  # noqa: E402
from app.models.users import User  # noqa: E402

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "workouts" / "exercises.csv"


async def main() -> None:
    load_dotenv()
    # The settings' URL, not the raw variable: it is normalised, so a
    # provider's string (Neon's sslmode=require) works as given.
    engine = create_async_engine(settings().database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    added = updated = 0
    async with Session() as session:
        user_id = await session.scalar(select(User.id).order_by(User.created_at).limit(1))
        if user_id is None:
            raise SystemExit("no user row — the library belongs to someone")
        with CSV_PATH.open() as fh:
            for row in csv.DictReader(fh):
                name = row["name"].strip()
                fields = {
                    "aliases": [a.strip() for a in row["aliases"].split(";") if a.strip()],
                    "kind": row["kind"].strip() or None,
                    "muscle_group": row["muscle_group"].strip() or None,
                    "equipment": row["equipment"].strip() or None,
                    "typical_minutes": (int(row["typical_minutes"])
                                        if row["typical_minutes"].strip() else None),
                }
                found = await session.scalar(select(Exercise).where(
                    Exercise.user_id == user_id, Exercise.name == name,
                    Exercise.deleted_at.is_(None)))
                if found is None:
                    session.add(Exercise(name=name, user_id=user_id, source="seed", **fields))
                    added += 1
                else:
                    # `tried`, `steps` and `note` are the user's — never reset
                    # by a re-import of the catalogue.
                    for key, value in fields.items():
                        setattr(found, key, value)
                    updated += 1
        await session.commit()
    print(f"{added} added, {updated} updated")


if __name__ == "__main__":
    asyncio.run(main())
