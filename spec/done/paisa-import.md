# Paisa — workbook import

> Done. `backend/scripts/import_workbook.py`, idempotent.
> Source: `Paisa_Tracker.xlsx`, Aug 2026 · Target: the schema in `spec/done/paisa-data-model.md`

The point of importing real history is that the schema gets tested against what
actually happened. That only works if the import is **faithful** — inventing a
value to fill a column would test the schema against fiction.

Where the workbook does not say something, the column stays `NULL`.

## Daily Log → `transactions` (73 rows)

| Workbook | Column | Rule |
|---|---|---|
| `Din` | `local_day` | `2026-08-<Din>`. The workbook has no year; August 2026 is implied by context and made explicit here |
| `Din` | `occurred_at` | Midday UTC. **The workbook records no clock time** — noon marks "day known, time unknown", not a guess |
| `Amount` | `amount_paise` | `× 100`. All 73 are whole rupees |
| `Category` | `category` | Verbatim, slash and all |
| `Kya kharcha` | `description` | **Verbatim, in full** — see below |
| `Kya kharcha` | `counterparty_name` | Two-or-more ALL-CAPS words, how UPI writes a payee. 17 rows |
| `Cash/Digital` | `method` | 24 rows filled; **49 blank → `NULL`**, never defaulted |
| `Note` | `note` | Verbatim, all 26 |
| — | `direction` / `kind` | `debit` / `expense` on all 73 |
| — | `source` | `manual`, except two rows whose note says *"notification se"* |

**Description keeps the payee name rather than having it stripped.** The
original plan removed it, on the grounds that `counterparty_name` already holds
it. But `MANISH SHARMA` is a description made *entirely* of the name, so
stripping leaves an empty string in a `NOT NULL` column — and
`MOHAN LAL (paan shop - cigarette)` would become `(paan shop - cigarette)`,
which is not a sentence anyone wrote. Nothing is lost by keeping both: the name
is separately available for matching.

### The four `Logon ko diya` rows are `expense`

₹800 to sister, ₹1,000 to mummy, ₹500 and ₹2,500 for Rakhi. Decided by the user.
A gift is the safe default: wrongly marking one as `lent` inflates money you
think is coming back.

### Rakhi is the case that justifies `tags`

Three rows carry `tags = {rakhi}` — ₹290 under `Khana/Grocery`, ₹500 and ₹2,500
under `Logon ko diya`. They sum to **₹3,290**, exactly the figure the workbook's
author had totalled *by hand in a note* because no category could produce it.

A row has one category. A festival cuts across categories. That is the whole
argument for the column, and the source data made it without being asked.

## Udhaar → `transactions` (7 rows)

The sheet has **no dates at all**. These come from the user, from memory, and
carry `confidence = 0.5` so the imprecision stays visible instead of being
assumed away.

| Who | Amount | Lent | Back |
|---|---|---|---|
| Dost 1 | ₹7,000 | 2 Aug | 12 Aug |
| Dost (1,000 wala) | ₹1,000 | 2 Aug | 12 Aug |
| Badi sister | ₹2,000 | 2 Aug | 12 Aug |
| Dost 2 | ₹4,000 | **24 Jun** | still out |

Each lending is a `lent` row; each return a `repayment` row with `settles_id`
pointing at it. Outstanding falls out as principal minus the sum of rows
settling it — no `baaki` column, and partial repayment works for free.

### The ₹4,000 was lent in June, and the workbook was wrong about it

The Dashboard counts ₹4,000 as an August outflow, which is how it arrives at a
₹6,921 gap. But the money left in **June**, so it was never part of August's
₹42,052. Corrected:

```
42,052 − 22,139 (kharcha) − 0 (net udhaar) − 8,992 (bacha) = ₹10,921 gayab
```

Net udhaar for August is zero: ₹10,000 went out and came back inside the month.

The real "jo yaad hi nahi" is **₹4,000 larger** than the spreadsheet showed.
This is worth stating plainly rather than quietly matching the old number — the
app's rule is that a metric which would flatter the user is the one to show
straight.

## Counterparties (15)

Eleven payee names from Daily Log, plus the four people on the Udhaar sheet.

The plan said eleven. The four udhaar people are counterparties too — they only
*look* different because the sheet recorded a placeholder (`Dost 1 (naam?)`)
instead of a name. Leaving them out would break `settles_id` and leave `is_peer`
with no data at all.

`display_name` and `default_category` stay `NULL`: those are the user's to set,
and filling them from a guess puts words in their mouth.

**`is_peer` is true for exactly three** — the ones whose money came back. Dost 2
stays false, because nothing has returned. The flag got real data on day one.

## Setup → transactions, `balance_checks`, `profile`

```
balance_checks:  ₹8,992 as of 2026-08-22   ("bank check karke bataya")
profile:         savings_target_paise = ₹11,000
```

### The Setup money is six ordinary transactions

Added after the first import, once the deck work needed the arc to be derived
rather than hardcoded.

| Day | Kind | Amount | Category | Tag | Confidence |
|---|---|---|---|---|---|
| 2 Aug | income | ₹95,000 | Salary | — | 0.7 |
| 13 Aug | income | ₹8,000 | Family | — | 1.0 |
| 3 Aug | expense | ₹40,000 | Ghar | `fixed` | 0.7 |
| 7 Aug | expense | ₹10,000 | EMI | `fixed` | **0.4** |
| 10 Aug | expense | ₹3,000 | Subscriptions | `fixed` | 0.7 |
| 14 Aug | expense | ₹7,948 | Rent | `fixed` | 0.9 |

Dates are from memory — the sheet carries only one (13 Aug) and admits
*"Salary date confirm nahi hui"* — so each row's confidence reflects how firm
its date is. EMI at 0.4 is the loosest: *"kuch din baad"* is all there was.

**`MERE HAATH MEIN THA` was a subtraction wearing the name of a fact.** The
workbook kept these six out of the ledger and reported the remainder, ₹42,052,
as money held. It was never held: ghar ka paisa is spent and never returns, and
the same is true of EMI, subscriptions and rent. They are expenses with a
category, exactly as this spec's Setup section always said they would be.

**`fixed` is a tag, not a column.** Being fixed cuts across categories — Ghar,
EMI, Subscriptions and Rent are four different things — which is precisely the
argument Rakhi spending won for tags in the first place.

Everything the card needs now derives, with nothing stored:

```
daily-limit kharcha    expense minus tag:fixed   = ₹22,139   (unchanged)
pale arc               expense with tag:fixed    = ₹60,948   (was hardcoded)
arc total              income − fixed            = ₹42,052
August ka asli gap     income − expense − 8,992  = ₹10,921
```

That last line is the number this spec worked out by hand when the June ₹4,000
was corrected. It is now a query — **and an estimate, not a fact.** It compares
a balance stated on the 22nd with spending logged through the 28th, assumes the
month began with an empty account, and cannot see cash sitting outside the
bank. A true gap needs two balance checks with full capture between them; until
notification capture lands, this figure is directional. It is still shown —
directional honesty beats silence — but it is `andaaza`, and renders as such.

## Not imported

- **`predictions`** — nothing was predicted. Every row was typed by a human, so
  there is no signal snapshot and no guess to learn from.
- **`places`** — the workbook has no coordinates.

## Idempotency

Every imported row carries `dedupe_key = xlsx:<sheet>:<row>`. Re-running inserts
nothing. This widens what `dedupe_key` means — it was built for "this
notification already arrived" — but the question is identical: has this exact
source row landed already?

## Verified after import

| Check | Expected | Result |
|---|---|---|
| Rows | 73 + 7 | 73 `expense`, 4 `lent`, 3 `repayment` |
| Sum of `expense` | ₹22,139 | ₹22,139 |
| Category totals | all seven match the Dashboard | all seven exact |
| Rows with `method` | 24 | 21 digital + 3 cash |
| `rakhi` tag total | ₹3,290 | ₹3,290 |
| Outstanding udhaar | ₹4,000, one person | ₹4,000, Dost 2 |
| Re-run | nothing added | `added 0, skipped 80` |
