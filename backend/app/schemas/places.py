"""Wire shapes for places. spec/in-progress/places.md."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Row
from app.schemas.writes import Id, Patch

KIND = r"^(home|office|shop|eat|hangout|pickup|gym|other)$"
SOURCE = r"^(manual|search|detected)$"


class PlaceOut(Row):
    """A pin, and what the ledger knows about it.

    `payments`, `spent_paise` and `last_seen` are counted per request over the
    transactions pointing here — unlike the exercise library, a place *has* a
    ledger under it, so deleting a payment corrects the pin with no write.
    """

    id: str
    name: str
    kind: str | None
    lat: float
    lng: float
    """A paan shop is ~20m and a mall ~200m; one threshold would be wrong for both."""
    radius_m: float
    address: str | None
    category: str | None
    counterparty_id: str | None
    counterparty_name: str | None
    note: str | None
    source: str
    """Null on a detected pin until you say so — that is what shows `· andaaza`."""
    confirmed_at: datetime | None

    payments: int
    spent_paise: int
    last_seen: date | None


class PlaceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    name: str = Field(min_length=1, max_length=120)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    kind: str | None = Field(default=None, pattern=KIND)
    radius_m: float = Field(default=50, gt=0, le=5000)
    address: str | None = None
    category: str | None = None
    counterparty_id: str | None = None
    note: str | None = None
    # 'detected' is the agent's; a person dropping a pin says how they found it.
    source: str = Field(default="manual", pattern=SOURCE)


class PlacePatch(Patch):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: str | None = Field(default=None, pattern=KIND)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    radius_m: float | None = Field(default=None, gt=0, le=5000)
    address: str | None = None
    category: str | None = None
    counterparty_id: str | None = None
    note: str | None = None
