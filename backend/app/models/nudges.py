"""
What Spica says without being asked. spec/in-progress/nudges.md.

A scheduled job that has something to say writes **nudges**, never a turn in
the thread: an unprompted message in the person's conversation reads as a
message nobody sent — the reason the time-of-day greeting was taken out. The
thread hears about a nudge only when the person hands it over.

One row per thing said. The morning brief writes three — Your day, Meals
today, Workout — so each has its own page and its own done state.
"""

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Envelope

KINDS = ("day", "meals", "workout", "dinner", "reminder", "review")


class Nudge(Envelope, Base):
    """One thing a run said, and what the person has done about it."""

    __tablename__ = "nudges"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    #: Which page it opens. A closed vocabulary: the phone draws a page per
    #: kind, so a kind it does not know would be a card leading nowhere.
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    #: The run that made it. Every nudge names one — nothing nudges from a
    #: hidden trigger — and *Turn these off* switches that schedule off.
    #: Nullable so a nudge outlives a schedule removed later.
    schedule_id: Mapped[str | None] = mapped_column(Text, ForeignKey("schedules.id"))
    #: The person's day it belongs to. It expires with that day: yesterday's
    #: are *Earlier* and read-only, and after seven they are off the page.
    local_day: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    #: What the agent said at that hour — history, like any chat message, and
    #: the one stored sentence. Never shown as a claim about now: every number
    #: on the nudge's page is worked out from the rows when it is drawn. Null
    #: when the card says nothing of its own (Meals today shows the plan live).
    line: Mapped[str | None] = mapped_column(Text)
    #: Live ids only — tasks, dishes, the plan's day, transactions — so a row
    #: deleted since 8:00 drops off the page instead of being quoted from a
    #: snapshot.
    refs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    #: Opened. What clears the card's dot.
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Acted on — a meal logged from the plan, a task ticked, the last question
    #: answered, *Done*. The card says so.
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: *Not today*, or dismissed from ⋮: hidden for the day, not deleted.
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"kind IN {KINDS}", name="ck_nudges_kind"),
        # The page reads one person's last seven days, and nothing else.
        Index("ix_nudges_user_day", "user_id", "local_day"),
    )
