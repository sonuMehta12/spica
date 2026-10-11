"""Wire shapes for the person. spec/in-progress/users-profile.md § What the API adds."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import Row
from app.schemas.writes import Id, Patch

MemoryKind = Literal["identity", "preference", "style", "interest", "project", "reference"]
MemorySource = Literal["user", "claude-code", "claude", "chatgpt", "gemini", "cortex"]
Gender = Literal["female", "male", "other"]
Diet = Literal["veg", "nonveg", "eggetarian", "any"]


class UserOut(Row):
    id: str
    display_name: str
    # Shown in the Profile header: the one place that answers *which account
    # am I signed in as*, which has to be answerable before someone taps sign out.
    email: str | None
    avatar_url: str | None
    dob: date | None
    gender: str | None
    height_cm: Decimal | None
    city: str | None
    diet: str | None
    timezone: str
    savings_target_paise: int | None
    kcal_target: int | None
    protein_g_target: Decimal | None
    carbs_g_target: Decimal | None
    fat_g_target: Decimal | None
    fibre_g_target: Decimal | None
    weight_target_kg: Decimal | None
    sleep_target_min: int | None
    step_target: int | None
    onboarding_done_at: datetime | None
    updated_at: datetime


class UserPatch(Patch):
    """Any subset of the editable columns. id and created_at are not here, so
    they cannot be sent."""

    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    dob: date | None = None
    gender: Gender | None = None
    height_cm: Decimal | None = Field(default=None, gt=0, lt=300)
    city: str | None = None
    diet: Diet | None = None
    timezone: str | None = Field(default=None, min_length=1)
    # Upper bounds are the columns' own limits (NUMERIC(6,1) etc.), so a typo
    # like 135140 g is refused with a 422 the client can show, not a 500.
    savings_target_paise: int | None = Field(default=None, ge=0, lt=10**12)
    kcal_target: int | None = Field(default=None, gt=0, lt=20_000)
    protein_g_target: Decimal | None = Field(default=None, gt=0, lt=10_000)
    carbs_g_target: Decimal | None = Field(default=None, gt=0, lt=10_000)
    fat_g_target: Decimal | None = Field(default=None, gt=0, lt=10_000)
    fibre_g_target: Decimal | None = Field(default=None, gt=0, lt=10_000)
    weight_target_kg: Decimal | None = Field(default=None, gt=0, lt=500)
    sleep_target_min: int | None = Field(default=None, gt=0, lt=1_440)
    step_target: int | None = Field(default=None, gt=0, lt=200_000)
    # The client sets this when the first run is finished or skipped; a null
    # once it is set is ignored. Email, avatar and google_sub are deliberately
    # absent: Google owns them.
    onboarding_done_at: datetime | None = None

    @model_validator(mode="after")
    def a_name_and_a_real_birthday(self):
        """Every field clears with null but the name, which can be changed and
        never removed (spec/done/onboarding-goals.md § Profile) — the column is NOT
        NULL, so a null used to reach it and come back a 500. A date of birth
        is a day already lived: one in the future read "Age → -4 years"."""
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("the name can be changed, not removed")
        if self.dob is not None and not date(1900, 1, 1) <= self.dob <= date.today():
            raise ValueError("a date of birth is between 1900 and today")
        return self


class WeighInIn(BaseModel):
    # A typo in a client is a 422, never a silently ignored field.
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    local_day: date
    weight_kg: Decimal = Field(gt=0, lt=500)
    #: Said as a guess ("around 72"). Sent on the same-day replace too, so an
    #: exact reading clears it.
    estimated: bool = False
    note: str | None = None


class WeighInOut(Row):
    id: str
    local_day: date
    weight_kg: Decimal
    estimated: bool
    note: str | None
    updated_at: datetime


class MemoryIn(BaseModel):
    # A typo in a client is a 422, never a silently ignored field.
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    slug: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$")
    kind: MemoryKind
    text: str = Field(min_length=1, max_length=2000)
    source: MemorySource = "user"


class MemoryPatch(Patch):
    slug: str | None = Field(
        default=None, min_length=1, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$"
    )
    kind: MemoryKind | None = None
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    confirmed_at: datetime | None = None


class MemoryOut(Row):
    id: str
    slug: str
    kind: str
    text: str
    source: str
    confirmed_at: datetime | None
    updated_at: datetime
