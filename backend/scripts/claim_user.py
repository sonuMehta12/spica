"""
Claim the seeded row for a Google account. Run once, ever.

This database has held one user since the migrations created it, and every
imported row points at that id. A first sign-in that created a *new* row would
strand all of it on a user nobody can sign in as. So the address goes on the
existing row first; the first sign-in from that Google account then finds it by
email and links `google_sub` to it.

    PYTHONPATH=. uv run python scripts/claim_user.py --email you@gmail.com

spec/in-progress/sign-in.md § Claiming the seeded row.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models.users import User


async def main(email: str, user_id: str | None) -> None:
    async with SessionLocal() as session:
        rows = (await session.scalars(select(User).order_by(User.created_at))).all()
        if not rows:
            raise SystemExit("no users row — run the migrations")
        if user_id:
            row = next((r for r in rows if r.id == user_id), None)
            if row is None:
                raise SystemExit(f"no such user: {user_id}")
        elif len(rows) > 1:
            # Picking one of several would hand somebody else's ledger to this
            # address, which is the one mistake this script must not make.
            raise SystemExit(f"{len(rows)} users here — say which with --user <id>")
        else:
            row = rows[0]

        if row.google_sub:
            raise SystemExit(f"{row.display_name} is already signed in as {row.email}")

        taken = await session.scalar(select(User).where(User.email == email.lower()))
        if taken is not None and taken.id != row.id:
            raise SystemExit(f"{email} is already on another row")

        row.email = email.lower()
        await session.commit()
        print(f"{row.display_name} ({row.id}) claims {row.email}")
        print("Sign in with that Google account and the ledger comes with it.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--email", required=True)
    p.add_argument("--user", default=None, help="which row, when there is more than one")
    a = p.parse_args()
    asyncio.run(main(a.email, a.user))
