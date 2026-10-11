"""
The door. spec/in-progress/sign-in.md.

One way in: a Google ID token, verified against Google's public keys, exchanged
for a Spica session token. The Android app's Credential Manager produces the
same token against the same Web client ID, so this one route serves both
clients and the check does not change.

No refresh token is ever requested and no Google API is called on the user's
behalf — the ID token is read once and thrown away.
"""

import asyncio
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.auth import CurrentUser, bearer, hash_token, issue_session
from app.config import settings
from app.db import SessionDep
from app.models.users import Session, User
from app.schemas.users import UserOut

router = APIRouter(tags=["auth"])


class GoogleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: str


class SessionOut(BaseModel):
    token: str
    user: UserOut


def may_create(email: str) -> bool:
    """`ALLOWED_EMAILS` is a list of addresses, or `*` for anyone with a
    verified Google account. It gates creation only — an existing user always
    signs in, whatever the list says, so removing an address never locks
    someone out of their own ledger."""
    allowed = settings().allowed_emails.strip()
    if allowed == "*":
        return True
    return email.lower() in {e.strip().lower() for e in allowed.split(",") if e.strip()}


REFUSED = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    "that sign-in could not be verified",
    headers={"WWW-Authenticate": "Bearer"},
)


def _verify_blocking(credential: str) -> dict:
    """Signature, audience and expiry, against Google's own keys.

    Nothing but the call: `google-auth`'s transport is synchronous and fetches
    the signing keys over the network (cached between calls), so this runs off
    the event loop — and everything that is a *decision* about the claims sits
    in `verify` below, where it can be read and tested without a network.
    """
    client_id = settings().google_client_id
    if not client_id:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "sign-in is not configured on this server"
        )
    return google_id_token.verify_oauth2_token(
        credential, google_requests.Request(), client_id
    )


async def verify(credential: str) -> dict:
    """A bad credential is a 401, never a 422: it is not the shape of the
    request that is wrong, and saying which check failed only helps whoever
    sent it."""
    try:
        claims = await asyncio.to_thread(_verify_blocking, credential)
    except ValueError:
        raise REFUSED from None
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise REFUSED
    if not claims.get("email") or not claims.get("email_verified"):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "that Google account has no verified email"
        )
    return claims


@router.post("/auth/google", status_code=status.HTTP_200_OK)
async def google(
    body: GoogleIn,
    session: SessionDep,
    user_agent: Annotated[str | None, Header()] = None,
) -> SessionOut:
    claims = await verify(body.credential)
    sub, email = claims["sub"], claims["email"].lower()

    row = await session.scalar(select(User).where(User.google_sub == sub))

    if row is None:
        # Claiming: a row that already carries this email but no identity is
        # this person's — this is how the seeded row, and everything imported
        # against it, comes under the account instead of being stranded.
        row = await session.scalar(
            select(User).where(func.lower(User.email) == email, User.google_sub.is_(None))
        )

    if row is None:
        if not may_create(email):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Spica is invite-only right now")
        if await signups_today(session) >= settings().daily_signup_limit:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Spica is invite-only right now")
        row = User(display_name=claims.get("given_name") or claims.get("name") or "")
        session.add(row)

    # Google owns these three; refresh them every time rather than keeping a
    # picture URL that has since rotated away.
    row.google_sub = sub
    row.email = email
    row.avatar_url = claims.get("picture")
    row.last_seen_at = datetime.now(UTC)

    await session.flush()
    token = await issue_session(session, row.id, user_agent)
    await session.commit()
    await session.refresh(row)
    return SessionOut(token=token, user=UserOut.model_validate(row))


async def signups_today(session) -> int:
    """A door that can be opened by a link on the internet can be walked
    through by a script. This caps the damage at a day's worth."""
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return await session.scalar(
        select(func.count()).select_from(User).where(User.created_at >= since)
    ) or 0


@router.delete("/auth/session", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(
    session: SessionDep,
    user: CurrentUser,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """This device only. Other devices keep their sessions, because signing out
    of a laptop should not sign out the phone."""
    raw = bearer(authorization)
    if raw:
        row = await session.scalar(select(Session).where(Session.token_hash == hash_token(raw)))
        if row is not None:
            await session.delete(row)
            await session.commit()
