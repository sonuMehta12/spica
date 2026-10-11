# Paisa — data model

> Working doc. Open questions at the end; moves to `spec/` when they close.
> Source of truth for the data: `Paisa_Tracker.xlsx`, 1–28 Aug 2026.
> Reads from: `spec/substrate.md`, `spec/paisa-categorise.md`, `spec/udhaar.md`

The React prototype's `seed.ts` is **not** an input. It was a sketch to steer the
UI; its shapes carry no authority here.

## What the workbook contains

| Sheet | Rows | Columns |
|---|---|---|
| Daily Log | 73 | Din · Kya kharcha · Category · Amount · Cash/Digital · Note |
| Udhaar | 4 | Din · Kisko diya · Diya · Wapas aaya · Baaki · Note |
| Setup | 18 | salary, fixed costs, stated balance, savings target |
| Dashboard | — | entirely derived; nothing to store |

Facts the schema has to accommodate:

- **73 transactions, ₹22,139.** All amounts whole rupees; no decimals anywhere.
- **17 rows carry a real UPI counterparty name** inside the description —
  `MOHAN LAL` ×4, `MOHD WASIM` ×2, `SADANAND GUPTA` ×2,
  `DSCSC CHILLA DALLUPURA` ×2, and seven others.
- **Cash/Digital filled 24 of 73.** Mostly unknown, so nullable and never
  defaulted.
- **26 notes**, which decompose into confidence (*"Amount confirm karo"*,
  *"andaaza"*), provenance (*"Notification se"*), and corrections (*"Aapne ~400
  kaha tha, 350 log kiya"*) — each of which becomes a field rather than prose.
- **Udhaar already tracks partial repayment** — ₹14,000 out, ₹10,000 back.
- **The reconciliation gap is real: ₹6,921**, 16.5% of available money.
  `42,052 − 22,139 − 4,000 − 8,992`.

---

## Money is stored as integer paise

`amount_paise BIGINT`. `₹98.00` is `9800`. Formatted at the edge, never in the
database.

Binary floating point cannot represent decimal fractions exactly, and this app
sums constantly — every report, every category total, every daily limit — so the
error compounds until a total is wrong for no traceable reason.

Integer minor units are also what every payment system this will ever touch
speaks: Razorpay's API takes paise, Stripe takes *"the smallest currency unit"*,
and NPCI settles UPI in paise. Storing paise means never converting at a
boundary.

`BIGINT` over `INTEGER` because `INTEGER` caps at ₹2.15 crore, and four extra
bytes per row removes the ceiling entirely.

---

## `transactions`

The ledger — what happened. Nothing about what was *guessed* lives here.

```sql
CREATE TABLE transactions (
  id            TEXT PRIMARY KEY,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at    TIMESTAMPTZ,

  source        TEXT NOT NULL CHECK (source IN ('manual','notification')),
  confidence    REAL NOT NULL DEFAULT 1.0,
  tags          TEXT[] NOT NULL DEFAULT '{}',   -- see below

  occurred_at   TIMESTAMPTZ NOT NULL,
  local_day     DATE NOT NULL,

  amount_paise  BIGINT NOT NULL CHECK (amount_paise > 0),
  direction     TEXT NOT NULL CHECK (direction IN ('debit','credit')),
  kind          TEXT NOT NULL CHECK (kind IN
                  ('expense','income','lent','borrowed','repayment','transfer')),
  category      TEXT NOT NULL,
  description   TEXT NOT NULL,

  counterparty_name TEXT,
  counterparty_id   TEXT REFERENCES counterparties(id),

  method        TEXT CHECK (method IN ('cash','digital')),
  place_id      TEXT REFERENCES places(id),

  settles_id    TEXT REFERENCES transactions(id),
  supersedes_id TEXT REFERENCES transactions(id)
);

CREATE INDEX ON transactions (local_day DESC);
CREATE INDEX ON transactions (category, local_day);
CREATE INDEX ON transactions (counterparty_id);
CREATE INDEX ON transactions (settles_id) WHERE settles_id IS NOT NULL;
CREATE INDEX ON transactions (updated_at, id);
CREATE INDEX ON transactions USING GIN (tags);
```

### `kind` — udhaar is a transaction type, not a table

`direction` says which way money moved. `kind` says what the movement *meant*,
and that is what the budget reads:

| kind | direction | Counts against the daily limit |
|---|---|---|
| `expense` | debit | **yes** |
| `income` | credit | no — it is the pool, not a spend |
| `lent` | debit | no — still your money, now a receivable |
| `borrowed` | credit | no — not your money |
| `repayment` | either | no — settles an earlier `lent` or `borrowed` |
| `transfer` | either | no — pass-through, e.g. papa's ₹8,000 for rent |

A separate udhaar table would duplicate amount, date, counterparty and direction,
and then need reconciling against the ledger it duplicates.

`settles_id` points a repayment at the original `lent` or `borrowed` row. Partial
repayment falls out for free: outstanding is the principal minus the sum of rows
that settle it. The workbook has been doing this by hand since day one.

### Fixed costs are ordinary transactions

Rent, EMI, subscriptions and money sent home are `expense` rows with a category.
No schedule, no recurrence, no generated rows — recurrence does not model them
honestly, since rent covers a period and a subscription's renewal date drifts.
The monthly fixed total is `SUM(amount_paise) WHERE category IN (...)`.

This removes the need for any per-month budget table: the month comes from
`local_day`, income is `kind = 'income'`, and the only figure that cannot be
derived is what the bank actually holds — `balance_checks` below.

### Location resolves to a place, and the raw fix is kept

`transactions.place_id` points at where you were. The coordinates that resolved
to it are **not** on the ledger row — they live in `predictions.signals`.

Coordinates are a means, not an end: the useful answer is *which place*. But
resolving and discarding would make a wrong answer permanent, and reverse
geocoding is often wrong — it will happily return a neighbourhood where you
wanted a shop. Keeping the raw fix in the signal snapshot means a bad resolution
can be redone.

**A place is only created when the fix is good enough.** Worse than
`ACCURACY_LIMIT_M` (50m) covers a whole market, and inferring a shop from that is
inventing data. The coordinates are still recorded, so the transaction can attach
to a place later once a cleaner fix names one.

Matching, on each payment:

```
coordinates → a place within its radius?
                yes → attach
                no  → create one, if accuracy allows
```

The counterparty shortens this: if `MOHAN LAL` already has a place, the
payment attaches without consulting coordinates at all.

### `category` is a flat string

`Khana/Grocery` is one name that happens to contain a slash. There is no parent,
no child, no rollup — food and grocery are simply different categories. Totals
stay unambiguous because there is only ever one key to sum by.

### `tags` — for what cuts across categories

A transaction has exactly one category, so anything spanning several needs
somewhere else to live. The workbook shows this being done by hand already:

```
Mithai (Rakhi)          ₹290   Khana/Grocery
Sister ko diya (Rakhi)  ₹500   Logon ko diya
Rakhi - sisters ko     ₹2500   Logon ko diya
                        ─────
        note: "Rakhi ka total ab 3,290"
```

Two categories, one occasion, totalled manually in a note. `Rakhi` is not worth a
category — it happens once a year — and cigarettes show the same shape across
`Health/Diet` and `Dost & Bahar`, tracked in prose as *"16 Aug ke baad band"*.

A GIN index makes `WHERE tags @> ARRAY['rakhi']` cheap.

### Fields deliberately absent

- **`motion_before`** — used only for prediction, so it belongs in the signal
  snapshot, not on the ledger row.
- **`note`** — the workbook's notes were three different things wearing one
  column: confidence, provenance, and correction feedback. Each now has its own
  home. A free-text note beside them would immediately be used for all three
  again.
- **`type`** — with a table per entity it would be the same constant in every
  row of that table.

---

## `counterparties`

Whoever the money moved to or from — a shop, a friend, an employer.
`spec/substrate.md` settled that place, payee and counterparty are one table.

```sql
CREATE TABLE counterparties (
  id           TEXT PRIMARY KEY,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

  raw_name     TEXT NOT NULL UNIQUE,   -- "MOHAN LAL", exactly as captured
  display_name TEXT,                   -- "chai aur samosa", set once by the user
  default_category TEXT,               -- what payments here usually are

  is_peer      BOOLEAN NOT NULL DEFAULT false,
  in_contacts  BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX ON counterparties USING GIN (raw_name gin_trgm_ops);
```

Three name-ish fields, each answering a different question, which is why the
names have to be precise:

- `raw_name` — what the payment system said. Never edited; it is how the next
  notification is matched.
- `display_name` — what you call it. *"chai aur samosa"* is not a category and
  never will be.
- `default_category` — the spending bucket, e.g. `Health/Diet`.

`is_peer` flips to true the first time money comes **back** from this
counterparty, and never flips back. Shops take money; people also return it.

Counts and amount ranges are **not** stored. `txn_count`, `amount_min/max/median`,
`first_seen`, `last_seen` are all a `GROUP BY` away, and storing them means
keeping them correct on every insert, correction and delete.

---

## `predictions`

Everything the model saw and everything it guessed. Separate from the ledger
because a prediction is not a fact about the world.

```sql
CREATE TABLE predictions (
  id             TEXT PRIMARY KEY,
  transaction_id TEXT NOT NULL REFERENCES transactions(id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

  predicted_by   TEXT NOT NULL CHECK (predicted_by IN ('dictionary','rules','llm')),
  model          TEXT,
  signals        JSONB NOT NULL,

  pred_category    TEXT,
  pred_description TEXT,
  confidence       REAL NOT NULL,
  reasoning        TEXT,

  actual_category    TEXT,
  actual_description TEXT,
  user_feedback      TEXT,
  corrected_at       TIMESTAMPTZ
);
CREATE INDEX ON predictions (transaction_id);
CREATE INDEX ON predictions (corrected_at) WHERE corrected_at IS NOT NULL;
```

**Signals are snapshotted, not recomputed.** `payee_seen_count` was 3 when the
model predicted and is 47 today; recomputing it later produces a training example
that never existed. The vector is stored exactly as the model saw it.

**`signals` is JSONB on purpose.** The feature set will change as signals are
added, and nothing ever aggregates over an individual signal. That is the case
JSONB is for — the opposite of the ledger, where columns and indexes matter.

```json
{
  "amount_paise": 9800, "method": "digital",
  "hour_of_day": 19, "day_of_week": 1, "is_working_day": true,
  "counterparty_name": "MOHAN LAL", "payee_seen_count": 3,
  "payee_median_paise": 6100, "amount_band_match": "Health/Diet",
  "has_bidirectional": false, "in_contacts": false,
  "mins_since_last_txn": 12, "last_txn_category": "Transport",
  "motion_before": "WALKING", "location_cluster": "ghar"
}
```

**Corrections are feedback.** When confidence is low the user gets an edit
affordance; editing writes `actual_*`, `corrected_at`, and optionally
`user_feedback` in their own words. The training set is then
`WHERE corrected_at IS NOT NULL`, and one transaction may carry several
predictions — the first guess, then a re-prediction after the skill file
improved — which is how you measure whether the skill file helped.

---

## `balance_checks`

The user stating what is actually in the bank. An observation, not a derivation —
nothing in the ledger can produce it.

```sql
CREATE TABLE balance_checks (
  id           TEXT PRIMARY KEY,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  as_of        DATE NOT NULL,
  amount_paise BIGINT NOT NULL,
  note         TEXT
);
```

This is the other half of the reconciliation in `spec/paisa-categorise.md` §4.4.
The gap is a query, not a stored figure:

```
income − fixed − expenses − net_lent − stated_balance
```

which on 28 Aug is ₹6,921.

---

## Incremental reads

Clients ask for what changed rather than re-reading everything:

```sql
SELECT * FROM transactions
WHERE  updated_at > $cursor
ORDER  BY updated_at, id;
```

Deletes are visible to that query because they are soft — `deleted_at` is set and
the row stays. A hard delete would simply vanish from the result and the client
would keep its stale copy forever, which is the failure this avoids.

The cursor is `(updated_at, id)`, not `updated_at` alone: two rows written in the
same millisecond would otherwise let paging skip one.

A dedicated event log with a single monotonic sequence across all tables is the
alternative, and it becomes the better answer once there is a client holding its
own copy. Deferred for now — `spec/notes.md`.

```sql
CREATE INDEX ON transactions (updated_at, id);
```

---

## Identity and de-duplication

`id` is always a **ULID** — opaque, stable, sortable by creation time, and never
derived from the row's contents.

De-duplication is a **separate column**:

```sql
id         TEXT PRIMARY KEY,   -- ULID, always
dedupe_key TEXT UNIQUE         -- hash(package + amount + counterparty + minute)
                               -- for captured rows; NULL for manual ones
```

**Why not use a content hash as the id.** It binds identity to the de-duplication
rule. Today the rule is `minute`; the day it becomes a five-minute window, every
existing id changes — and every row referencing them (`settles_id`,
`supersedes_id`, `predictions.transaction_id`) breaks. Ids must never move;
de-duplication rules will.

**Why the constraint belongs in the database as well as the code.** The
application decides what "duplicate" means and computes `dedupe_key`; the
database only enforces it. Check-then-insert has a gap that application code
cannot close — two notifications processed concurrently both find nothing and
both insert, and a retry after a network timeout does the same. It is rare with
one user, and silent when it happens.

```sql
INSERT INTO transactions (...) VALUES (...)
ON CONFLICT (dedupe_key) DO NOTHING;
```

Manual rows carry `NULL`, and Postgres does not treat two `NULL`s as equal — so
two ₹40 chais typed on the same day both insert, which is correct. They are two
transactions.

## `profile`

One row. Goals and preferences — not observations, not transactions, and not
derivable from either.

```sql
CREATE TABLE profile (
  id                   TEXT PRIMARY KEY DEFAULT 'me',
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  savings_target_paise BIGINT,
  timezone             TEXT NOT NULL DEFAULT 'Asia/Kolkata'
);
```

`timezone` sits here because `local_day` depends on it, and hardcoding
`Asia/Kolkata` in the write path would make it invisible the day it is wrong.

## Import from the workbook

The `Din` column is a day-of-month integer and the workbook carries no year —
August 2026 is implied by context. Made explicit on import; `local_day` is a real
`DATE` from then on.

## Next

1. Alembic migration
2. Import script from the workbook
3. `GET /deck` returning the transaction rows
