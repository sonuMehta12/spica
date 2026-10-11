"""
What Spica does on its own, and when. spec/in-progress/schedules.md.

One row per job the user has scheduled. The row holds **everything a run
needs** — the time, how it repeats, how late is too late, and `params` for
whatever that job takes. Code holds only what is true of the job itself: its
function and the defaults a new row starts from. A constant read out of a
Python file would be a setting the user cannot see and cannot change, which is
the thing this table exists to stop.
"""

from datetime import date, datetime, time

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Envelope

REPEATS = ("daily", "weekly", "once")


class Schedule(Envelope, Base):
    """One scheduled job. `job` names code; everything else is the user's."""

    __tablename__ = "schedules"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    #: Which job to run — a closed vocabulary, validated against the registry.
    #: Free text here would let a row point at nothing while looking like it works.
    job: Mapped[str] = mapped_column(Text, nullable=False)
    #: The user's clock on the user's day, like `local_day` everywhere else.
    at_local_time: Mapped[time] = mapped_column(Time, nullable=False)
    repeat: Mapped[str] = mapped_column(Text, nullable=False, server_default="daily")
    #: 0=Monday … 6=Sunday, read only when `repeat` is weekly.
    days: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, server_default="{}")
    #: What this job is run *with*. JSONB because each job takes something
    #: different and nothing ever aggregates over one key — the same case the
    #: prediction signals make.
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    #: How late is still worth running. A nightly review missed while the
    #: laptop was shut is worth having in the morning; a morning brief at 6pm
    #: is not late, it is wrong.
    grace_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="4")

    #: The day it last ran, in the user's local days — not a timestamp. That is
    #: what makes a tick that fires twice, or a dispatcher run by hand, unable
    #: to run a job twice in one day.
    last_run_local_day: Mapped[date | None] = mapped_column(Date)
    #: When, for the row the UI draws. Display only; nothing decides on it.
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: The last failure, kept until a run succeeds. A scheduled job that
    #: silently stopped working is worse than one that was never built.
    last_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(f"repeat IN {REPEATS}", name="ck_schedules_repeat"),
        CheckConstraint("grace_hours > 0", name="ck_schedules_grace"),
        CheckConstraint("repeat <> 'weekly' OR cardinality(days) > 0",
                        name="ck_schedules_weekly_has_days"),
    )


# One schedule per job, and a retired one frees the name — the partial-index
# rule every other table in this schema follows.
Index("uq_schedules_user_job", Schedule.user_id, Schedule.job, unique=True,
      postgresql_where=Schedule.deleted_at.is_(None))
