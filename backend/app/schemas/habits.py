"""Wire shapes for the habit library. spec/in-progress/habits.md."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Row
from app.schemas.writes import Id, Patch

DIRECTION = r"^(build|break)$"


class HabitOut(Row):
    """A habit and how it has gone this week.

    `direction` has always been on the row and has never been on a screen.
    It is the whole point of the chain: a long run of ticks is progress on a
    `build` and a warning on a `break`.
    """

    id: str
    name: str
    direction: str
    #: What a tick can carry an amount in. NULL is a real state — a cigarette
    #: is counted, not measured, and a tick is the whole fact.
    unit: str | None
    #: Days ticked in the current week, Monday first. Counted per request;
    #: there is no stored streak to drift.
    days_this_week: int
    #: Ticks ever. `0` means it has never been logged, not that it is new.
    logged_ever: int


class HabitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    name: str = Field(min_length=1, max_length=60)
    direction: str = Field(pattern=DIRECTION)
    unit: str | None = Field(None, max_length=20)


class HabitPatch(Patch):
    name: str | None = Field(None, min_length=1, max_length=60)
    direction: str | None = Field(None, pattern=DIRECTION)
    unit: str | None = Field(None, max_length=20)
