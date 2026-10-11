from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Envelope, new_id

SOURCES = ("manual", "notification")
# Worse than this and a fix says nothing useful: a 500m radius covers a whole
# market, so inferring a place from it would be inventing data. The coordinates
# are still kept in predictions.signals and can attach to a place later.
ACCURACY_LIMIT_M = 50.0
DIRECTIONS = ("debit", "credit")
KINDS = ("expense", "income", "lent", "borrowed", "repayment", "transfer")


class Counterparty(Envelope, Base):
    """Whoever money moved to or from — a shop, a friend, an employer."""

    __tablename__ = "counterparties"

    # Yours: who YOU pay is personal, and is_peer describes YOUR relationship.
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    # What the payment system said. Never edited: this is how the next
    # notification is matched back to the same counterparty.
    raw_name: Mapped[str] = mapped_column(Text, nullable=False)
    # What you call it — "chai aur samosa". Not a category, and never will be.
    display_name: Mapped[str | None] = mapped_column(Text)
    # The spending bucket payments here usually fall into.
    default_category: Mapped[str | None] = mapped_column(Text)

    # Flips true the first time money comes *back*, and never flips back.
    # Shops take money; people also return it.
    is_peer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    in_contacts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # What this row *is*. Never guessed from the payee name: a notification
    # renders your sister and the paan-wala identically, so the name carries
    # nothing. NULL = nobody has said, and nothing breaks while it is NULL.
    kind: Mapped[str | None] = mapped_column(Text)
    # In the user's words — dost, badi sister, landlord. Not a taxonomy, and
    # never derived: only contacts or the user can know it.
    relation: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    # Who last wrote the three above. 'contacts' outranks 'agent'; 'user'
    # outranks both and is never overwritten. NULL = nobody has.
    source: Mapped[str | None] = mapped_column(Text)
    # Last time the user said "haan, sahi hai". Inferred is marked · andaaza,
    # confirmed is not — the pair `memories` carries, for the same reason.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Unique per user, not in the world: two people both pay MOHAN LAL.
        # Retires when capture gives us the VPA — two different Manoramas are
        # one row under this. spec/in-progress/people.md § Contacts.
        UniqueConstraint("user_id", "raw_name", name="uq_counterparties_user_raw"),
        CheckConstraint("kind IS NULL OR kind IN ('person','shop','service')",
                        name="ck_counterparties_kind"),
        CheckConstraint("source IS NULL OR source IN ('user','agent','contacts')",
                        name="ck_counterparties_source"),
        Index("ix_counterparties_raw_name_trgm", "raw_name", postgresql_using="gin",
              postgresql_ops={"raw_name": "gin_trgm_ops"}),
    )


class Place(Envelope, Base):
    """
    Where you were when a payment happened.

    Not the same as a counterparty, and the difference matters: a counterparty
    is *who you paid*, a place is *where you were*. Mohan Lal's shop is both.
    Rapido is a counterparty with no place. A Zepto delivery is a counterparty
    whose place is your home. A food court is one place with many counterparties.

    Created silently from payment locations rather than curated — but only when
    the GPS fix is good enough to mean something. See ACCURACY_LIMIT_M.
    """

    __tablename__ = "places"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    # How far out still counts as "here". A paan shop is ~20m, a mall ~200m —
    # one fixed threshold would be wrong for both.
    radius_m: Mapped[float] = mapped_column(Float, nullable=False, default=50)

    # Same split as counterparties: what the provider said, and what we make of
    # it. Change providers and the mapping changes; the raw value does not.
    raw_type: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)

    address: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(16))
    # The provider's own id, so a re-lookup is stable. Searching again by name
    # and coordinates can return a different answer.
    provider_id: Mapped[str | None] = mapped_column(Text)
    # Reverse geocoding is often wrong. A place we inferred and one you named
    # are not equally trustworthy. This is the *detector's* own measure, which
    # the agent can threshold on; `confirmed_at` is what the screen reads.
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # "Chai tapri" and "the paan shop" are different facts about one street
    # corner. Home and office are pins like any other.
    kind: Mapped[str | None] = mapped_column(Text)
    # "This is Mohan Lal's shop" — what lets the pin show its spend with no
    # payment tagged by hand. Optional both ways: Rapido is a counterparty with
    # no place, a food court is one place with many counterparties.
    counterparty_id: Mapped[str | None] = mapped_column(ForeignKey("counterparties.id"))
    note: Mapped[str | None] = mapped_column(Text)
    # How the pin got here. A 'manual' pin leaves provider, provider_id,
    # raw_type and address empty: you put it there, there is nothing to doubt.
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="manual")
    # A detected pin is a guess until you say otherwise, and shows · andaaza
    # until then — the same pair `memories` and `counterparties` carry.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("provider IS NULL OR provider IN ('google','user','derived')",
                        name="ck_places_provider"),
        CheckConstraint("radius_m > 0", name="ck_places_radius_positive"),
        CheckConstraint(
            "kind IS NULL OR kind IN "
            "('home','office','shop','eat','hangout','pickup','gym','other')",
            name="ck_places_kind"),
        CheckConstraint("source IN ('manual','search','detected')", name="ck_places_source"),
        Index("ix_places_latlng", "lat", "lng"),
    )


class Transaction(Envelope, Base):
    """The ledger. What happened — never what was guessed."""

    __tablename__ = "transactions"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # For what cuts across categories — a festival, a habit — since a row has
    # exactly one category. See the spec for why this earned its place.
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    # The user's decision on the row, not a category's property: this money was
    # never spendable (fixed), and it goes again next month (repeats). Repeats
    # implies fixed. spec/in-progress/fixed-costs.md.
    fixed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    repeats: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # The obligation this payment pays, if any. A linked payment is not
    # discretionary spend: it leaves *spent* and the commitment's *owed* falls by
    # it. `fixed` and `repeats` above are no longer read anywhere — they stay
    # one release so nothing is lost, then drop. spec/done/commitments.md.
    commitment_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("commitments.id"), index=True)
    # The link was guessed from the category, not stated: it wears the amber dot
    # until the user moves it or confirms it.
    commitment_inferred: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false")

    # The application computes this; the database only enforces it. NULL for
    # manual rows, and Postgres does not treat two NULLs as equal — so two ₹40
    # chais on one day both insert, which is correct. Unique per user, not
    # globally: two users can receive identical notification text.
    dedupe_key: Mapped[str | None] = mapped_column(Text)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Stored, not derived at read time: India is UTC+5:30, so an 11:30pm entry
    # lands on the wrong day otherwise.
    local_day: Mapped[date] = mapped_column(Date, nullable=False)

    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    # Which way money moved is `direction`; what the movement *meant* is `kind`,
    # and that is what the budget reads. Only `expense` counts against the limit.
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Whatever you want to say about this one payment. Confidence, provenance and
    # correction feedback each have their own home, so this is not for those — it
    # is for the context none of them hold, like "4 logon ne khilaya tha".
    note: Mapped[str | None] = mapped_column(Text)

    counterparty_name: Mapped[str | None] = mapped_column(Text)
    counterparty_id: Mapped[str | None] = mapped_column(ForeignKey("counterparties.id"))

    method: Mapped[str | None] = mapped_column(String(8))
    # Where you were, resolved. Cleared and recomputed from the fix below if the
    # match turns out wrong.
    place_id: Mapped[str | None] = mapped_column(ForeignKey("places.id"))

    # The fix itself. It sat in `predictions.signals` until 2026-09-07, which
    # lost it whenever the agent had not guessed about the payment — and a
    # payment at an unknown spot is exactly what discovers a place by
    # repeating. A GPS reading is an observation, not a guess, so it belongs
    # here with everything else that happened.
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    # Worse than ACCURACY_LIMIT_M and it still stores but cannot resolve:
    # inferring a shop from a 500m circle is inventing data.
    fix_accuracy_m: Mapped[float | None] = mapped_column(Float)

    # A repayment points at the lending it settles. Partial repayment falls out
    # for free: outstanding is principal minus the sum of rows settling it.
    settles_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"))
    # A correction is a new row superseding the old one, never an edit.
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"))

    __table_args__ = (
        CheckConstraint(f"source IN {SOURCES}", name="ck_transactions_source"),
        CheckConstraint(f"direction IN {DIRECTIONS}", name="ck_transactions_direction"),
        CheckConstraint(f"kind IN {KINDS}", name="ck_transactions_kind"),
        CheckConstraint("method IS NULL OR method IN ('cash','digital')",
                        name="ck_transactions_method"),
        CheckConstraint("amount_paise > 0", name="ck_transactions_amount_positive"),
        Index("uq_transactions_dedupe", "user_id", "dedupe_key", unique=True,
              postgresql_where=dedupe_key.isnot(None)),
        # Personal indexes lead with user_id, or one person's week scans
        # everyone's rows.
        Index("ix_transactions_local_day", "user_id", local_day.desc()),
        Index("ix_transactions_category_day", "user_id", "category", "local_day"),
        Index("ix_transactions_counterparty", "counterparty_id"),
        Index("ix_transactions_place", "place_id"),
        CheckConstraint(
            "(lat IS NULL) = (lng IS NULL) AND (fix_accuracy_m IS NULL OR fix_accuracy_m > 0)",
            name="ck_transactions_fix"),
        Index("ix_transactions_settles", "settles_id",
              postgresql_where=settles_id.isnot(None)),
        # The sync cursor is (updated_at, id): updated_at alone would let paging
        # skip one of two rows written in the same millisecond.
        Index("ix_transactions_sync", "user_id", "updated_at", "id"),
        Index("ix_transactions_tags", "tags", postgresql_using="gin"),
    )


class Prediction(Base):
    """
    What the model saw and what it guessed. Separate from the ledger because a
    prediction is not a fact about the world.
    """

    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), nullable=False)

    predicted_by: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    # Snapshotted, never recomputed: payee_seen_count was 3 when the model
    # predicted and is 47 today, so recomputing produces a training example that
    # never existed. JSONB because the feature set will change and nothing ever
    # aggregates over an individual signal.
    signals: Mapped[dict] = mapped_column(JSONB, nullable=False)

    pred_category: Mapped[str | None] = mapped_column(Text)
    pred_description: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)

    actual_category: Mapped[str | None] = mapped_column(Text)
    actual_description: Mapped[str | None] = mapped_column(Text)
    user_feedback: Mapped[str | None] = mapped_column(Text)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("predicted_by IN ('dictionary','rules','llm')",
                        name="ck_predictions_predicted_by"),
        Index("ix_predictions_transaction", "transaction_id"),
        # The training set is exactly the corrected rows.
        Index("ix_predictions_corrected", "corrected_at",
              postgresql_where=corrected_at.isnot(None)),
    )


class BalanceCheck(Base):
    """
    The user stating what is actually in the bank. An observation — nothing in
    the ledger can produce it, and the reconciliation gap is measured against it.
    """

    __tablename__ = "balance_checks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
