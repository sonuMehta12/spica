# Commitments: what you still owe this month

> Status: **shipped 2026-10-10; the 21 chat sentences pass in the app.** The backend — the table, the migration and
> its backfill, rolling, linking, the limit, the routes, `manage_commitment`,
> the Commitments card, Your day's due-soon line — is tested
> (`backend/tests/test_commitments.py`, 37 tests; the suite is green at 440).
> The phone is built and was seen on the emulator. **Still owed:** the web has
> been built, typechecked and bundled but not yet seen running; the amber
> guessed link on a real payment and *Make this a commitment* have not been
> seen on the device; `n2n_eval` does not hold the sentences yet.
> Supersedes the LOCKED half of `spec/done/fixed-costs.md`; the `fixed` /
> `repeats` flags are re-decided here. Stage 1 of the old plan (the card, and
> the `commitments` read in `paisa_report`) shipped 2026-09-13.
> Surface: backend (a table, routes, one agent tool) · android (the page, the
> sheet, the Money widget) · web (the chat card and Your data)

## How it works today

A commitment is **not a thing the user can see or set**. It is derived, every
time the limit is worked out, from payments the user flagged last month.

```
pool   = income + repaid + borrowed − all expenses − lent − paid back
owed   = last month's rows with  repeats = true, one line per category,
         for every category with no  fixed  payment yet this month
       + borrowings from earlier months not yet repaid
limit  = max(0, (pool − owed − savings goal) ÷ days left)
```

(`app/paisa_summary.py` — `limit_as_of`, and the `commitments` field beside it.)

**Where the flags come from.** Each payment's ⋮ tray has *Fixed* and *Repeat*.
Marking a row *Repeat* on, say, August's rent is what makes September owe it.
A payment in a category that repeated last month inherits both flags, so
September's rent, once paid, clears the line.

### On the live ledger, today (2026-10-10)

| Line | Expected | Paid | Owed |
|---|---|---|---|
| Ghar | ₹40,000 | — | ₹40,000 |
| EMI | ₹10,000 | — | ₹10,000 |
| Rent | ₹8,421 | — | ₹8,421 |
| Subscriptions | ₹3,000 | — | ₹3,000 |
| Health/Diet | ₹2,000 | ₹50 | **₹0** — and not a commitment at all |
| **Owed** | | | **₹61,421** |

Pool ₹69,636 − owed ₹61,421 leaves ₹8,215, and the savings goal takes the rest:
the limit is **₹0**. That is the *Left to spend today ₹0 — everything left this
month is committed* on the phone. It is not a bug in the arithmetic. It is the
arithmetic working on numbers the user cannot see and cannot change.

### Why the user cannot change it

- **There is nothing to tap.** *Committed* on the Money widget is a plain figure.
  No page lists the lines; only the agent can, and only as text.
- **The only lever is a flag on an old payment.** To drop *Rent* from this
  month, the user would have to find August's rent row and clear *Repeat* on it.
  Nothing says that is the way.
- **The amount is whatever last month was.** It cannot be edited. A rent that
  went down, or an EMI that ended, still reserves last month's money.
- **A commitment can only exist after a payment did.** A new EMI that starts
  this month, a one-off insurance premium, a bill not yet paid even once: there
  is no way to say so. The agent has no tool for it either — `correct_payment`
  can only set the flags on a payment that already happened.
- **Any flagged payment settles the whole line.** ₹50 against Health/Diet's
  ₹2,000 clears it. The deeper fault is the line: Health/Diet is everyday
  spending, not an obligation. A payment in it was flagged *Repeat* once and has
  reserved ₹2,000 a month since — the flag cannot tell a rent from a habit.
- **A zero hides which zero it is.** `max(0, …)` shows the same ₹0 for *nothing
  left* and *₹3,799 past the line*.

## The problem

`fixed` is one boolean doing two jobs, and only one of them is a fact.

**Job one, a label.** *This is a rent-type payment.* True the moment it is
written, never changes.

**Job two, a forecast.** With `repeats` beside it, last month's amount in that
category becomes owed next month — money reserved before it is spent.

Marking a payment `fixed` therefore does something the word does not say: it
quietly reserves money in a future month. The user set a label; the app made a
prediction. And the prediction has no handle: it cannot be seen, corrected,
skipped or removed — which is every complaint above.

Commitment is also not only `fixed`: a borrowing from an earlier month joins
the same total in a separate branch of the same function. The idea exists twice
under one name, and has no name of its own.

## What it does

**A commitment is an obligation, not a habit.** Rent, an EMI, a loan, a
subscription, money borrowed: things that are owed whether or not the person
spends. Food, health, transport and shopping are spending, and a category of
spending is never a commitment — a ₹50 purchase there is not a part payment of
anything. The app cannot tell the two apart from a category name, so the person
decides: nothing becomes a commitment unless it was made one, and the page lets
any line be deleted at once.

**A commitment is a row the user owns.** One per thing owed, per month. It can
be made, changed, skipped, repeated, linked to the payment that settles it, and
deleted — from the page, from chat, from a payment's tray.

| Field | |
|---|---|
| `name` | *Rent*, *Home loan EMI*, *Insurance* |
| `category` | the ledger category its payment is filed under |
| `amount_paise` | what is expected this month — editable |
| `amount_source` | `stated` (the user set it) · `rolled` (copied from last month) |
| `local_month` | the month it is owed in, the first of it |
| `due_day` | 1–31, optional; clamps to the month's last day. Orders the list and says *due Friday*; it never changes the limit |
| `repeats` | comes back next month — **on by default**, everywhere: a commitment the user set is expected again until they say *this is no longer a commitment* or change its amount |
| `skipped_at` | *not this month* — the row stays, owed is 0 |
| `carried_from_id` | the earlier month's row this one is the unpaid remainder of |

**Paid is never stored.** A payment links to a commitment (`transactions.
commitment_id`, nullable), and *paid* and *owed* are worked out live:

```
paid   = Σ linked payments
owed   = 0                          if skipped
       = max(0, amount − paid)      otherwise
```

So a deleted payment gives the commitment its debt back, an edited amount is
at once in the limit, and no card holds a sentence about what is owed
(`CLAUDE.md`: *never store a sentence about the user's own data*).

### Where a month's commitments come from

1. **The user makes one** — on the page, in chat, or from a payment (*Make this
   a commitment*). `repeats` says whether it returns.
2. **Rolled** — the first time the current month is read, every `repeats`
   commitment of last month is copied forward. Its amount is what was **paid** if
   anything was (the best guess for the next bill, as today), else what was
   expected. It is marked `rolled`, so it wears the amber dot — an inferred
   figure — until the user states it or pays it.
3. **Carried** — what last month left unpaid comes forward as its own line,
   *Rent · from September*, for the remainder only. `repeats` off. An unpaid
   commitment does not evaporate at midnight on the 1st; the user said it
   plainly: *"is month 50k commit, 30k pay kiye, 20k left — next month ka 30k
   aur ye 20k."*
4. **Borrowings** are **not** rows. They are lines worked out live from the
   udhaar ledger — amount minus repayments, for borrowings taken before this
   month — read-only here, and their action is *Repay*. Storing a copy would
   break the live-id rule and disagree with the udhaar page the first time a
   repayment landed.

Rolling runs **once per month on first read of the current month**, never on a
clock, and is idempotent (a unique key on the row it was rolled from). Past
months are never back-filled; they show only what was recorded.

### Settling: a payment links to one commitment

A payment is an expense the user logs as ever. When it is written:

- **One open commitment in its category** → it links, **and the link is marked
  as inferred** — an amber dot on the receipt and on the line, with a one-tap
  *Not this*. The app is guessing that this payment is that bill; a wrong guess
  is small and visible, and a bill like Rent or EMI clears itself. The receipt
  says it: *Rent · ₹8,421 → settles Rent ●*. Moving the link by hand, or
  confirming it, removes the dot.
- **More than one** (a carried line and this month's; two loans) → the oldest
  month first, then the earlier due day. Deterministic and explainable, and the
  total owed in the category is the same whichever line it lands on. If the
  payment's own words match one commitment's name (*"home loan emi"*), that one
  wins.
- **None** → it stays ordinary spending, as now.

The user can move the link: a payment's ⋮ has *Counts toward…* (the month's
open commitments) and *Not a commitment*. A link survives a later category
edit — it is a statement, not a guess.

**A linked payment is not discretionary spend.** It leaves *spent today* and
the pale arc takes it, as `fixed` payments do now; the pool already subtracted
it. Nothing about the limit's arithmetic moves, only the label.

**No hand-settling.** There is no *mark as paid* without a payment: the money
would stay in the pool and the limit would rise by an amount that has actually
left. *"Rent cash de diya"* is a payment to log — one sentence — and it links.
What the user can say without a payment is **skip**: *not this month.*

### The limit

```
limit = (pool − Σ owed − savings goal) ÷ days left       may go negative
```

`Σ owed` is this month's commitments plus the live borrowing lines. **It is
still subtracted**: a limit that ignores rent due tomorrow lets you spend the
rent today, a comfortable lie. The complaint was never the subtraction, it was
that it could be neither seen nor changed. Both are fixed.

**Negative is shown, in red.** *₹0* and *₹3,799 past the line* are different
facts. The phone already draws overage in red (`money-over`); the server stops
clamping.

**Before salary lands.** With no income row yet this month **and** a limit that
would be negative, the limit is **unknown** — `—`, *Salary not in yet* — not a
red number that reads as overspending. Unknown is not zero. (A month with no
income but a positive limit — carried money, a loan — still shows its number.)
On the wire the summary omits the key (`exclude_none`), so a client reads
*absent* as unknown; the Commitments page returns an explicit `null`.

## The surfaces

### The page — *Commitments*

Opened by tapping **Committed** on the Money widget, from a chat card's lines,
and from the *Left to spend* tile's line whenever the limit is 0 or below
(*Everything left this month is committed* gets a **See what's committed**
link — the thing that was missing when the phone said ₹0).

```
Commitments · October                               ₹61,421 owed
─────────────────────────────────────────────────────────────
Ghar            due 1st   ● ₹40,000         owed ₹40,000   ⋮
EMI             due 5th     ₹10,000         owed ₹10,000   ⋮
Rent            due 5th   ● ₹8,421          owed ₹8,421    ⋮
Subscriptions   due 7th     ₹3,000          owed ₹3,000    ⋮
Health/Diet                 ₹2,000 · ₹50 paid  owed ₹1,950 ⋮
Rent · from September       ₹4,000 left     owed ₹4,000    ⋮
Dost ka udhaar  (borrowed)  ₹6,000          owed ₹6,000   Repay
─ Skipped ───────────────────────────────────────────────────
Gym             skipped this month                         ⋮
                                              + Add commitment
```

- ● is the amber dot: a `rolled` amount, not yet stated.
- A header line works the sum out: *₹61,421 owed · ₹8,215 free · limit ₹0* — the
  chain from the pool to the limit in one place, so a zero is never a mystery.
- Settled lines sort to the foot, struck, with the payment they were settled by.
- **Coverage is shown**: *3 of 6 commitments paid.*
- The ⋮ on a line: **Edit** (amount, name, due day, category), **Skip this
  month** / **Unskip**, **Stop repeating** / **Repeat**, **Delete**.
  *Delete* asks for a confirmation and **ends the line**: its payments become
  ordinary spending and it does not roll next month. To leave only this month
  out, use **Skip this month** — they are different intents, so they are
  different buttons. There is no *Undo* on a delete; making it again takes one
  sentence.
- **+ Add commitment** opens the same sheet: name, amount, category, due day,
  *repeats every month* (**on** by default; switch it off for a one-off).

Opening a month other than the current one shows what was recorded and nothing
more: past months are read-only, and a future month does not exist yet.

### The Money report — a **Commits** tab

The report's Payments section filters by tab: *All · Lent · Borrowed · each
category*. **Commits** joins them, right after Borrowed: this month's
commitments as rows in the same list, with the ⋮ actions, a count, the owed
total and the coverage line, and `+ Add commitment` at the foot like Lent and
Borrowed have. It is not date-range filtered — commitments are monthly — and
says so when the range is not this month. Borrowings stay on Borrowed. A
payment linked to a commitment still shows in *All* with `· Rent` in its
sub-line, so the two views agree. The full page stays one tap from the Money
widget. The report's head carries no link to it (2026-10-11): the Commits tab
already holds the same lines.

### The Money widget

No new widget — Home stays five (`CLAUDE.md`). Two changes: **Committed** is a
link to the page, and the explanatory line under a zero limit links there too.
**Your day** lists what is due within three days — *Rent due Friday* — as part
of this work (below).

### Chat — every verb, in a sentence

| User says | Tool call | Reply |
|---|---|---|
| *kya kya committed hai* | `paisa_report` `commitments` | the **Commitments card** (below) |
| *rent 8,421 har mahine add karo* | `manage_commitment` name, amount, repeats | confirm card; `repeats` guessed → amber |
| *EMI 10k, 5 tarikh ko, is mahine se* | `manage_commitment` + due_day | confirm card |
| *is mahine ka rent 7,000 hai* | `manage_commitment` amount | receipt, limit moves |
| *gym is mahine skip* | `manage_commitment` skip | receipt; *skip* is undone by *Unskip* |
| *gym band kar diya* | `manage_commitment` repeats=false | asks *is mahine ka bhi hata doon?* if unpaid |
| *ghar wala hata do* | `manage_commitment` delete | receipt, struck through; no Undo |
| *wo 8,421 rent wala payment rent me count karo* | `manage_commitment` pay_with | receipt |
| *rent 8,421 de diya* | `log_payment` | receipt; links on its own |

`manage_commitment` is one tool, the shape of `manage_habit`: a name alone
makes one; `commitment_id` — a name or an id — picks one to change. Reads stay
on `paisa_report`, whose `commitments` field gains `id`, `due_day`, `repeats`,
`skipped`, `amount_source` and the month. A name that matches nothing returns
what *does* exist, so the reply has somewhere to go; a name that matches two
returns both and the model asks.

**The tool count.** Twenty-six on 2026-09-27, with the ceiling raised on purpose
(`agent-tools.md`). This makes **twenty-seven**, and the reason is the one that
justified `manage_habit`: the money side's only way to change what is owed was
a flag on a payment that already happened, so *"is mahine ka rent kam hai"* had
no path at all. `tests/test_agent.py` holds the number; raise it with this.

**Agent rules** (`prompt.py`): to change what is owed, call `manage_commitment`
— never `correct_payment`, which edits a payment. *Kya committed hai* is
`paisa_report` `commitments`, never `fixed`: unchanged, and still the rule that
stops the opposite-set answer.

### The Commitments card

A typed card for the `commitments` read: the same lines as the page, each with
the ⋮, every row holding the commitment's **id** (not a copy), so an edit or a
delete updates every card that showed it. The agent's line above is computed
from the live rows when drawn — *₹61,421 owed across 5 lines; 1 skipped* — and
`no commitments yet` is said as that, never as ₹0.

### Web

The chat card, and **Your data → Commitments**, the same list and sheet. The
web keeps the deck and gets no widget.

### Your day

The morning brief reads the live commitments. A line with a `due_day` inside
the next three days (this month's, owed above 0, not skipped) adds one line to
*Your day*: *Rent due Friday · EMI due Sunday*, naming at most two and saying
how many more. Worked out from the rows when the brief runs, silent when
nothing is due, and the figure on its page is live like the rest of Your day.
No due day set, nothing said: a line the person never dated is not announced.

### The payment tray

*Fixed* and *Repeat* leave the tray. In their place, **Counts toward…** and
**Not a commitment** on an expense, and **Make this a commitment** on one with
none — which opens the sheet pre-filled from the payment (name, category,
amount) with *repeats* the person's choice.

## Rules and edge cases

| Case | What happens |
|---|---|
| **Part payment** | owed is the remainder; the line shows `₹2,000 · ₹50 paid` |
| **Over-payment** | ₹9,000 against ₹7,948: owed 0, the line shows `+₹1,052`. The payment is **not split** — a ledger row stays one fact. The extra is simply not discretionary spend |
| **Payment deleted** | the commitment owes it again, immediately |
| **Payment's category edited** | the link stays; only auto-linking reads category |
| **Amount edited after paying** | owed is recomputed live; `amount_source` becomes `stated` |
| **Delete a commitment** | its payments unlink and become ordinary spending, so *spent* rises — said in the receipt. The ledger is never touched |
| **Skip, then pay anyway** | the payment is ordinary spending; *Unskip* first to link it |
| **Skipped line** | owed 0, shown under *Skipped*, **not carried**, and rolls next month if `repeats` |
| **Unpaid at month end** | its remainder is carried as *from September*. A carried line the user no longer owes is one *Delete* away |
| **A line unpaid for three months** | still carried, still labelled with its month. The label, not a nag, is what keeps it honest |
| **Two commitments, one category** | FIFO by month then due day; a payment's own words win. Total owed is the same either way |
| **Rolled amount** | amber dot until stated or paid; paid-last-month beats expected-last-month |
| **First month of a new commitment** | exists from the day it is made; due day only orders it |
| **Due day 31 in February** | the 28th (29th) |
| **A commitment made for a past month** | refused: past months are read-only |
| **Zero or negative amount** | 422. A line owing nothing is *skip*, not ₹0 |
| **Borrowings** | live, read-only, from udhaar; a repaid one drops off by itself |
| **Two taps, two devices** | edits are `PATCH`es on the row and last write wins; rolling is idempotent |
| **Before salary** | limit unknown (`—`), never a red number |
| **Rolling raced by two reads** | a unique key on `carried_from_id` / the rolled-from row makes the second insert a no-op |
| **An account with nothing flagged** | no commitments, owed ₹0, the page says *No commitments yet* with the add button. Not a zero card |

## Data

```sql
CREATE TABLE commitments (
  id               TEXT PRIMARY KEY,
  user_id          TEXT NOT NULL REFERENCES users(id),
  name             TEXT NOT NULL,
  category         TEXT NOT NULL,
  amount_paise     BIGINT NOT NULL CHECK (amount_paise > 0),
  amount_source    TEXT NOT NULL DEFAULT 'stated',   -- stated | rolled
  local_month      DATE NOT NULL,                    -- first of the month
  due_day          SMALLINT CHECK (due_day BETWEEN 1 AND 31),
  repeats          BOOLEAN NOT NULL DEFAULT false,
  skipped_at       TIMESTAMPTZ,
  rolled_from_id   TEXT REFERENCES commitments(id),  -- the repeating line this was copied from
  carried_from_id  TEXT REFERENCES commitments(id),  -- the line whose remainder this is
  created_at, updated_at, deleted_at
);
CREATE UNIQUE INDEX uq_commitments_rolled  ON commitments (rolled_from_id)  WHERE rolled_from_id  IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX uq_commitments_carried ON commitments (carried_from_id) WHERE carried_from_id IS NOT NULL AND deleted_at IS NULL;

ALTER TABLE transactions ADD COLUMN commitment_id TEXT REFERENCES commitments(id);
```

A payment's link has a second column, `transactions.commitment_inferred`: true
when the link was guessed from the category, false once the user has moved or
confirmed it — the amber dot. On the wire a payment carries `commitment_id` and
`commitment_inferred`; `fixed` and `repeats` are gone from it. The two old
columns stay in the table for one release, read by nothing, then drop.

`categories.is_bill` from the old draft is **not** built: with commitments as
rows the category no longer has to carry the meaning, and a *Bills* filter is
"payments with a `commitment_id`".

| Route | |
|---|---|
| `GET /commitments?month=` | the page's list: lines with expected, paid, owed, status; plus the live borrowing lines. Rolls the current month on first read |
| `POST /commitments` | make one. Current month only |
| `PATCH /commitments/{id}` | amount, name, category, due day, `repeats`, `skipped` (a switch, like `PATCH /nudges`) |
| `DELETE /commitments/{id}` | soft; payments unlink |
| `PATCH /transactions/{id}` | gains `commitment_id` (set, or `null` for *Not a commitment*) |
| `GET /paisa/summary?fields=commitments,limit_today` | reads the table; the lines add up to `owed_paise` exactly, and a test asserts it |

Someone else's row, or a deleted one, is a 404. `fixed_paid_paise` stays in the
summary as *the sum of linked payments* for the pale arc.

### Migration

*(Built as `alembic/versions/f3a8c5d21b69_commitments.py`; its `backfill()` is
importable and the test runs it against a ledger seeded the old way, since a
fresh test database has nothing to migrate.)*

For the current month and the one before — the only two the limit ever reads —
and in one pass, so **no number moves except the one that was wrong**:

1. Every category with a `repeats` row last month becomes a commitment for
   *that* month (`repeats = true`, `amount` = the repeats sum), and one for this
   month, `rolled`.
2. Every `fixed` payment links to the commitment of its category and month, or,
   where there is none, becomes a **settled one-off** commitment so *spent*
   keeps its meaning.
3. `fixed` and `repeats` stop being read anywhere. The columns drop in a later
   migration, after a release with nothing reading them.

The migration cannot know which flagged categories were obligations, so it
keeps them all as `rolled` lines (amber) and **the person prunes**. On the
live ledger that was Health/Diet — everyday spending flagged *Repeat* once,
reserving ₹2,000 a month — and it was deleted on 2026-10-10; what remained
(Ghar, EMI, Rent, Subscriptions, ₹61,421) is exactly what the old arithmetic
said was owed. One number does change by rule rather than by
choice — a part payment now leaves its remainder owed instead of clearing the
line — and a test pins it as the only delta.

## Definition of done

`backend/tests/test_commitments.py`, per the project rule.

| # | Claim | How |
|---|---|---|
| 1 | Make, list, patch, skip, delete — each via the routes; a stranger's row is a 404 | test |
| 2 | `owed` = max(0, amount − Σ linked payments), 0 when skipped; recomputed live after a payment is added, edited or deleted | test |
| 3 | A payment links to the only open commitment of its category; with two, the oldest month first; with none, it stays ordinary spending | test |
| 4 | A payment's own words beat FIFO; `commitment_id` can be set and cleared | test |
| 5 | Rolling copies `repeats` lines once, with paid-else-expected amount, `amount_source = rolled`, twice-read still once | test |
| 6 | An unpaid remainder carries as its own line; a skipped one does not | test |
| 7 | Past months are read-only; a future month cannot be made | test |
| 8 | The limit subtracts live `Σ owed`, may be negative, and is `null` before any income this month | test |
| 9 | The `commitments` lines add up to `owed_paise` exactly | test |
| 10 | Deleting a commitment unlinks its payments and leaves the ledger untouched | test |
| 11 | Borrowing lines are live, read-only and drop off once repaid | test |
| 12 | The migration moves no limit except by the part-payment remainder | test |
| 13 | `manage_commitment` makes, edits, skips, deletes and links; an unknown name returns what exists; two matches return both | test |
| 14 | `correct_payment` no longer takes `fixed` or `repeats` | test |
| 15 | `n2n_eval` has the nine chat sentences above, each with the tool and the row it must produce | **not yet** — the eval is chat-quality's, and spends real tokens |
| 16 | The page, the sheet, the Money widget link and the payment tray on the emulator | **by hand** — seen 2026-10-10: the negative limit in red, the page and its header chain, add / edit / skip / delete moving the limit each time, *Counts toward…*, the live chat card. **Not yet seen:** an amber guessed link on a real payment, *Make this a commitment*, past-month navigation, the empty state, the Your day due-soon panel, *Salary not in yet* |
| 17 | The chat card and Your data on the web | **by hand** — built, typechecks and builds, **not yet seen running** (the preview needs a signed-in session) |
| 18 | Your day names commitments due within three days, live, and says nothing when none is | test |
| 19 | An auto-link is flagged inferred; moving or confirming it clears the flag | test |

Rows 1–14, 18 and 19 are green in `backend/tests/test_commitments.py`; 12 runs
the migration's own backfill function. 16 and 17 are the agents' hand
verification on the emulator and in the browser, recorded when done.

## Chat sentences to try by hand

Each is a sentence to type in the composer, the tool it should call and what
should come back. Use a throwaway name (*Test gym*) so the real lines stay
put, and delete it at the end. These are the cases `n2n_eval` should hold
(row 15); until then they are run by hand.

| # | Say | Expect |
|---|---|---|
| 1 | *kya kya committed hai* | `paisa_report` `commitments` → the live **Commitments** card; the sentence gives the total, never the list |
| 2 | *is mahine kitna pay karna baaki hai* | the same read, a total in the sentence |
| 3 | *kitna bacha hai* | `balance`, **not** commitments — a check that the two are not confused |
| 4 | *test gym 1500 har mahine add karo, category Subscriptions* | `manage_commitment` made; confirm card — Repeats *every month*, Category not guessed |
| 5 | *insurance 12000 sirf ek baar ka commitment, 20 tarikh ko* | made with `repeats = false`, due the 20th; Repeats *this month only* |
| 6 | *EMI 8000 add karo* (an EMI already exists) | asks whether to change that one or add a second — no write, never a silent duplicate |
| 7 | *ek commitment add karo* | asks the name and the amount — no write |
| 8 | *test gym 1800 kar do* | changed; owed moves to ₹1,800 |
| 9 | *test gym ki due date 5 kar do* | changed; the line gains *due 5th* |
| 10 | *test gym is mahine skip* | skipped; owed 0; the page shows it under Skipped |
| 11 | *test gym wapas on karo* | unskipped |
| 12 | *test gym 1800 de diya* | `log_payment`; it links itself — owed falls to 0, the link is a marked guess |
| 13 | *wo 500 wala payment test gym me count karo* | `manage_commitment` `pay_with` → linked, link confirmed |
| 14 | *wo payment commitment nahi hai* | `correct_payment` with `commitment_id = null` → ordinary spending again |
| 15 | *test gym ab har mahine nahi aata* | `repeats = false`; if still unpaid this month it asks *is mahine ka bhi hata doon?* |
| 16 | *test gym hata do* | deleted; the card is struck through, its payments now count as spending |
| 17 | two lines *Test loan A* and *Test loan B*, then *test loan ka amount 5000 kar do* | asks which one — both named |
| 18 | *nonesuch commitment hata do* | says there is none and names what exists |
| 19 | *grocery pe 500 kharcha hua* | a payment — **never** a commitment |
| 20 | *health 2000 har mahine commitment add karo* | refused: Health/Diet is everyday spending, not an obligation; asks what the bill really is (the Commitments page can still add anything) |
| 21 | *pichhle mahine ka rent edit karo* | read as a payment edit (last month's rent payment) and asks what to change; a past month's *commitment* is never edited |

**Run 2026-10-10** in the app on the emulator against the real model: all 21
pass. Two failed first, and were fixed: **6** made a second EMI line beside the
real ₹10,000 one, and **20** made a Health/Diet commitment — and when given an
override flag the model set it unasked, so the guard has no bypass in chat
(`test_the_agent_does_not_make_a_second_line…`,
`test_everyday_spending_is_not_a_commitment_from_chat`). Notes: the agent filed
a gym payment under Subscriptions and linked it by itself; *"Loans"* is not one
of the app's categories, so it asked for EMI or Udhaar instead; it also copies
the user's own sentence into a payment's `note` when it re-links one (13, 14).

After each write, open the Commitments page (or the Money report's **Commits**
tab) and check the owed total and the daily limit moved by the same amount.

## Staging

Built 2026-10-10 in this order: the backend (done, tested), then the phone and
the web against it. One stage, because two sources of truth for one month is the bug
this replaces (the old draft's open question, answered):

1. **Backend**: the table, the migration, rolling, linking, the limit reading
   the table, the routes, `manage_commitment`, the prompt rule, the tests.
   Your day's due-soon line is part of this stage.
2. **Android**: the page and sheet, the Money widget links, the payment tray,
   the Commitments card.
3. **Web**: the card and Your data.
4. **The drop** of `fixed` and `repeats`, one release later.

## Decided against

- **Dropping the subtraction** and showing commitments as information only.
  It is the option the complaint pointed at, and it makes the limit unsafe: on
  the 13th with rent due on the 14th it would invite spending the rent. Visible
  and editable solves the real problem; unsafe solves nothing.
- **Keeping `fixed` as a label only.** The ledger would carry a per-row flag
  meaning the same as a link, and they would disagree within a month.
- **A standing template plus per-month overrides.** Fewer rows, two tables, and
  *"is mahine ka rent kam hai"* becomes an exception record instead of an edit.
  One row per month per commitment is more rows and less machinery.
- **Hand-settling without a payment.** The money stays in the pool and the
  limit rises by what has left the bank. Log the payment; or skip.
- **Splitting an over-payment** across a commitment and ordinary spending. A
  row is one fact; the extra shows on the line.
- **Storing borrowings as commitment rows.** A copy of a live debt is a second
  place for it to be wrong.
- **Generating a month's rows on a schedule.** Nothing here runs on a clock the
  user cannot see; it rolls on first read, idempotently.
- **`categories.is_bill`.** See § Data.
- **A compatibility shim for the old flags.** The server and the phone ship
  together and nothing has been released; a shim is a second path to keep true.
- **A new Home widget.** Home is five widgets; this is Money's detail.
- **Icons instead of the label row** on the old three-number card — still true;
  each column already carries a word.

## Open

- **A notification when a commitment is due.** Moved to the notification
  spec's review (`TODO.md` § Notifications): the phone's channels, quiet hours
  and the Reminder card are decided there, and a due commitment is one more
  thing that spec must account for.
