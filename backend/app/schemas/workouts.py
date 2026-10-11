"""Wire shapes for the exercise library. spec/done/workouts.md.

No session shapes and no star. A workout is logged as a habit — yes or no — so
nothing here records what was done; `tried` on the row is the whole story.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Row
from app.schemas.writes import Id, Patch

KIND = r"^(strength|cardio|mobility|stretch)$"
SOURCE = r"^(seed|chat|link|manual)$"


class ExerciseOut(Row):
    """One library row — everything a suggestion is made from, plus how well
    you know it."""

    id: str
    name: str
    aliases: list[str]
    """Separate from `muscle_group`: cardio is not a muscle."""
    kind: str | None
    muscle_group: str | None
    equipment: str | None
    typical_minutes: int | None

    steps: str | None
    source_url: str | None
    image_url: str | None
    source: str
    note: str | None

    """0 means bookmarked but never done. Stored, because there is no ledger of
    exercises to count — a workout is a habit tick."""
    tried: int
    last_tried: date | None


class ExerciseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    name: str = Field(min_length=1, max_length=120)
    """What you call it — "OHP" — so a spoken request finds it."""
    aliases: list[str] = []
    kind: str | None = Field(default=None, pattern=KIND)
    muscle_group: str | None = Field(default=None, max_length=40)
    equipment: str | None = Field(default=None, max_length=40)
    typical_minutes: int | None = Field(default=None, ge=1, le=600)

    steps: str | None = None
    source_url: str | None = None
    image_url: str | None = None
    # Where it came from. 'seed' is the importer's; a client says how it
    # arrived — typed, said in conversation, or shared as a link.
    source: str = Field(default="manual", pattern=SOURCE)
    note: str | None = None
    # Accepted on create so an exercise you already know does not start at zero.
    tried: int = Field(default=0, ge=0)
    last_tried: date | None = None


class ExercisePatch(Patch):
    """Every field, `tried` included — a miscount is corrected deliberately,
    never by an endpoint that decrements."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    aliases: list[str] | None = None
    kind: str | None = Field(default=None, pattern=KIND)
    muscle_group: str | None = Field(default=None, max_length=40)
    equipment: str | None = Field(default=None, max_length=40)
    typical_minutes: int | None = Field(default=None, ge=1, le=600)
    steps: str | None = None
    source_url: str | None = None
    image_url: str | None = None
    note: str | None = None
    tried: int | None = Field(default=None, ge=0)
    last_tried: date | None = None


class DidIt(BaseModel):
    """`tried += 1` and a date, in one write — so a client never reads a
    counter and writes it back."""

    model_config = ConfigDict(extra="forbid")

    local_day: date | None = None
