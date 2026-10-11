"""What the client may say about a schedule. spec/in-progress/schedules.md."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.writes import Id, Patch

REPEAT = r"^(daily|weekly|once)$"


class ScheduleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    job: str = Field(min_length=1)
    at_local_time: time
    repeat: str = Field("daily", pattern=REPEAT)
    #: 0=Monday … 6=Sunday, read only when `repeat` is weekly.
    days: list[int] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)
    enabled: bool = True
    grace_hours: int = Field(4, gt=0, le=24)


class SchedulePatch(Patch):
    at_local_time: time | None = None
    repeat: str | None = Field(None, pattern=REPEAT)
    days: list[int] | None = None
    params: dict | None = None
    enabled: bool | None = None
    grace_hours: int | None = Field(None, gt=0, le=24)


class ScheduleOut(BaseModel):
    """The row, plus what the registry says about the job — so the UI can draw
    a name and an explanation without knowing the vocabulary."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    job: str
    label: str
    blurb: str
    at_local_time: time
    repeat: str
    days: list[int]
    params: dict
    enabled: bool
    grace_hours: int
    last_run_local_day: date | None
    last_run_at: datetime | None
    last_error: str | None
    #: True when this schedule is past its time today and has not run — what
    #: the row says under the name, so "did it run" is answerable at a glance.
    due_now: bool
