"""
The wire shape of GET /deck.

Written out rather than serialising the ORM directly, so the API's contract is
a decision instead of a side effect of the schema. Adding a column to a table
must not silently start publishing it.

What is left out on purpose: `created_at` / `updated_at` / `deleted_at` (the
deck is a read of what is live), and `user_id` (the caller already is the user).
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Row
from app.schemas.users import UserOut


class TransactionOut(Row):
    id: str
    local_day: date
    occurred_at: datetime
    # Integer paise, formatted at the very edge — never in the database and
    # never on the wire.
    amount_paise: int
    direction: str
    kind: str
    category: str
    description: str
    note: str | None
    tags: list[str]
    #: The commitment it pays, if any; a linked payment is not discretionary spend.
    commitment_id: str | None
    #: The link was guessed from the category — an amber dot until confirmed.
    commitment_inferred: bool
    method: str | None
    counterparty_name: str | None
    counterparty_id: str | None
    place_id: str | None
    settles_id: str | None
    source: str
    confidence: float


class TransactionRowOut(TransactionOut):
    """A row asked for by id (`GET /transactions?ids=`). The one read that
    returns deleted rows, so a card that named one can say it used to be
    there rather than silently losing it."""

    deleted_at: datetime | None


class BalanceCheckOut(Row):
    id: str
    as_of: date
    amount_paise: int
    note: str | None


class MealOut(Row):
    id: str
    local_day: date
    occurred_at: datetime
    meal_type: str
    dish: str
    kcal: int
    protein_g: Decimal
    carbs_g: Decimal | None
    fat_g: Decimal | None
    fibre_g: Decimal | None = None
    #: What the model said before the user touched it, and when they did. The
    #: gap between these and the values above is the error, kept on purpose.
    estimated_kcal: int | None = None
    estimated_protein_g: Decimal | None = None
    estimated_carbs_g: Decimal | None = None
    estimated_fat_g: Decimal | None = None
    estimated_fibre_g: Decimal | None = None
    corrected_at: datetime | None = None
    cooked_home: bool | None
    note: str | None
    tags: list[str]
    confidence: float


class MealRowOut(MealOut):
    """`GET /meals?ids=` — see TransactionRowOut."""

    deleted_at: datetime | None


class HabitOut(Row):
    id: str
    name: str
    direction: str
    unit: str | None


class HabitLogOut(Row):
    id: str
    habit_id: str
    local_day: date
    amount: float | None
    note: str | None


class DayOut(Row):
    id: str
    local_day: date
    # NULL means unknown, and the card must not read it as complete.
    log_complete: bool | None
    weight_kg: float | None
    sleep_hours: float | None
    note: str | None


class PantryMoveOut(Row):
    id: str
    food_id: str
    local_day: date
    quantity: int
    kind: str
    meal_log_id: str | None
    note: str | None


class ProjectOut(Row):
    id: str
    key: str
    name: str
    color: str
    description: str | None = None
    icon: str | None = None
    aliases: list[str] = []
    is_default: bool = False


class TaskOut(Row):
    id: str
    title: str
    status: str
    done_at: datetime | None
    due: date | None
    priority: int | None
    labels: list[str]
    project_id: str | None
    # The model chose the project — the amber dot (spec/done/projects.md).
    project_guessed: bool = False
    source: str
    source_ref: str | None
    doc_ref: str | None
    blocked_by: str | None
    # Provenance for the 'kahan likha tha' line.
    repo: str | None
    path: str | None
    line: int | None
    # A tracker's stage and the reminder it drives (spec/work-sync.md). The
    # stage is the team's own word; `awaiting_move` is derived from the row.
    source_state: str | None = None
    tracked: bool = False
    awaiting_move: bool = False
    # A document's title — the meeting a task came from. Joined, not stored on
    # the task, so it is written once per meeting.
    source_title: str | None = None


class PaisaOut(BaseModel):
    transactions: list[TransactionOut]
    balance_check: BalanceCheckOut | None


class DietOut(BaseModel):
    meals: list[MealOut]
    habits: list[HabitOut]
    habit_logs: list[HabitLogOut]
    days: list[DayOut]


class WorkOut(BaseModel):
    projects: list[ProjectOut]
    tasks: list[TaskOut]


class OnboardingStepOut(BaseModel):
    """A Getting started step, as builds before spec/done/onboarding-goals.md parse
    it. None is sent any more."""

    id: str
    done: bool


class OnboardingOut(BaseModel):
    """Whether the first run is finished or skipped — what the apps read to
    decide whether to show it."""

    done_at: datetime | None
    #: Always empty: the Getting started card is gone, and older builds still
    #: parse the key.
    steps: list[OnboardingStepOut] = []


class DeckOut(BaseModel):
    """Rows, never totals. The client computes every number it shows."""

    # `from` is a Python keyword, so the field is `from_` and serialises as
    # `from`, matching the query parameter it echoes back.
    from_: date | None = Field(serialization_alias="from")
    to: date
    # The whole users row: every target the rings and the limit need.
    profile: UserOut
    paisa: PaisaOut
    diet: DietOut
    work: WorkOut
    onboarding: OnboardingOut

    model_config = ConfigDict(populate_by_name=True)
