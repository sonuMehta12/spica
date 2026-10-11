"""
Spica as an OAuth 2.1 authorization server for its own MCP endpoint.
spec/work-sync.md § Auth.

claude.ai adds a custom connector by OAuth, so Spica plays the front desk:
a client registers, the person approves it once in the app, and the client
swaps a one-time code for tokens. The access token itself is a `sessions` row
with `scope = 'mcp'` — the same hash-in-a-table sign-in already uses — so these
tables hold only what OAuth adds around it.

None of these is an `Envelope`, for the reason `sessions` is not: a credential
is not the user's data, and a soft-deleted one must not resolve.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id


class OAuthClient(Base):
    """A client that registered itself (RFC 7591). Registering proves nothing
    about anyone — it is the person's approval that grants access — so the
    SDK's full registration record is kept as it arrived."""

    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    info: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OAuthCode(Base):
    """One authorization, from the request to the one-time code.

    Born when a client hits `/authorize`, with no user and no code: the person
    has not said yes yet. Approval fills in `user_id` and `code_hash`; the
    token exchange stamps `used_at`, after which the code never works again.
    Both secrets are stored as SHA-256 only.
    """

    __tablename__ = "oauth_codes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    # The consent page's handle for this request — in the URL, so hashed here.
    request_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    code_hash: Mapped[str | None] = mapped_column(Text, unique=True)
    client_id: Mapped[str] = mapped_column(
        Text, ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"))
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri_provided_explicitly: Mapped[bool] = mapped_column(nullable=False)
    code_challenge: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    resource: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OAuthRefreshToken(Base):
    """What lets a routine keep its access after the access token expires.
    Rotated on every use: the old one is revoked the moment a new pair is
    issued, so a stolen copy works at most once."""

    __tablename__ = "oauth_refresh_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    client_id: Mapped[str] = mapped_column(
        Text, ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


Index("ix_oauth_refresh_tokens_user_client", OAuthRefreshToken.user_id, OAuthRefreshToken.client_id)
