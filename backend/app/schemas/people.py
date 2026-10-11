"""Wire shapes for People. spec/in-progress/people.md § Data and API."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Row
from app.schemas.writes import Id, Patch


class PersonOut(Row):
    """A counterparty and everything the ledger knows about them.

    The four numbers are computed per request and never stored: delete the
    repayment and `still_out_paise` goes back up on its own. `typical_days` is
    None when nothing has ever come back — unknown is not zero, and an average
    of no repayments would be the most flattering lie available.
    """

    id: str
    raw_name: str
    display_name: str | None
    """What this row is. NULL = nobody has said, which breaks nothing."""
    kind: str | None
    relation: str | None
    note: str | None
    """Who wrote kind/relation/note. NULL or 'agent' with no confirmed_at is
    what puts `· andaaza` on screen."""
    source: str | None
    confirmed_at: datetime | None
    """Flipped by an event, not by a claim: money came back from them."""
    is_peer: bool
    in_contacts: bool
    default_category: str | None

    sent_paise: int
    received_paise: int
    """What they owe you: lendings minus the repayments settling them."""
    still_out_paise: int
    """What you owe them: borrowings minus what you have paid back."""
    you_owe_paise: int
    """Mean days from a lending to its first repayment, over settled ones."""
    typical_days: int | None
    tx_count: int
    last_day: date | None


class CounterpartyPatch(Patch):
    """The user speaking. Every field here stamps source='user' and
    confirmed_at — this route is never the agent's."""

    kind: str | None = Field(default=None, pattern=r"^(person|shop|service)$")
    relation: str | None = Field(default=None, max_length=60)
    note: str | None = None
    display_name: str | None = Field(default=None, max_length=120)
    default_category: str | None = None


class CounterpartyIn(BaseModel):
    """Someone you have not paid yet — the cash you owe Wasim, the friend you
    are about to lend to. Everything here is the user's own word, so the row is
    born confirmed.

    `raw_name` is the one required field and the one that cannot be changed
    afterwards: a payment from this name has to find this row.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Id
    raw_name: str = Field(min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=120)
    kind: str | None = Field(default=None, pattern=r"^(person|shop|service)$")
    relation: str | None = Field(default=None, max_length=60)
    note: str | None = None
    default_category: str | None = None

