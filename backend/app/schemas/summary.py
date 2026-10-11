"""Wire shape for GET /paisa/summary — only the keys asked for are present."""

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.deck import TransactionOut


class LimitOut(BaseModel):
    #: Unknown — null — before the month's first income, when a negative figure
    #: would read as overspending. May otherwise be negative: past the line.
    limit_paise: int | None
    spent_today_paise: int
    left_paise: int | None
    pool_paise: int
    locked_paise: int
    fixed_paid_paise: int
    days_left: int
    savings_target_paise: int


class CommitmentOut(BaseModel):
    #: A commitment's id, or the borrowing's — a borrowing is read-only here.
    id: str
    name: str
    #: `commitment`, or `borrowing` — worked out live from the udhaar ledger.
    source: str
    #: `manual`, `rolled`, `carried` or `borrowing`.
    origin: str
    category: str
    expected_paise: int
    paid_paise: int
    owed_paise: int
    #: Paid beyond what was expected; the payment is not split.
    over_paise: int = 0
    settled: bool
    skipped: bool = False
    due_day: int | None = None
    repeats: bool = False
    #: `rolled` is an inferred figure and wears the amber dot.
    amount_source: str = "stated"
    #: Payments linked to it that were only guessed from the category.
    inferred_links: int = 0
    carried_from_month: date | None = None


class CommitmentsOut(BaseModel):
    """What is still owed this month, line by line. Adds up to
    `limit_today.locked_paise`."""

    month: date
    owed_paise: int
    settled_paise: int
    items: list[CommitmentOut]


class BalanceOut(BaseModel):
    """"How much is left" as one answer, already worked out — see
    `paisa_summary` § balance for why it is not left to the caller."""

    left_paise: int
    committed_paise: int
    savings_target_paise: int
    free_paise: int
    came_in_paise: int
    went_out_paise: int
    of_which_fixed_paise: int
    of_which_lent_paise: int
    days_left: int


class WithinLimitOut(BaseModel):
    n: int
    of: int


class OpenUdhaarOut(BaseModel):
    """One open lending or borrowing, with the id a repayment must settle."""

    id: str
    kind: str
    name: str
    amount_paise: int
    remaining_paise: int
    local_day: date


class UdhaarOut(BaseModel):
    out_paise: int
    owe_paise: int
    open_lendings: int
    open_borrowings: int
    open: list[OpenUdhaarOut] = []


class FixedOut(BaseModel):
    fixed_paise: int
    repeats_paise: int


class ByDayOut(BaseModel):
    local_day: date
    spent_paise: int


class ByCategoryOut(BaseModel):
    category: str
    paise: int
    share: float


class ByCounterpartyOut(BaseModel):
    counterparty_id: str
    name: str | None
    paise: int
    n: int


class GuessOut(BaseModel):
    category: str
    description: str | None = None
    confidence: float
    why: str | None = None
    by: str


class ToReviewOut(BaseModel):
    """One payment the batch was unsure about, with its guess and the reason,
    so the card can show why before asking."""

    transaction_id: str
    amount_paise: int
    payee: str
    local_day: date
    was: str
    guess: GuessOut


class PaisaSummaryOut(BaseModel):
    """Every key optional: absent means *not asked for*, never zero."""

    model_config = {"from_attributes": True}

    # `from` is a Python keyword; the field is `from_` and serialises as `from`.
    from_: date = Field(serialization_alias="from")
    to: date
    spent_paise: int | None = None
    income_paise: int | None = None
    daily_avg_paise: int | None = None
    days_in_range: int | None = None
    within_limit: WithinLimitOut | None = None
    limit_today: LimitOut | None = None
    balance: BalanceOut | None = None
    commitments: CommitmentsOut | None = None
    udhaar: UdhaarOut | None = None
    fixed: FixedOut | None = None
    by_day: list[ByDayOut] | None = None
    by_category: list[ByCategoryOut] | None = None
    by_counterparty: list[ByCounterpartyOut] | None = None
    rows: list[TransactionOut] | None = None
    to_review: list[ToReviewOut] | None = None
    total_matching: int | None = None
    next_after: str | None = None
