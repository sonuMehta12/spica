"""Wire shapes for dishes. spec/in-progress/dishes.md."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Row
from app.schemas.writes import Id, Patch


class DishItemOut(Row):
    """A line of the dish: a food with grams, or another dish with servings."""

    id: str
    food_id: str | None
    food_name: str | None
    component_dish_id: str | None
    quantity: int | None
    unit: str = "g"
    servings: Decimal
    note: str | None
    """Set when this line came from a component dish, so the UI can say where
    an ingredient is really from. Grams are already scaled by the servings."""
    from_dish: str | None = None


class DishOut(Row):
    """
    A dish, plus this user's relationship with it. `tried` and `last_tried` are
    counted from the ledger at read time — no stored counter to drift.
    """

    id: str
    name: str
    aliases: list[str]
    meal_type: str | None
    serving_label: str
    kcal: int | None
    protein_g: Decimal
    carbs_g: Decimal | None
    fat_g: Decimal | None
    fibre_g: Decimal | None
    minutes: int | None
    needs_prep_ahead: bool
    steps: str | None
    image_url: str | None
    tags: list[str]
    note: str | None
    mine: bool
    saved: bool
    tried: int
    last_tried: date | None
    items: list[DishItemOut] = []


class DishIn(BaseModel):
    # A typo in a client is a 422, never a silently ignored field.
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    name: str = Field(min_length=1, max_length=120)
    serving_label: str = Field(min_length=1, max_length=60)
    protein_g: Decimal = Field(ge=0)
    aliases: list[str] = []
    meal_type: str | None = None
    kcal: int | None = Field(default=None, ge=0)
    carbs_g: Decimal | None = None
    fat_g: Decimal | None = None
    fibre_g: Decimal | None = None
    minutes: int | None = Field(default=None, ge=0)
    needs_prep_ahead: bool = False
    steps: str | None = None
    tags: list[str] = []
    source_url: str | None = None
    note: str | None = None


class DishPatch(Patch):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    aliases: list[str] | None = None
    meal_type: str | None = None
    serving_label: str | None = Field(default=None, min_length=1, max_length=60)
    kcal: int | None = Field(default=None, ge=0)
    protein_g: Decimal | None = Field(default=None, ge=0)
    carbs_g: Decimal | None = None
    fat_g: Decimal | None = None
    fibre_g: Decimal | None = None
    minutes: int | None = Field(default=None, ge=0)
    needs_prep_ahead: bool | None = None
    steps: str | None = None
    tags: list[str] | None = None
    note: str | None = None
    visibility: str | None = Field(default=None, pattern=r"^(private|public)$")
