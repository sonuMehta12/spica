"""Wire shapes for the pantry. spec/in-progress/pantry-view.md § Data and API."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import Row
from app.schemas.writes import Id, Patch


class PantryItemOut(Row):
    """A tracked food and the numbers the status ladder needs: what the moves
    sum to, whether anything ever came IN at all, and when the last one did.

    The word — unknown, out, stale, soon, ok — is the client's to pick.
    """

    id: str
    food_id: str
    name: str
    stock_g: int
    reorder_at_g: int | None
    shelf_life_days: int | None
    unit: str
    note: str | None
    """Always in the house, so counting it is meaningless. The user's call —
    the moves cannot tell atta from eggs nobody has logged yet."""
    staple: bool
    inbound: int
    last_in: date | None
    last_in_g: int | None


class PantryItemIn(BaseModel):
    """Start tracking a food. `food_name` is resolved to an existing food by
    name or alias, or creates one with no nutrition."""
    # A typo in a client is a 422, never a silently ignored field.
    model_config = ConfigDict(extra="forbid")


    id: str = Id
    food_id: str | None = None
    food_name: str | None = Field(default=None, min_length=1, max_length=120)
    # Only used when the food is new. An existing food keeps the unit it has.
    unit: str = Field(default="g", pattern=r"^(g|ml|piece)$")
    staple: bool = False
    reorder_at_g: int | None = Field(default=None, ge=0)
    shelf_life_days: int | None = Field(default=None, ge=1, le=3650)
    note: str | None = None

    @model_validator(mode="after")
    def one_of(self):
        if not (self.food_id or self.food_name):
            raise ValueError("food_id or food_name is required")
        return self


class PantryItemPatch(Patch):
    """The row's inputs. A quantity is never here — that is a move."""

    staple: bool | None = None
    reorder_at_g: int | None = Field(default=None, ge=0)
    shelf_life_days: int | None = Field(default=None, ge=1, le=3650)
    note: str | None = None


class PantryMoveRow(Row):
    """One line of the ledger. `dish` is the meal that caused a consumption —
    the reason those lines carry no Undo."""

    id: str
    food_id: str
    name: str
    local_day: date
    quantity: int
    unit: str
    kind: str
    note: str | None
    dish: str | None
