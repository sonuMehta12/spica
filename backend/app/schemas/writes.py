"""
What the client may send. spec/in-progress/ledger-writes.md.

Two shapes per kind. `…In` is a full row for POST — required fields required,
optional ones default to NULL, nothing invented server-side. `…Patch` is every
editable field made optional, so a PATCH sends only what changes; a field left
out is left alone, a field sent as null is cleared.

Never accepted from the client: `user_id` (comes from the auth seam),
`created_at` / `updated_at` / `deleted_at` (the server's), and on PATCH also
`id` and `source` — facts about where a row came from, not about what happened.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ULIDs are 26 chars; task ids are the 4-char file markers. Anything in between
# is fine — the id is opaque, the client owns it.
Id = Field(min_length=4, max_length=26, pattern=r"^[0-9A-Za-z_-]+$")


class Patch(BaseModel):
    """Marker base: every field optional, and the route applies only the ones
    the client actually sent (`model_dump(exclude_unset=True)`)."""

    model_config = ConfigDict(extra="forbid")


# ─── transactions ────────────────────────────────────────────────────────────

class TransactionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    occurred_at: datetime
    local_day: date
    amount_paise: int = Field(gt=0)
    direction: str = Field(pattern=r"^(debit|credit)$")
    kind: str = Field(pattern=r"^(expense|income|lent|borrowed|repayment|transfer)$")
    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: str = Field(pattern=r"^(manual|notification)$")

    note: str | None = None
    tags: list[str] = []
    # The obligation this pays, if the client knows which. Left out, an expense
    # is linked to the one open commitment in its category, as a marked guess.
    commitment_id: str | None = None
    method: str | None = Field(None, pattern=r"^(cash|digital)$")
    counterparty_name: str | None = None
    counterparty_id: str | None = None
    place_id: str | None = None
    # Where the phone was. An observation, so it arrives with the payment and
    # is never edited afterwards — a wrong *match* is fixed by clearing
    # `place_id`, which is why the fix stays beside it.
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    fix_accuracy_m: float | None = Field(None, gt=0)
    settles_id: str | None = None
    confidence: float = Field(1.0, ge=0, le=1)
    dedupe_key: str | None = None

    @model_validator(mode="after")
    def whole_fix(self):
        """Half a coordinate is not a location. The database says so too, but a
        check constraint surfaces as a stack trace; the client deserves a
        sentence."""
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat and lng go together")
        return self


class TransactionPatch(Patch):
    occurred_at: datetime | None = None
    local_day: date | None = None
    amount_paise: int | None = Field(None, gt=0)
    direction: str | None = Field(None, pattern=r"^(debit|credit)$")
    kind: str | None = Field(None, pattern=r"^(expense|income|lent|borrowed|repayment|transfer)$")
    category: str | None = None
    description: str | None = None
    note: str | None = None
    tags: list[str] | None = None
    # Set to move the link (a statement); null for *Not a commitment*.
    commitment_id: str | None = None
    method: str | None = Field(None, pattern=r"^(cash|digital)$")
    counterparty_name: str | None = None
    counterparty_id: str | None = None
    # Redoing the match is the whole reason the fix sits on the row. The fix
    # itself is not patchable: it is what the phone read, not a decision.
    place_id: str | None = None
    settles_id: str | None = None
    confidence: float | None = Field(None, ge=0, le=1)


# ─── meals ───────────────────────────────────────────────────────────────────

class MealItemIn(BaseModel):
    """One line of the plate. Exactly one of `dish_id` or `food_id`: *dal* is a
    dish, *2 roti* is a food and a quantity."""

    model_config = ConfigDict(extra="forbid")

    dish_id: str | None = None
    food_id: str | None = None
    servings: Decimal | None = Field(None, gt=0)
    quantity: int | None = Field(None, gt=0)
    #: The user's own words for this line, before it was resolved.
    said: str | None = None
    #: exact | alias | similar | id — only the certain ones may spend.
    rung: str | None = None

    @model_validator(mode="after")
    def one_target(self):
        if bool(self.dish_id) == bool(self.food_id):
            raise ValueError("a line points at exactly one of dish_id or food_id")
        return self


class MealIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    occurred_at: datetime
    local_day: date
    meal_type: str = Field(min_length=1)   # free text — 'Grazing' is a real value
    dish: str = Field(min_length=1)
    kcal: int = Field(ge=0)
    protein_g: Decimal = Field(ge=0)
    carbs_g: Decimal | None = Field(None, ge=0)   # unknown = omit, never 0
    fat_g: Decimal | None = Field(None, ge=0)
    fibre_g: Decimal | None = Field(None, ge=0)
    # What the model said before the user touched it — frozen at log time and
    # never updated. spec/in-progress/meal-estimates.md § the pair.
    estimated_kcal: int | None = Field(None, ge=0)
    estimated_protein_g: Decimal | None = Field(None, ge=0)
    estimated_carbs_g: Decimal | None = Field(None, ge=0)
    estimated_fat_g: Decimal | None = Field(None, ge=0)
    estimated_fibre_g: Decimal | None = Field(None, ge=0)
    source: str = Field(pattern=r"^(manual|photo)$")

    # Set this and the pantry is spent — see the route.
    ingredients: str | None = None
    cooked_home: bool | None = None
    note: str | None = None
    tags: list[str] = []
    confidence: float = Field(1.0, ge=0, le=1)
    dedupe_key: str | None = None
    #: The plate, line by line. Written before the pantry is spent, because
    #: `spend()` walks these — a meal posted without them takes nothing out of
    #: the house, which is what happened until 2026-09-12.
    items: list[MealItemIn] = []


class MealPatch(Patch):
    occurred_at: datetime | None = None
    local_day: date | None = None
    meal_type: str | None = None
    dish: str | None = None
    kcal: int | None = Field(None, ge=0)
    protein_g: Decimal | None = Field(None, ge=0)
    carbs_g: Decimal | None = Field(None, ge=0)
    fat_g: Decimal | None = Field(None, ge=0)
    fibre_g: Decimal | None = Field(None, ge=0)
    ingredients: str | None = None
    cooked_home: bool | None = None
    note: str | None = None
    tags: list[str] | None = None
    confidence: float | None = Field(None, ge=0, le=1)


# ─── habit logs ──────────────────────────────────────────────────────────────

class HabitLogIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    habit_id: str
    occurred_at: datetime
    local_day: date
    source: str = Field(pattern=r"^(manual|photo)$")
    amount: float | None = None            # NULL = it happened, that is all
    note: str | None = None
    dedupe_key: str | None = None


class HabitLogPatch(Patch):
    occurred_at: datetime | None = None
    local_day: date | None = None
    amount: float | None = None
    note: str | None = None


# ─── tasks ───────────────────────────────────────────────────────────────────

class TaskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)      # 'self' | 'linear' | 'email' | 'meeting' | 'file' …
    status: str = Field("open", pattern=r"^(open|doing|done)$")
    due: date | None = None
    priority: int | None = Field(None, ge=1, le=3)
    labels: list[str] = []
    project_id: str | None = None
    source_ref: str | None = None
    doc_ref: str | None = None
    blocked_by: str | None = None
    repo: str | None = None
    path: str | None = None
    line: int | None = None


class TaskPatch(Patch):
    title: str | None = None
    status: str | None = Field(None, pattern=r"^(open|doing|done)$")
    due: date | None = None
    priority: int | None = Field(None, ge=1, le=3)
    labels: list[str] | None = None
    project_id: str | None = None
    source_ref: str | None = None
    doc_ref: str | None = None
    blocked_by: str | None = None
    archived: bool | None = None           # true sets archived_at, false clears it


# ─── pantry moves ────────────────────────────────────────────────────────────

class PantryMoveIn(BaseModel):
    """Stock arriving, a stock-take, waste, or a correction the user states.
    Consumption is never posted by hand — POST /meals writes it."""

    model_config = ConfigDict(extra="forbid")

    id: str = Id
    food_id: str
    occurred_at: datetime
    local_day: date
    # Signed, in the food's own unit — grams, ml or pieces.
    quantity: int
    kind: str = Field(pattern=r"^(purchase|opening|correction|waste)$")
    note: str | None = None
    dedupe_key: str | None = None


class PantryMovePatch(Patch):
    occurred_at: datetime | None = None
    local_day: date | None = None
    quantity: int | None = None
    kind: str | None = Field(None, pattern=r"^(purchase|opening|correction|waste)$")
    note: str | None = None


# ─── days ────────────────────────────────────────────────────────────────────

class DayIn(BaseModel):
    """Only what meals and habits cannot derive: sleep, weight, whether the day
    was fully logged. Upserted by local day — one row per person per day."""

    model_config = ConfigDict(extra="forbid")

    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    weight_kg: float | None = Field(default=None, gt=0, lt=500)
    # NULL = unknown. FALSE = the user said there is more. TRUE = that was all.
    log_complete: bool | None = None
    note: str | None = None

