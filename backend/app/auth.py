"""
Who is asking. The single seam for authentication.

Every endpoint takes the user id from HERE rather than hardcoding it, which was
the whole point of building the seam before the lock: the lock landed on
2026-09-15 inside this one function and no endpoint changed.

A request proves itself with an opaque bearer token. The database stores only
its SHA-256, so a dump cannot be replayed as a login, and signing out is a
DELETE — which is why a session row beats a signed token here. The server reads
the database on every request anyway, so statelessness would buy nothing and
cost revocation.

spec/in-progress/sign-in.md.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionDep
from app.models.users import Session

#: How long a session survives without use. A phone opened weekly never signs
#: in again; one left in a drawer does.
SESSION_DAYS = 90
#: `last_used_at` is a write, and writing it on every request would double the
#: cost of every read. Bumping it at most hourly keeps expiry honest to within
#: an hour, which is the resolution the 90-day window deserves.
TOUCH_AFTER = timedelta(hours=1)

UNAUTHENTICATED = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    "sign in",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue_session(session: AsyncSession, user_id: str, user_agent: str | None) -> str:
    """A new session for this user. Returns the raw token, which exists here and
    in the response and nowhere else — the row keeps only its hash."""
    raw = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    session.add(Session(
        user_id=user_id,
        token_hash=hash_token(raw),
        # Truncated: a header is attacker-controlled and this column exists only
        # so a future "your devices" list can name a row.
        user_agent=(user_agent or "")[:200] or None,
        expires_at=now + timedelta(days=SESSION_DAYS),
    ))
    return raw


def bearer(authorization: str | None) -> str | None:
    """The token out of an `Authorization: Bearer <token>` header, or None."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    raw = bearer(authorization)
    if raw is None:
        raise UNAUTHENTICATED

    # `app` only. An MCP access token is a row in the same table, and it opens
    # `/mcp` and nothing else — spec/work-sync.md § Auth. Refused as if it did
    # not exist, so a leaked routine token learns nothing about this door.
    row = await session.scalar(select(Session).where(
        Session.token_hash == hash_token(raw), Session.scope == "app"))
    if row is None:
        raise UNAUTHENTICATED

    now = datetime.now(UTC)
    if row.expires_at <= now:
        # Expired is gone, not merely refused: leaving the row would keep a dead
        # token in the table for as long as nobody signs in again.
        await session.delete(row)
        await session.commit()
        raise UNAUTHENTICATED

    if now - row.last_used_at > TOUCH_AFTER:
        row.last_used_at = now
        row.expires_at = now + timedelta(days=SESSION_DAYS)
        await session.commit()

    return row.user_id


# Endpoints write `user: CurrentUser` and get the id, knowing nothing about how
# it was established.
CurrentUser = Annotated[str, Depends(current_user)]
