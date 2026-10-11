"""Wire shapes for commitments. spec/done/commitments.md."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.summary import CommitmentOut
from app.schemas.writes import Id, Patch


class CommitmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    name: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=60)
    amount_paise: int = Field(gt=0)
    due_day: int | None = Field(None, ge=1, le=31)
    #: On by default: a commitment the user set is expected again until they
    #: say it is not one any more.
    repeats: bool = True
    #: Payments to link at once — *Make this a commitment* from a payment's tray.
    link_transaction_ids: list[str] = []


class CommitmentPatch(Patch):
    name: str | None = Field(None, min_length=1, max_length=80)
    category: str | None = Field(None, min_length=1, max_length=60)
    amount_paise: int | None = Field(None, gt=0)
    due_day: int | None = Field(None, ge=1, le=31)
    repeats: bool | None = None
    #: A switch, like `PATCH /nudges`: true is *not this month*, false clears it.
    skipped: bool | None = None


class CommitmentsPageOut(BaseModel):
    """The page: the month's lines, and the chain from the pool to the limit so
    a zero is never a mystery."""

    month: date
    #: A past month is read-only.
    editable: bool
    owed_paise: int
    pool_paise: int
    savings_target_paise: int
    #: Null before the month's first income — unknown, not zero.
    limit_paise: int | None
    days_left: int
    #: Lines paid in full, of the lines that are not skipped.
    paid_count: int
    open_count: int
    items: list[CommitmentOut]
