"""
Fill the one user's targets — only the ones still NULL.

These are the numbers the web prototype hardcoded in config.ts until the
profile row existed (and the workbook's Profile & Targets sheet before that).
Idempotent: a value the user has since edited is never overwritten.

    PYTHONPATH=. uv run python scripts/seed_targets.py
"""

import asyncio

from app.db import SessionLocal
from app.models.users import User
from scripts._user import pick_user

TARGETS = {
    "kcal_target": 2050,
    "protein_g_target": 135,
    "carbs_g_target": 243,
    "fat_g_target": 60,
    "fibre_g_target": 30,
    "sleep_target_min": 450,   # 7h 30m
    "step_target": 8000,
}


async def main() -> None:
    async with SessionLocal() as session:
        user = await session.get(User, await pick_user(session))
        filled = []
        for key, value in TARGETS.items():
            if getattr(user, key) is None:
                setattr(user, key, value)
                filled.append(key)
        await session.commit()
        print(f"user {user.id} ({user.display_name}): filled {filled or 'nothing'}")


if __name__ == "__main__":
    asyncio.run(main())
