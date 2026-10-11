"""
Spica's OAuth, for its own MCP endpoint. spec/work-sync.md § Auth.

claude.ai adds a custom connector by OAuth, so Spica is the front desk. The
MCP SDK owns the protocol — `/authorize`, `/token`, `/register`, `/revoke`,
the discovery documents, PKCE — and calls the provider below for storage. This
file decides only what Spica decides:

- **Who says yes.** `/authorize` sends the person to the app's own `/connect`
  page, where they are already signed in. Approval there is what mints the
  one-time code; registering a client grants nothing.
- **What a token is.** A `sessions` row with `scope = 'mcp'` — the same
  hash-in-a-table sign-in uses — so revoking Claude is deleting a row, and the
  REST API refuses the token without a special case (`app.auth`).

Every secret is stored as its SHA-256 only.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from sqlalchemy import delete, select, update

import app.db as db
from app.auth import hash_token
from app.config import settings
from app.models.oauth import OAuthClient, OAuthCode, OAuthRefreshToken
from app.models.users import Session

#: The one scope: tasks. Everything the MCP server can do is inside it, and
#: nothing outside it is reachable with it.
SCOPE = "tasks"
#: From `/authorize` to the person's yes, and from yes to the token exchange.
REQUEST_TTL = timedelta(minutes=10)
CODE_TTL = timedelta(minutes=5)


def now() -> datetime:
    return datetime.now(UTC)


def resource_url() -> str:
    return settings().public_url.rstrip("/") + "/mcp"


class SpicaOAuthProvider:
    """Storage for the SDK's OAuth handlers. A fresh DB session per call:
    these run inside the SDK's request handling, not a FastAPI dependency."""

    # ── clients ──────────────────────────────────────────────────────────────

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        async with db.SessionLocal() as s:
            row = await s.get(OAuthClient, client_id)
            return OAuthClientInformationFull.model_validate(row.info) if row else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        async with db.SessionLocal() as s:
            s.add(OAuthClient(client_id=client_info.client_id, name=client_info.client_name,
                              info=client_info.model_dump(mode="json", exclude_none=True)))
            await s.commit()

    # ── the request, and the person's yes ────────────────────────────────────

    async def authorize(self, client: OAuthClientInformationFull,
                        params: AuthorizationParams) -> str:
        """Park the request and send the browser to the app to ask.

        No code exists yet and no user is attached: both arrive when the person
        approves on `/connect` (`routes/oauth.py`)."""
        request = secrets.token_urlsafe(24)
        async with db.SessionLocal() as s:
            s.add(OAuthCode(
                request_hash=hash_token(request), client_id=client.client_id,
                redirect_uri=str(params.redirect_uri),
                redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
                code_challenge=params.code_challenge, state=params.state,
                scopes=params.scopes or [SCOPE], resource=params.resource,
                expires_at=now() + REQUEST_TTL,
            ))
            await s.commit()
        return f"{settings().app_url.rstrip('/')}/connect?request={request}"

    async def load_authorization_code(self, client: OAuthClientInformationFull,
                                      authorization_code: str) -> AuthorizationCode | None:
        async with db.SessionLocal() as s:
            row = await s.scalar(select(OAuthCode).where(
                OAuthCode.code_hash == hash_token(authorization_code),
                OAuthCode.client_id == client.client_id))
            # A used code never works again — replaying one is how a stolen
            # code gets tried.
            if row is None or row.used_at is not None or row.user_id is None:
                return None
            return AuthorizationCode(
                code=authorization_code, scopes=row.scopes,
                expires_at=row.expires_at.timestamp(), client_id=row.client_id,
                code_challenge=row.code_challenge, redirect_uri=row.redirect_uri,
                redirect_uri_provided_explicitly=row.redirect_uri_provided_explicitly,
                resource=row.resource, subject=row.user_id,
            )

    async def exchange_authorization_code(self, client: OAuthClientInformationFull,
                                          authorization_code: AuthorizationCode) -> OAuthToken:
        async with db.SessionLocal() as s:
            # Claimed in one statement, so two exchanges racing get one token.
            claimed = await s.execute(update(OAuthCode).where(
                OAuthCode.code_hash == hash_token(authorization_code.code),
                OAuthCode.used_at.is_(None)).values(used_at=now()))
            if claimed.rowcount != 1:
                raise TokenError("invalid_grant", "authorization code already used")
            token = await _issue(s, client, authorization_code.subject,
                                 authorization_code.scopes)
            await s.commit()
            return token

    # ── refresh ──────────────────────────────────────────────────────────────

    async def load_refresh_token(self, client: OAuthClientInformationFull,
                                 refresh_token: str) -> RefreshToken | None:
        async with db.SessionLocal() as s:
            row = await s.scalar(select(OAuthRefreshToken).where(
                OAuthRefreshToken.token_hash == hash_token(refresh_token),
                OAuthRefreshToken.client_id == client.client_id))
            if row is None or row.revoked_at is not None or row.expires_at <= now():
                return None
            return RefreshToken(token=refresh_token, client_id=row.client_id,
                                scopes=row.scopes, expires_at=int(row.expires_at.timestamp()),
                                subject=row.user_id)

    async def exchange_refresh_token(self, client: OAuthClientInformationFull,
                                     refresh_token: RefreshToken,
                                     scopes: list[str]) -> OAuthToken:
        """Rotate both. The old refresh token is revoked in the same statement
        that checks it, so a stolen copy works at most once."""
        async with db.SessionLocal() as s:
            revoked = await s.execute(update(OAuthRefreshToken).where(
                OAuthRefreshToken.token_hash == hash_token(refresh_token.token),
                OAuthRefreshToken.revoked_at.is_(None)).values(revoked_at=now()))
            if revoked.rowcount != 1:
                raise TokenError("invalid_grant", "refresh token already used")
            token = await _issue(s, client, refresh_token.subject,
                                 scopes or refresh_token.scopes)
            await s.commit()
            return token

    # ── access ───────────────────────────────────────────────────────────────

    async def load_access_token(self, token: str) -> AccessToken | None:
        async with db.SessionLocal() as s:
            row = await s.scalar(select(Session).where(
                Session.token_hash == hash_token(token), Session.scope == "mcp"))
            if row is None:
                return None
            if row.expires_at <= now():
                await s.delete(row)
                await s.commit()
                return None
            return AccessToken(token=token, client_id=row.client_id or "",
                               scopes=[SCOPE], expires_at=int(row.expires_at.timestamp()),
                               resource=resource_url(), subject=row.user_id)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        """Either token revokes the pair: this client loses this person."""
        async with db.SessionLocal() as s:
            await s.execute(delete(Session).where(
                Session.scope == "mcp", Session.client_id == token.client_id,
                Session.user_id == token.subject))
            await s.execute(update(OAuthRefreshToken).where(
                OAuthRefreshToken.client_id == token.client_id,
                OAuthRefreshToken.user_id == token.subject,
                OAuthRefreshToken.revoked_at.is_(None)).values(revoked_at=now()))
            await s.commit()

    async def exchange_identity_assertion(self, client, params) -> OAuthToken:
        raise TokenError("unsupported_grant_type", "not supported")


async def _issue(s, client: OAuthClientInformationFull, user_id: str | None,
                 scopes: list[str]) -> OAuthToken:
    """A new access token (a `sessions` row) and refresh token for this person."""
    if not user_id:
        raise TokenError("invalid_grant", "no person approved this")
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    cfg = settings()
    at = now()
    s.add(Session(user_id=user_id, token_hash=hash_token(access), scope="mcp",
                  client_id=client.client_id,
                  user_agent=f"MCP · {client.client_name or client.client_id}"[:200],
                  expires_at=at + timedelta(hours=cfg.mcp_access_hours)))
    s.add(OAuthRefreshToken(token_hash=hash_token(refresh), client_id=client.client_id,
                            user_id=user_id, scopes=scopes,
                            expires_at=at + timedelta(days=cfg.mcp_refresh_days)))
    return OAuthToken(access_token=access, token_type="Bearer",
                      expires_in=cfg.mcp_access_hours * 3600, refresh_token=refresh,
                      scope=" ".join(scopes))


# ─── the person's answer, called from the app ────────────────────────────────

async def pending(s, request: str) -> OAuthCode | None:
    """A request still waiting for an answer — not expired, not answered."""
    row = await s.scalar(select(OAuthCode).where(OAuthCode.request_hash == hash_token(request)))
    if row is None or row.approved_at is not None or row.expires_at <= now():
        return None
    return row


async def approve(s, row: OAuthCode, user_id: str) -> str:
    """Mint the one-time code for this person and say where the browser goes."""
    code = secrets.token_urlsafe(32)
    row.user_id, row.code_hash = user_id, hash_token(code)
    row.approved_at, row.expires_at = now(), now() + CODE_TTL
    await s.commit()
    return construct_redirect_uri(row.redirect_uri, code=code, state=row.state,
                                  iss=settings().public_url.rstrip("/"))


async def deny(s, row: OAuthCode) -> str:
    row.approved_at, row.expires_at = now(), now()
    await s.commit()
    return construct_redirect_uri(row.redirect_uri, error="access_denied",
                                  error_description="The person declined.", state=row.state)


__all__ = ["SpicaOAuthProvider", "SCOPE", "approve", "deny", "pending", "resource_url"]
