# People — the humans among your counterparties

> Shipped 2026-09-05. Feeds *Your data → People*, gives `spec/udhaar.md` §3.8
> (per-person history) its first home, and gives the agent the row it will write
> its guess about a payee onto.

## The problem

Eighteen counterparties hold real money against them, and the ledger already
knows more about each than the app shows: Dost 1 was lent ₹7,000 on 2 Aug and
paid it back on the 12th; Dost 2 was lent ₹4,000 in June and has not. Nothing
on screen says either. And the rows cannot tell a person from a paan shop —
Mohan Lal and Badi sister sit in the same list, distinguished only by a flag
that flips when money comes *back*.

That last one is not cosmetic. It is what makes a payment unreadable at the
moment it arrives: a new payee is a name and an amount, and the app has nowhere
to put what it works out about them.

## What it does

- **No new table, and nothing on `transactions`.** A person you pay is already a
  row in `counterparties`; every transaction points at it with
  `counterparty_id`, and a write that carries a name creates the row first
  (`person()` in the write path). What we know about someone is a fact about
  *them*, so it is stored once on their row — not copied onto each of their
  twelve payments, where twelve copies could disagree.
- Three columns join the row: **`kind`** (person · shop · service), a
  **`relation`** in your words (dost, badi sister, papa, landlord), and a
  **`note`**.
- ***Your data → People*** lists rows with `kind = 'person'`. Each row answers,
  from the ledger alone: sent, received, **still out**, and **typical days to
  return** — the average gap between a lending and its first repayment.
- **A tap files a row.** Later the agent proposes a `kind` and the tap becomes a
  confirmation, but the proposal is always displayed marked `· andaaza` — as an
  inferred memory is on the profile — and correcting it is what sticks.

## Data

```sql
ALTER TABLE counterparties
  ADD COLUMN kind         TEXT CHECK (kind IN ('person','shop','service')),  -- NULL = nothing known
  ADD COLUMN relation     TEXT,
  ADD COLUMN note         TEXT,
  ADD COLUMN source       TEXT CHECK (source IN ('user','agent','contacts')),
  ADD COLUMN confirmed_at TIMESTAMPTZ;   -- last time you said "haan, sahi hai"
```

`source` and `confirmed_at` are the same pair the `memories` table already
carries, with the same meaning and the same display rule: **inferred is marked,
confirmed is not.** Both are nullable — unlike on `memories`, where a row always
has a writer. A counterparty is born from a payment, so a default of `'user'`
would have eleven rows claiming the user said something they never said. They
are not bookkeeping —

- `confirmed_at IS NULL` is what puts `· andaaza` on screen. Without it a guess
  and a fact look identical, which is the one thing *Honesty over completeness*
  forbids.
- `source` is what stops a weak guess overwriting a strong one. A relation read
  off your contacts ("Mummy") must not be replaced by a model's hunch, and the
  agent must not re-guess a row you have already answered.

One flag covers all three fields on purpose: you confirm a *row* — "yes, that's
my sister" — in one gesture, not three.

**Seed rule for the imported rows:** `is_peer = true` → `kind = 'person'`,
`source = 'agent'`, unconfirmed (money came back from them; shops do not do
that). Everything else stays `NULL` and shows under **Unsorted**. On the
imported ledger that is six of seventeen.

Per-person numbers are **never stored**; the same rule as tried-counts on dishes
and stock in the pantry:

```sql
sent      = SUM(amount) WHERE direction = 'debit'
received  = SUM(amount) WHERE direction = 'credit'
still_out = Σ lent − Σ repayments settling those lendings   (the Pending arithmetic, per person)
days      = AVG(first repayment.local_day − lending.local_day)  over settled lendings
```

Today that gives: Dost 1, Dost (1,000 wala) and Badi sister at **10 days**;
Dost 2 at **₹4,000 still out**, no average because nothing has come back.

## Scope — what is built now, and what waits

**Now, and it is the whole feature:** the columns, the derived numbers, the
People section, and the tap that files a row. Thirteen rows to classify once
each, by hand, in about a minute. That is not a stopgap — a tap is the correct
primary path for a one-person app, and every guess below only exists to save
that tap on payees you have not seen yet.

**Phase 3, with the agent:** the guessing. **Android:** the contacts match.
Neither changes a column; both write to the same five.

## What the agent will guess from, and what it cannot

**The name is not a signal.** In the real product the payee name is read off a
notification, and a notification renders your sister and the paan-wala
identically — `MANORAMA DEVI` either way. The mixed-case Hinglish names in
today's data (`Badi sister`, `Dost 1 (naam?)`) are artifacts of a hand-typed
import; nothing that arrives through capture will ever look like that. Any
classifier built on how the name is spelled would score well on this data and
fail on the first real payment.

What survives is what the notification carries reliably — **the amount and the
direction**:

1. **Money ever came back.** Already the `is_peer` rule, already stored, and
   still the only signal that is never wrong. Shops do not repay.
2. **A round thousand.** Every person-payment in the ledger is exactly ₹1,000,
   ₹2,000, ₹4,000 or ₹7,000. No shop payment is round, and none exceeds ₹570.
   You hand a friend a round number; a bill is whatever the bill is.
3. **Rhythm.** Four payments of ₹44–98 to one payee across a week is a shop
   whatever its name says.

None of these is strong enough to write a `relation` — they can propose
`kind = 'person'`, marked, and that is all. `relation` comes from you, or from
contacts.

### When the agent is allowed to speak

A row is created on **every** payment — it has to be, it is the key the next
notification matches against, and creating it is silent and free. The threshold
is not about whether the row exists. It is about **when the agent proposes
something about it**, because a suggestion on all ninety-two payments is four a
day and the app becomes a nag.

| Trigger | Wait |
|---|---|
| Money came back (`is_peer`) | **None.** One event settles it — shops do not repay |
| Paid on **three or more separate days** | Then, and not before |

Counted in **days, not payments**. Mohan Lal is four payments across three
days; two chais on one afternoon is one visit, and counting them twice would
promote a one-off into a habit.

On the imported ledger that fires for exactly one row in twenty-four days. That
is quieter than it sounds and it is the right way round: a suggestion you did
not want costs attention, a suggestion never made costs nothing — Unsorted is
always there and a tap is free.

**An unapproved suggestion is not withdrawn.** It stays on the row, unconfirmed
and marked `· andaaza`, exactly as it looked before you saw it. Silence is not
rejection, and the agent does not ask twice.

**A payee it has seen** is read, not re-guessed: `kind`, `relation` and
`default_category` become the suggestion on the new payment, and `still_out`
and `typical days` are what let the agent say *"Dost 2 — ₹4,000 still out since
June"* instead of a name and a number.

## Contacts — the match is on the number, not the name

The obvious version does not work. UPI shows `MANORAMA DEVI`; your phone book
says `Didi`. Comparing those two strings finds nothing, and fuzzy-matching them
would be worse than nothing — it would silently pair the wrong people.

The join has to be the **phone number**. A UPI ID is frequently the number
itself (`9810012345@ybl`, `9810012345@paytm`), and where it is, the chain is
exact and needs no model at all:

```
notification → VPA 9810012345@ybl → 9810012345 → contact "Didi" → relation
```

Where the VPA is a handle instead (`manorama.devi@okhdfcbank`), there is no
number to match on and the row stays unguessed until you tap it. That is the
honest outcome, not a gap to paper over with name similarity.

**The open question is whether we get the VPA at all.** GPay and PhonePe
notifications often show only *"You paid ₹40 to MANORAMA DEVI"* — the ID lives
in the app, not the notification. The RBI Account Aggregator feed, already the
sanctioned capture path in CLAUDE.md, carries the beneficiary handle properly.
Which surface supplies it is settled when capture is built, not here.

**The column that implies:** `counterparties.vpa TEXT`, the real identity of a
payee, with `raw_name` demoted to a label. Not migrated now — nothing can write
it — but written down because it also retires
`UNIQUE (user_id, raw_name)`: two different Manoramas are one row under that
constraint, and a payee whose bank changes how it renders their name forks into
two. Both are real bugs that arrive with real capture, and both are fixed by
the same one-line migration.

**Privacy rules, fixed now** so the Android build cannot drift: the contact list
is never stored and never leaves the device; only payees are matched, never the
whole book; permission is asked at a payment with the reason on screen, not at
install; refusing it costs a guess and nothing else. `READ_CONTACTS` is not in
the settled *no* list with SMS and call logs — Play Store permits it with a
disclosure.

## API

```
GET    /people                → counterparties with the four derived numbers; ?kind= filters, no kind = all
POST   /counterparties        → someone the ledger has never seen; born source='user', confirmed
PATCH  /counterparties/{id}   → kind, relation, note, display_name, default_category
                                (both writes stamp source='user' and confirmed_at)
```

Almost every counterparty is still born from a payment, and that stays the
normal path. `POST` is for the row that exists before the money does — cash you
owe, a friend you are about to lend to, the state `sunny` is already in with
zero transactions. A duplicate `raw_name` is a **409**: two rows for one name
and the next notification cannot say which it belongs to.

## Rules

- **Unsorted never nags.** No badge, no count, nothing to clear. Classifying is a
  one-time pass over thirteen rows and then a trickle: most new payees are shops,
  and a shop with no `kind` breaks nothing — the ledger, the daily limit and the
  report never ask. The rows that matter announce themselves, because `is_peer`
  fires on its own the first time money comes back.
- **The app never guesses silently; the agent guesses out loud.** Every
  unconfirmed value carries `· andaaza` and one tap fixes it. An unmarked wrong
  relation is worse than an empty one.
- **`is_peer` stays derived-by-event**, not by kind. A shop that ever refunds
  you becomes a peer by the existing rule, and that is correct: money came back.
  `kind` is what the row *is*; `is_peer` is what the ledger *saw*.
- **`raw_name` is never edited.** It is the key the next notification matches
  on. Everything the user says goes to `display_name`, `relation` and `note`.
- **68 of 92 transactions have no counterparty.** They were typed by hand
  without a payee. They are not wrong and are not backfilled; a person appears
  in People when a row names them.
- **Merging two spellings** (`sunny`, `sunnny` — both peers, both with zero
  transactions) is a later decision. The raw name is the match key, so a merge
  is a fork of that problem, not a rename.

## Decided against

| Option | Why not |
|---|---|
| `kind` / `relation` on `transactions` | A fact about a person copied onto every payment to them; twelve rows that can disagree, and a correction that has to hit all twelve |
| A separate `people` table | One person seen two ways; every join and every count would exist twice |
| Guessing `kind` from the payee name at all | A notification renders your sister and the paan-wala identically. Both what the name *means* (Mohan Lal is a paan shop — `spec/udhaar.md` §4.3) and how it is *spelled* fail; the mixed-case names in today's data are import artifacts that capture will never produce |
| Fuzzy-matching the UPI name to a contact name | `MANORAMA DEVI` against `Didi` finds nothing, and tuned loose enough to match, it pairs the wrong people silently |
| Storing sent/received/out on the row | Drifts the first time a transaction is deleted; the ledger already knows |
| A confidence score on the guess | `confirmed_at` answers the only question the UI asks — mark it or not. A number nobody can act on is decoration |
| ~~A POST /people form~~ | **Reversed 2026-09-06.** The rule that forms are what this product avoids is about *logging* — you do not fill a form to record a meal. *Your data* is the management surface, where direct editing is right and every other section already has an add row. The cost is a twin: a hand-typed *Wasim* will not match `MOHD WASIM` later, which is the merge problem `sunny` / `sunnny` already pose |
| Pills for `kind` | They were the same shape and size as the tabs above the list, so a field read as navigation. A dropdown, styled like the other four fields, says *form* |
| A short add form | Adding and editing write the same five columns, so they render the same fields. A cut-down add form just means opening the row again to finish it |
| Saving the kind on its own tap | It re-filed the row into another tab mid-edit and stranded whatever was still being typed. One Save, and the row moves once |
| An editable `raw_name` | It is the match key. `display_name` is the rename, and the editor shows the raw name read-only with that reason under it |
| Instant save on the text fields | Typing needs a commit; a chip is a single tap and files the row immediately. A chip tap sends the typed fields along with it, so nothing in the boxes is ever dropped |

## Definition of done

| Check | Expected |
|---|---|
| Migration | five columns on `counterparties`; the five `is_peer` rows read `person` / `agent` / unconfirmed, the rest `NULL` |
| `GET /people` | 17 rows; Dost 1 shows sent 7,000 · received 7,000 · out 0 · 10 days; Dost 2 shows out 4,000, no days |
| Your data → People | six under People marked `· andaaza` (the migration's guess), eleven under Unsorted |
| Tap Mohan Lal → *shop* | filed; `source='user'`, `confirmed_at` set, the mark gone; Shops 0→1, Unsorted 11→10 |
| ⋮ → relation *badi sister* | the row says so; `GET /people` returns it; a later agent pass leaves it alone |
| Scope | no guessing built — the migration's `is_peer` inference is the only inferred value in this feature |
| Delete a transaction that repaid Dost 1 | out becomes 7,000, days becomes none — nothing to update |
| Amount column | every number carries its word — *still out* · *you owe* · *sent* — because colour alone cannot separate ₹4,000 owed from ₹2,000 spent |
| The editor | five labelled fields — *What is this* (a dropdown) · *What you call them* · *Relation* · *Usual category* · *Note* — and `raw_name` read-only with why. The unlabelled pill version got a sister filed as a shop |
| Add and edit | the same five fields, from one component. Add puts `Name` on top: the match key, set exactly once |
| One Save | changing the kind and typing a relation is a single write, and the row re-files itself once |
| One editor at a time | opening *Add someone* closes an expanded row and vice versa — two panels put two identical chip rows on screen with no way to tell which a tap belongs to |
| *+ Add someone* | name required, duplicate refused with 409, all five fields stored, the row appears in the right tab |
| Money coming back | said only when `received > 0`. `is_peer` was hand-set on the imported rows, so trusting it told Dost 2 his money had come back when nothing had |
| Tests | `backend/tests/test_people.py` — 17 tests, green |
