"""
Which user a script acts on. spec/in-progress/sign-in.md § Scripts.

The request path proves identity with a token; a script has no request, so it
takes `--user <id>` and falls back to the only user when there is exactly one.
Guessing between two would silently write into the wrong person's ledger, so it
refuses instead.
"""

from sqlalchemy import select

from app.models.users import User


async def pick_user(session, user_id: str | None = None) -> str:
    if user_id:
        if await session.get(User, user_id) is None:
            raise SystemExit(f"no such user: {user_id}")
        return user_id
    ids = (await session.scalars(select(User.id).order_by(User.created_at))).all()
    if not ids:
        raise SystemExit("no users row — run the migrations")
    if len(ids) > 1:
        raise SystemExit(
            f"{len(ids)} users in this database — say which with --user <id>"
        )
    return ids[0]
