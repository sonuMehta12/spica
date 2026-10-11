"""
The person. spec/in-progress/users-profile.md.

Two shapes, not one: columns for what has a unit (a protein target, a height),
rows for what has a sentence (profession, how they like to be spoken to).
`User` is the first; `Memory` is the second. `WeighIn` is a ledger because a
weight is a measurement over time — a single overwritten number cannot show
the trend that is the only reason to record it.

The lock arrived 2026-09-15 (spec/in-progress/sign-in.md): `google_sub` is the
identity a request proves, `Session` is what it proves it with.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Envelope, new_id

GRAMS = Numeric(6, 1)
KILOS = Numeric(5, 1)
CENTIMETRES = Numeric(4, 1)

MEMORY_KINDS = ("identity", "preference", "style", "interest", "project", "reference")
MEMORY_SOURCES = ("user", "claude-code", "claude", "chatgpt", "gemini", "cortex")


class User(Base):
    """One row per person. Targets are nullable: unset is unset, never 2,050."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    # identity
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    # Google's `sub` — unique and never reused, which the email is not: one
    # account can change address, so the address is a label and this is the id.
    google_sub: Mapped[str | None] = mapped_column(Text, unique=True)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    # Google's `picture`. Refreshed on every sign-in because the URL rotates.
    avatar_url: Mapped[str | None] = mapped_column(Text)
    # An age said as "28" is stored as 1 January of the birth year: only the
    # year means anything, so it is shown as an age, never as the date.
    dob: Mapped[date | None] = mapped_column(Date)
    # Categories the app computes with — diet limits the meal plan, gender
    # sizes it — so columns, not memories. Null is unanswered, never a default.
    gender: Mapped[str | None] = mapped_column(Text)
    height_cm: Mapped[Decimal | None] = mapped_column(CENTIMETRES)
    city: Mapped[str | None] = mapped_column(Text)
    diet: Mapped[str | None] = mapped_column(Text)
    # local_day depends on it; hardcoding it in the write path would make it
    # invisible the day it is wrong.
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="Asia/Kolkata")
    # money
    savings_target_paise: Mapped[int | None] = mapped_column(BigInteger)
    # food
    kcal_target: Mapped[int | None] = mapped_column(Integer)
    protein_g_target: Mapped[Decimal | None] = mapped_column(GRAMS)
    carbs_g_target: Mapped[Decimal | None] = mapped_column(GRAMS)
    fat_g_target: Mapped[Decimal | None] = mapped_column(GRAMS)
    fibre_g_target: Mapped[Decimal | None] = mapped_column(GRAMS)
    weight_target_kg: Mapped[Decimal | None] = mapped_column(KILOS)
    # rest and movement
    sleep_target_min: Mapped[int | None] = mapped_column(Integer)
    step_target: Mapped[int | None] = mapped_column(Integer)

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Finished or skipped the first run; set once, by the client, and it stays
    # set. The apps show the first run while it is null
    # (spec/done/onboarding-goals.md § Which flag).
    onboarding_done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The first run's answers today, and the local day they are counted for —
    # the cap behind `POST /onboarding/turn`'s 429. Each answer is a billed
    # model call the chat's turn limit never sees, and the turns are not
    # written to the thread, so there is no row to count; a counter on the
    # person is the smallest honest store (spec/done/onboarding-goals.md § A turn).
    onboarding_turns: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    onboarding_turns_day: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("gender IS NULL OR gender IN ('female', 'male', 'other')",
                        name="ck_users_gender"),
        CheckConstraint("diet IS NULL OR diet IN ('veg', 'nonveg', 'eggetarian', 'any')",
                        name="ck_users_diet"),
    )


class Session(Base):
    """
    One row per signed-in device. Not an `Envelope`: a session is not the
    user's data, and a soft delete would mean a revoked token still resolves.

    The raw token never lands here — only its SHA-256 — so a database dump
    cannot be replayed as a login.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Which door this token opens. `app` is the phone and the web client; `mcp`
    # is an OAuth access token for Spica's MCP server, which opens `/mcp` and
    # nothing else — a leaked routine token must not be able to read payments
    # (spec/work-sync.md § Auth). Each door refuses the other's key.
    scope: Mapped[str] = mapped_column(String(8), nullable=False, server_default="app")
    # The OAuth client an `mcp` token was issued to; NULL for `app` sessions.
    client_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("scope IN ('app','mcp')", name="ck_sessions_scope"),
    )


Index("ix_sessions_user", Session.user_id)


class WeighIn(Envelope, Base):
    """'Aaj 78.4' — one row per day. The profile holds the target; this holds the truth."""

    __tablename__ = "weigh_ins"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    local_day: Mapped[date] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(KILOS, nullable=False)
    # Said as a guess — "around 72". The one approximate answer people give
    # routinely; an exact reading the same day replaces it, and clears this.
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    note: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str | None] = mapped_column(Text)


# One weight per day; a second reading that day replaces the first. Partial so
# a soft-deleted row does not block the day forever. Declared after the class:
# the predicate needs the real column, which the mixin attribute is not until
# the class is built.
Index("uq_weigh_ins_user_day", WeighIn.user_id, WeighIn.local_day, unique=True,
      postgresql_where=WeighIn.deleted_at.is_(None))


class Memory(Envelope, Base):
    """
    A fact about the person, in their words, one row each. `slug` is the stable
    handle: 'profession' written by one agent and rewritten by another is one
    row, not two — which is the whole fix for memory scattered across apps.

    Facts about the person, never sentences about the person's data.
    """

    __tablename__ = "memories"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(11), nullable=False)
    # Last time the user said "yes, still true". Inferred is marked, confirmed is not.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "kind IN ('identity','preference','style','interest','project','reference')",
            name="ck_memories_kind",
        ),
        CheckConstraint(
            "source IN ('user','claude-code','claude','chatgpt','gemini','cortex')",
            name="ck_memories_source",
        ),
    )


Index("uq_memories_user_slug", Memory.user_id, Memory.slug, unique=True,
      postgresql_where=Memory.deleted_at.is_(None))
Index("ix_memories_user_kind", Memory.user_id, Memory.kind)
