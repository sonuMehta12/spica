# Places — where the money was spent

> Shipped 2026-09-07. The `places` table had existed since the paisa data model
> and never had a row.

## The problem

`transactions.place_id` has pointed at `places` since the schema was written,
and not one of 92 payments uses it. The table waited for a location source that
never arrived, so the app cannot answer *"Mohan Lal pe is mahine kitna gaya"*
or *"chai pe kitna"* — questions about **where**, which category cannot answer
because one category covers a dozen shops.

This is not a list of places to visit. It is where money has already moved.

## What it does

**A place is a spot on the map that payments happen at.** Two ways one appears:

- **You put it there.** Search or long-press on the map, drop a pin, name it,
  say what it is. That is the whole flow, and it is what makes the prototype
  usable before any phone is involved.
- **It repeats.** When capture exists, a payment carries the phone's fix. Three
  separate days of payments inside the same small radius, and the agent proposes
  a place: *"Chilla Dallupura — 3 baar. Naam de doon?"* Below that it stays raw
  points.

Once a place exists, a payment at it is **matched, not tagged**: a fix inside
`radius_m` gets the place, and the place's `category` and `counterparty_id`
become the suggestion for what the payment was.

***Your data → Places*** is a map with your pins and a list under it. Each pin
carries what the ledger knows: **how many payments, how much, when last** — all
counted, never stored.

## The data, as it stands today

| | |
|---|---|
| `places` | 15 columns, **0 rows** |
| `transactions.place_id` | exists, indexed, **0 rows use it** |
| `predictions` | 15 columns, **0 rows** |

The table already has `name`, `lat`, `lng`, `radius_m` (default 50),
`address`, `raw_type`, `category`, `provider`, `provider_id`, `confidence`,
`user_id` and the envelope — plus `ix_places_latlng` and
`ACCURACY_LIMIT_M = 50.0`, the fix quality below which resolving is refused
because a 500 m circle covers a whole market.

**The coordinate we already store is the *place's*, not the payment's.** The
plan was for a payment's raw fix to live in `predictions.signals` — "kept there
so a wrong resolution can be redone rather than baked into the ledger".

**That plan has a hole, and it is the important finding.** `predictions` is the
agent's guess-log: `pred_category`, `reasoning`, `user_feedback`. A payment the
agent never guessed about has **no prediction row** — so its fix has nowhere to
live. Those are exactly the fixes that matter, because a payment at an unknown
spot is what *discovers* a place by repeating. Under the old plan the discovery
signal is thrown away.

## Data

### `transactions` — the fix goes on the ledger

```sql
ALTER TABLE transactions
  ADD COLUMN lat             DOUBLE PRECISION,
  ADD COLUMN lng             DOUBLE PRECISION,
  ADD COLUMN fix_accuracy_m  DOUBLE PRECISION;   -- how much to trust the two above
```

Where the phone was when money moved is **what happened**, not what was guessed,
which is the ledger's own definition of what belongs in it. Keeping it here also
means a wrong match is still redoable — `place_id` can be cleared and recomputed
from the fix, which was the whole point of the original note.

`predictions.signals` keeps its job: what the *model* saw. Not where the *phone*
was.

### `places` — five columns join the eleven already there

```sql
ALTER TABLE places
  ADD COLUMN kind            TEXT,     -- home|office|shop|eat|hangout|pickup|gym|other
  ADD COLUMN counterparty_id TEXT REFERENCES counterparties(id),
  ADD COLUMN note            TEXT,
  ADD COLUMN source          TEXT NOT NULL DEFAULT 'manual',  -- manual|search|detected
  ADD COLUMN confirmed_at    TIMESTAMPTZ;
```

- **`kind`** — *chai tapri* and *the paan shop* are different facts about one
  street corner. `home` and `office` are pins like any other.
- **`counterparty_id`** — *this is Mohan Lal's shop*. It is what lets the pin
  show `₹285 · 4 payments` without a single payment being tagged by hand.
  Optional both ways: Rapido has no place, a food court has many counterparties.
- **`source`** — how the pin got here, and it is what keeps a hand-placed pin
  distinguishable from a discovered one. A `manual` pin leaves `provider`,
  `provider_id`, `raw_type` and `address` empty and carries `confidence = 1.0`;
  you put it there, there is nothing to doubt.
- **`confirmed_at`** — a `detected` pin is a guess until you say otherwise, and
  shows `· andaaza` exactly as an inferred relation does on a person.
  `confidence` stays what it always was — the *detector's* own measure, which
  the agent can threshold on. `confirmed_at` is what the **UI** reads, because
  marking it or not is the only question a screen asks.

### Counted, never stored

Unlike the exercise library, places **have a ledger under them** — the
transactions that point at them — so every number is a query:

```sql
payments  = COUNT(*)              WHERE place_id = :p
spent     = SUM(amount_paise)     WHERE place_id = :p AND direction = 'debit'
last_seen = MAX(local_day)        WHERE place_id = :p
```

Delete a payment and the pin corrects itself with no write.

## API

```
GET    /places                 → pins with payments · spent · last seen
POST   /places                 → { id, name, lat, lng, kind, radius_m?, counterparty_id?, note? }
PATCH  /places/{id}            → any of those
DELETE /places/{id}            → soft; payments keep their place_id
PATCH  /transactions/{id}      → place_id   (added here; the patch shape did not have it)
```

## The map

**Leaflet with OpenStreetMap tiles** — free, no key, and the only new dependency
in this queue. Search is **Nominatim**, OSM's own geocoder: also free and
keyless, rate-limited to about one request a second, which is fine for one
person typing.

Long-press or click drops a pin; search jumps the map and drops one. It proves
the **data and the gesture**, not the rendering — on Android this is a native
map view and nothing in the schema changes.

## Rules

- **A pin is somewhere money moved, or will.** Not a wishlist — a place you want
  to visit is a travel app (`spec/substrate.md` §10).
- **The fix is always kept; the place is not always created.** Every captured
  payment stores its coordinates. A *place* appears only on the third separate
  day at one spot, or because you dropped it. Counterparties work the other way
  round — the row is created every time and the threshold gates only what the
  agent *says* — because a counterparty row is a match key the ledger needs
  anyway, and a place is a claim about the world.
- **A fix worse than `ACCURACY_LIMIT_M` matches nothing.** It is still stored;
  it just cannot resolve. Inferring a shop from a 500 m circle is inventing data.
- **Not approving is not deleting.** An unconfirmed pin stays on the map marked
  `· andaaza`, and the agent does not ask again.
- **Nothing is backfilled.** None of the 92 payments has coordinates and none
  will; places start from the first pin you drop.

## What the build changed

**`TransactionPatch` had no `place_id`.** This spec claimed it was already
accepted; it was not, so *"⋮ → Where"* could not have worked. Added, along with
`lat` / `lng` / `fix_accuracy_m` on `TransactionIn` — but **not** on the patch:
the fix is what the phone read, and re-reading it is not an edit. Redoing a
wrong match means clearing `place_id`, which is exactly why the fix sits beside
it.

**Half a coordinate was a stack trace.** The check constraint caught it, as a
raw `IntegrityError`. A `model_validator` now refuses it with a sentence and the
constraint stays as the backstop.

**The seeded library is empty and *Where it came from* is hidden.** Every
section reads a real table as of this commit, so the last five seeded `place`
rows went the way the articles and videos did. The panel is hidden rather than
deleted — it is still the only picture of what the capture extension is for, and
it fills again the moment the extension saves anything.

## Decided against

| Option | Why not |
|---|---|
| Raw fixes in `predictions.signals` | A payment with no prediction row has nowhere to put its fix — and those are the ones that discover new places. Reversed here; see *Data* |
| Waiting for GPS before building anything | The places that matter are known, not discovered, and waiting kept the table empty for a month. A pin you drop is worth as much as one the phone finds |
| Merging Places into the People section | Reversed 2026-09-07. They are separate sections: a map and a list are different interactions, and the tables were always separate anyway |
| Storing payments / spent on the pin | Drifts on the first deleted payment. The ledger already knows |
| One place per counterparty automatically | Rapido has no place; a food court has many counterparties. The link is a choice, not a rule |
| A `visited` flag | `payments > 0` already says it |

## Definition of done

| Check | Expected |
|---|---|
| Migration | five columns on `places`, three on `transactions`; existing constraints intact |
| Half a coordinate | a 422 saying *lat and lng go together*, not a check-constraint stack trace |
| A credit at a pin | counts as a payment there, adds nothing to spent |
| Search *Chilla Dallupura* → drop → name it → kind `eat` | a pin; `source = 'search'`, confirmed |
| Long-press the map → *Ghar* → kind `home` | a pin with `source = 'manual'`, no provider fields |
| Link a pin to Mohan Lal | the card reads `₹285 · 4 payments` with nothing tagged by hand |
| ⋮ on a payment → *Where* → a pin | `place_id` set; the pin's count goes up by one |
| Delete that payment | the count goes back down — nothing to update |
| Delete a pin | off the map, out of `GET /places`; the payment keeps its `place_id` |
| Tests | `backend/tests/test_places.py` — 16 tests, green |
