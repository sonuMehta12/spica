"""
Diet + health. Spec: spec/in-progress/diet-data-model.md.

The split that decides everything here:
  reference  (foods, measures, dishes, exercises)  — what things ARE
  ledger     (meal_logs, habit_logs, days)          — what HAPPENED
  house      (pantry, pantry_moves)                 — what is AT HOME

Reference rows are shared; ledger and house rows belong to one user. `foods`
deliberately has no owner at all — nutrition is a fact about the world, and an
owner column would record who eats what.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Envelope

# One decimal place, exactly — labels write "6.6 g" and floats would drift.
GRAMS = Numeric(6, 1)


class Food(Envelope, Base):
    """An ingredient or a packaged product. Values per 100 g, like the label."""

    __tablename__ = "foods"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    # The data is English, the user speaks Hindi: 'dahi' and 'Curd' are one food.
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    brand: Mapped[str | None] = mapped_column(Text)
    # What this food is counted in. Eggs come by the piece, milk in ml, atta in
    # grams — and the ledger stores what you actually count, not a weight the
    # app invented. A dozen is twelve pieces, not a unit.
    unit: Mapped[str] = mapped_column(String(8), nullable=False, server_default="g")
    # For macro maths, which is per 100 g. Nullable: an unknown weight per egg
    # is not a zero one.
    grams_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    category: Mapped[str | None] = mapped_column(Text)

    # Nullable: you can own a thing before you know its macros. 29 of the
    # workbook's 40 foods have no nutrition anywhere, and they are still real.
    kcal_100g: Mapped[int | None] = mapped_column(Integer)
    protein_g_100g: Mapped[Decimal | None] = mapped_column(GRAMS)
    carbs_g_100g: Mapped[Decimal | None] = mapped_column(GRAMS)
    fat_g_100g: Mapped[Decimal | None] = mapped_column(GRAMS)
    fibre_g_100g: Mapped[Decimal | None] = mapped_column(GRAMS)

    # A label-read value and a guessed one must not render the same.
    nutrition_source: Mapped[str | None] = mapped_column(String(16))
    confidence: Mapped[float | None] = mapped_column(Float)

    # No created_by and no visibility, on purpose. See the module docstring.
    forked_from_id: Mapped[str | None] = mapped_column(ForeignKey("foods.id"))

    __table_args__ = (
        CheckConstraint("unit IN ('g','ml','piece')", name="ck_foods_unit"),
        CheckConstraint(
            "nutrition_source IS NULL OR "
            "nutrition_source IN ('label','reference','estimate','llm')",
            name="ck_foods_nutrition_source",
        ),
    )


class Measure(Envelope, Base):
    """A spoken unit resolved to grams: katori, muththi, chammach. Only units —
    '1 katori dal' is a food plus a measure, not a dish."""

    __tablename__ = "measures"

    phrase: Mapped[str] = mapped_column(Text, nullable=False)
    grams: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"))
    forked_from_id: Mapped[str | None] = mapped_column(ForeignKey("measures.id"))

    __table_args__ = (
        # One 'katori' per definer, not one in the world — yours may be 200 g.
        Index("uq_measures_phrase_definer", "phrase",
              func.coalesce(created_by_id, ""), unique=True),
    )


class Dish(Envelope, Base):
    """
    A thing you eat, described once: a serving and its macros. Ingredients and
    steps are optional — Office thali is a dish and nobody cooks it.

    Global, like posts: one pool, each row knowing who made it. Your library is
    what you saved plus what you have eaten (spec/in-progress/dishes.md).
    """

    __tablename__ = "dishes"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    # 'protein shake' and 'whey' are one dish. The resolution ladder reads these
    # before it reaches for trigrams.
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    meal_type: Mapped[str | None] = mapped_column(Text)
    serving_label: Mapped[str] = mapped_column(Text, nullable=False)

    # Per serving. Protein is required — the whole diet mode turns on it — and
    # the rest are nullable, because unknown is not zero.
    kcal: Mapped[int | None] = mapped_column(Integer)
    protein_g: Mapped[Decimal] = mapped_column(GRAMS, nullable=False)
    carbs_g: Mapped[Decimal | None] = mapped_column(GRAMS)
    fat_g: Mapped[Decimal | None] = mapped_column(GRAMS)
    fibre_g: Mapped[Decimal | None] = mapped_column(GRAMS)
    #: Where these numbers came from. `foods` has carried this since the
    #: import and `dishes` never did, so a dish's 420 kcal had no provenance
    #: at all — which is half the reason the library stopped being the macro
    #: source. 'llm' is new: an estimate outranked by anything that says it is
    #: a label or a reference, *because it says so*, not because of its table.
    nutrition_source: Mapped[str | None] = mapped_column(Text)

    # Load-bearing: the real barrier is time, not food. The library has to
    # answer "mere paas 20 minute hain".
    minutes: Mapped[int | None] = mapped_column(Integer)
    needs_prep_ahead: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    steps: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    # Whose photo it is — a Commons picture is shown with its credit or not at
    # all. `image_looked_at` keeps a name with no match from being searched on
    # every open. spec/in-progress/today-plan.md.
    image_credit: Mapped[str | None] = mapped_column(Text)
    image_looked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # What the agent ranks on beyond ingredients: 'veg', 'summer', 'office'.
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    source_url: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

    created_by_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"))
    visibility: Mapped[str] = mapped_column(String(8), nullable=False, default="private")
    forked_from_id: Mapped[str | None] = mapped_column(ForeignKey("dishes.id"))

    __table_args__ = (
        CheckConstraint("visibility IN ('private','public')", name="ck_dishes_visibility"),
        CheckConstraint(
            "nutrition_source IS NULL OR "
            "nutrition_source IN ('label','reference','estimate','llm')",
            name="ck_dishes_nutrition_source"),
        Index("ix_dishes_name_trgm", "name", postgresql_using="gin",
              postgresql_ops={"name": "gin_trgm_ops"}),
    )


class DishItem(Envelope, Base):
    """What a dish is made of: a food with grams, or another dish with servings.
    Ghar ka dinner is roti-sabzi plus dal."""

    __tablename__ = "dish_items"

    dish_id: Mapped[str] = mapped_column(ForeignKey("dishes.id"), nullable=False)
    food_id: Mapped[str | None] = mapped_column(ForeignKey("foods.id"))
    component_dish_id: Mapped[str | None] = mapped_column(ForeignKey("dishes.id"))
    # In the food's unit: 60 g of atta, or 2 eggs.
    quantity: Mapped[int | None] = mapped_column(Integer)
    servings: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False, default=1)
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("(food_id IS NULL) <> (component_dish_id IS NULL)",
                        name="ck_dish_items_one_target"),
        Index("ix_dish_items_dish", "dish_id"),
    )


class MealItem(Envelope, Base):
    """
    One line of a meal. A meal is a bill: "2 ande ki omelette + roti +
    moongphali chutney" is three lines, two dishes and one portion.

    A single dish_id on the meal would drop everything after the first dish;
    an array of ids would have no room for the quantity, or for the roti.
    """

    __tablename__ = "meal_items"

    meal_log_id: Mapped[str] = mapped_column(ForeignKey("meal_logs.id"), nullable=False)
    dish_id: Mapped[str | None] = mapped_column(ForeignKey("dishes.id"))
    food_id: Mapped[str | None] = mapped_column(ForeignKey("foods.id"))
    servings: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    quantity: Mapped[int | None] = mapped_column(Integer)
    # The user's own words for this line, before resolution.
    said: Mapped[str | None] = mapped_column(Text)
    #: How the ladder named this line — exact | alias | similar | id. It is
    #: what decides whether the line may move a shelf: a trigram hit is a
    #: guess about identity, fine to show and to hand the estimator, not fine
    #: to silently take food out of the house.
    #: spec/in-progress/meal-estimates.md § what may spend.
    rung: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("(dish_id IS NULL) <> (food_id IS NULL)", name="ck_meal_items_one_target"),
        Index("ix_meal_items_meal", "meal_log_id"),
        # 'How many times have I had this' is a count over these.
        Index("ix_meal_items_dish", "dish_id"),
    )


class DishSave(Envelope, Base):
    """A bookmark. Tried is derived from the ledger; saved is a declaration,
    so it needs a row."""

    __tablename__ = "dish_saves"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    dish_id: Mapped[str] = mapped_column(ForeignKey("dishes.id"), nullable=False)


Index("uq_dish_saves_user_dish", DishSave.user_id, DishSave.dish_id, unique=True,
      postgresql_where=DishSave.deleted_at.is_(None))


class Exercise(Envelope, Base):
    """
    A library for suggesting, **not** recording — the same reason dishes exist.
    *"Aaj leg lagana hai"* is answered by reading this; what it does not hold,
    the agent finds elsewhere and offers to keep.

    There is no matching ledger and that is deliberate: a workout is logged as a
    habit, yes or no, the way a cigarette is. Which exercises were done in the
    gym is not something this user records — a table for it was built once and
    removed (`f6c94d2e8a13`, and `spec/notes.md`).
    """

    __tablename__ = "exercises"

    # Whose library. Owned outright, not pooled: dishes keeps a shared pool
    # because the app ships one, and this does not need to.
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    # What the user actually says — "OHP", "shoulder press" — so a spoken
    # request matches the library without a model call.
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")

    # Separate from muscle_group on purpose: cardio is not a muscle. Incline
    # walk is kind='cardio' with no group, so "leg lagana hai" does not return
    # a treadmill.
    kind: Mapped[str | None] = mapped_column(Text)
    muscle_group: Mapped[str | None] = mapped_column(Text)
    # Must include 'none', or the library only works on gym days.
    equipment: Mapped[str | None] = mapped_column(Text)
    # Load-bearing: the real barrier was time. "Mere paas 20 minute hain".
    typical_minutes: Mapped[int | None] = mapped_column(Integer)

    # How to do it, and where to watch it being done.
    steps: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    # As on dishes: the photo's credit, and when a picture was last looked for.
    image_credit: Mapped[str | None] = mapped_column(Text)
    image_looked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # How it got here: shipped with the app, said in conversation, shared as a
    # link, or typed.
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    note: Mapped[str | None] = mapped_column(Text)

    # Stored, not derived — and the one count in Spica that is. There is no
    # ledger of exercises done, so "I have done this three times" is a
    # declaration rather than a measurement. It also replaces the old
    # `exercise_saves` star: the library is the bookmark, and 0 vs >0 is the
    # only distinction that star was making.
    tried: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_tried: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint("kind IS NULL OR kind IN ('strength','cardio','mobility','stretch')",
                        name="ck_exercises_kind"),
        CheckConstraint("source IN ('seed','chat','link','manual')", name="ck_exercises_source"),
        CheckConstraint("tried >= 0", name="ck_exercises_tried"),
        Index("ix_exercises_user_group", "user_id", "muscle_group"),
    )


class MealLog(Envelope, Base):
    """What you ate. The ledger row; its lines are meal_items, each pointing at
    a dish or a plain food."""

    __tablename__ = "meal_logs"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    local_day: Mapped[date] = mapped_column(Date, nullable=False)

    # Free text: twelve values appear in 24 days and 'Grazing' was invented
    # mid-experiment. An enum would have rejected the most interesting row.
    meal_type: Mapped[str] = mapped_column(Text, nullable=False)
    dish: Mapped[str] = mapped_column(Text, nullable=False)
    ingredients: Mapped[str | None] = mapped_column(Text)

    # On the row, not looked up: what was believed at log time. A later fix
    # supersedes the row rather than silently changing history.
    kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_g: Mapped[Decimal] = mapped_column(GRAMS, nullable=False)
    # Nullable: the composer knows kcal and protein for a chip but not its fat
    # or carbs, and the portion sheet those chips come from never recorded
    # them either. Unknown stays NULL — a 0 here is a fabricated number.
    carbs_g: Mapped[Decimal | None] = mapped_column(GRAMS)
    fat_g: Mapped[Decimal | None] = mapped_column(GRAMS)
    #: The one nutrition column meals lacked — `foods` and `dishes` have
    #: carried theirs since the import. A profile target with nothing to
    #: measure against is worse than no target.
    fibre_g: Mapped[Decimal | None] = mapped_column(GRAMS)

    # What the model said before the user touched it. Written once at log
    # time, never updated: the columns above are what was settled on, and the
    # gap between the two IS the error.
    #
    # It cannot be added later. Correct 420 to 186 without having kept the 420
    # and the guess is gone for good — recomputing it would need the model and
    # the person's history as they were that day, and both move.
    # spec/in-progress/meal-estimates.md § the pair.
    estimated_kcal: Mapped[int | None] = mapped_column(Integer)
    estimated_protein_g: Mapped[Decimal | None] = mapped_column(GRAMS)
    estimated_carbs_g: Mapped[Decimal | None] = mapped_column(GRAMS)
    estimated_fat_g: Mapped[Decimal | None] = mapped_column(GRAMS)
    estimated_fibre_g: Mapped[Decimal | None] = mapped_column(GRAMS)
    #: Null until the user changes a macro. The corrected rows are exactly the
    #: calibration set the next estimate reads back.
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cooked_home: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    note: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("meal_logs.id"))
    dedupe_key: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("source IN ('manual','photo')", name="ck_meal_logs_source"),
        # Two users can receive the same notification text; dedupe is per person.
        Index("uq_meal_logs_dedupe", "user_id", "dedupe_key", unique=True,
              postgresql_where=dedupe_key.isnot(None)),
        Index("ix_meal_logs_user_day", "user_id", "local_day"),
        Index("ix_meal_logs_sync", "user_id", "updated_at", "id"),
    )


class Habit(Envelope, Base):
    """A choice, named: workout, running, smoking, beer, meditation, fasting.
    Sleep is not here — you always sleep, so a blank would be unreported, not
    skipped. It lives on Day."""

    __tablename__ = "habits"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    unit: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("direction IN ('build','break')", name="ck_habits_direction"),
        # Partial and case-insensitive. A plain constraint let a retired habit
        # keep its name for ever, and made `workout` and `Workout` two rows
        # that `log_day` could not tell apart.
        Index("uq_habits_user_name", "user_id", text("lower(name)"), unique=True,
              postgresql_where=text("deleted_at IS NULL")),
    )


class HabitLog(Envelope, Base):
    """One occurrence. A skipped day is not a row: absence IS the rest day."""

    __tablename__ = "habit_logs"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    habit_id: Mapped[str] = mapped_column(ForeignKey("habits.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    local_day: Mapped[date] = mapped_column(Date, nullable=False)
    # NULL = it happened, that is all.
    amount: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("source IN ('manual','photo')", name="ck_habit_logs_source"),
        Index("uq_habit_logs_dedupe", "user_id", "dedupe_key", unique=True,
              postgresql_where=dedupe_key.isnot(None)),
        Index("ix_habit_logs_user_day", "user_id", "local_day"),
    )


class Day(Envelope, Base):
    """Only what meals and habits cannot derive. log_complete tells a fast from
    a failed log — without it, 16 Aug reads as 0 kcal and that is a lie."""

    __tablename__ = "days"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    local_day: Mapped[date] = mapped_column(Date, nullable=False)
    # NULL = unknown. FALSE = the user said there is more. TRUE = that was all.
    log_complete: Mapped[bool | None] = mapped_column(Boolean)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    # A measurement, not a habit: you always sleep, so blank means unreported.
    sleep_hours: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # One row per person per day. A DATE primary key would allow exactly
        # one person to exist.
        UniqueConstraint("user_id", "local_day", name="uq_days_user_day"),
    )


class PantryItem(Envelope, Base):
    """A food this house tracks. The quantity is not here — it is the sum of
    pantry_moves, so deleting a meal gives its ingredients back."""

    __tablename__ = "pantry"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    food_id: Mapped[str] = mapped_column(ForeignKey("foods.id"), nullable=False)
    # Below this, it goes on the shopping list. NULL for the untracked kind —
    # the family's atta is present, amount unknowable.
    reorder_at_g: Mapped[int | None] = mapped_column(Integer)
    # Curd: 'buy every 2-3 days'. Quantity alone is not enough — 780 g of curd
    # bought two weeks ago is not 780 g of curd.
    shelf_life_days: Mapped[int | None] = mapped_column(Integer)
    # The user's declaration, not something the moves can tell us: atta is
    # always in the house and counting it is meaningless, while eggs cycle even
    # if no purchase has been logged yet. Writing an inbound move flips it off —
    # once you are counting a thing, it is not a staple any more.
    staple: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    note: Mapped[str | None] = mapped_column(Text)



# One tofu row per house, not per world — among LIVE rows. Stop tracking
# soft-deletes; tracking the food again must be allowed, so the rule is partial.
Index("uq_pantry_user_food", PantryItem.user_id, PantryItem.food_id, unique=True,
      postgresql_where=PantryItem.deleted_at.is_(None))


class PantryMove(Envelope, Base):
    """Signed, in the food's unit. +400 when 400 g of tofu arrives, +12 when a
    dozen eggs do, -50 when a dish spends it. 'opening' is a stock-take — the
    pantry's balance_checks."""

    __tablename__ = "pantry_moves"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    food_id: Mapped[str] = mapped_column(ForeignKey("foods.id"), nullable=False)
    local_day: Mapped[date] = mapped_column(Date, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # In the food's own unit — grams, millilitres or pieces.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # What caused it, so deleting the meal takes its consumption with it.
    meal_log_id: Mapped[str | None] = mapped_column(ForeignKey("meal_logs.id"))
    note: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('purchase','opening','consumption','correction','waste')",
            name="ck_pantry_moves_kind",
        ),
        Index("uq_pantry_moves_dedupe", "user_id", "dedupe_key", unique=True,
              postgresql_where=dedupe_key.isnot(None)),
        Index("ix_pantry_moves_user_food_day", "user_id", "food_id", "local_day"),
    )