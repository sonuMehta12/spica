# The agent deletes, and can move a row to another day

> Status: shipped 2026-09-13
> Surface: backend, and one line of the confirm card

This overturns rule 6 of `spec/agent-tools.md` ("a tool never deletes") and the
matching bullet in `spec/agent.md`. Both are rewritten; this file is why.

## The problem

Two things the user asked for in ordinary words, and could not get:

> *"woh egg roll wala 180 ka entry galat hai, delete kar do"*
> *"egg roll ka 180 wala aaj ka nahi, kal ka tha"*

Neither worked, and the way they failed was worse than the failure.

**Delete was left out on purpose and the model was never told.** Rule 6 said
deleting is the user's gesture in the ledger, so there were nineteen tools and
none of them deleted, while `DELETE /transactions/{id}` and `DELETE /meals/{id}`
sat there working. The prompt never mentioned the rule. With no tool and no
explanation, the model invented one: *"money-log deletion feature abhi bhi
broken hai."* Nothing was broken.

**Moving a row to another day was a plain oversight.** `TransactionPatch` and
`MealPatch` both accept `local_day` and `occurred_at`, and the routes apply
them. The tool schemas handed the model a shorter field list that left both
out. A model cannot name a field it was not given.

**Blocked, it wrote its intentions into the ledger.** Every failed attempt
ended in the `note` column:

```
Rapido ₹160, 11 Sep — note: "User requested deletion: wrong Rapido log"
Egg roll ₹180      — note: "…local date 2026-08-27 hona chahiye; correction requested."
```

That breaks the *never store a sentence about the user's own data* rule in
CLAUDE.md, and it rots: the moment the row is deleted or moved, the note is a
lie sitting in the ledger. `note` is free text, so a blocked model treats it as
an escape hatch for anything it cannot do.

**Then the excuse became permanent.** Asked to *"remember this as bug"*, the
agent stored three `reference` memories, and `prompt.build()` injects every
memory into every system prompt. So the model opened each turn already
believing delete was broken, and said so with confidence. A missing capability
had hardened into an asserted fact about the product.

## What it does

**`delete_payment(transaction_id)` and `delete_meal(meal_id)`.** Two tools, not
one with a `kind` switch: one verb on one kind of thing is the shape the
forty-five-to-twenty merge settled on, and a payment and a meal are different
tables. Twenty-one tools now, against a ceiling of twenty-five.

Both soft-delete through the route that already exists, so every rule the route
holds still holds. A lending with repayments is still refused, and the refusal
reaches the model as data to explain rather than an exception. Deleting a meal
still unspends its lines, so whatever the plate took off the shelf goes back.

Each returns a `confirm` card in the new state `deleted`: lede struck through,
no tray. The card **stays on screen**. A row that vanished without a trace
leaves the user unsure whether anything happened.

**`correct_payment` and `correct_meal` gain `local_day`** (and `occurred_at`,
for the rare case where the time is also wrong).

**A day change moves the clock with it.** `local_day` and `occurred_at` are two
views of one moment; setting only the first leaves a row that claims Sunday and
happened on Friday, which every later query on `occurred_at` reads wrong. The
shift is *by the number of days moved*, never a date stamped onto the existing
value: `occurred_at` is UTC and `local_day` is the user's, so the two already
disagree either side of midnight IST. A 00:30 chai is the 21st locally and the
20th in UTC, and stamping the local date onto the UTC value would move that row
two days. A delta cannot, and the clock time survives untouched.

**Five new rules in the prompt**, each closing one of the failures above:

- A row id comes from a report's `rows`. Read first, then correct or delete.
  Never construct one. (The model had called `correct_payment` with the id
  `"egg-roll-180"`, which it made up.)
- Wrong value on a row is `correct_*`; a row that should not exist at all is
  `delete_*`. Both are soft, so do it when asked rather than sending them away.
- `note` is the user's own words about a row, never the agent's intentions or a
  record of what it could not do.
- You do not know what is broken. With no tool for something, say what you
  cannot do in one line and stop. Never blame a bug, never work around a
  missing tool by writing somewhere else.
- Memory is never about Cortex itself. Asked to remember a bug, say it belongs
  in the repo.

**`remember` refuses a bug report** and says why, so the model explains rather
than storing. The prompt rule is the real defence; the server check is a
backstop for the shape that already got through, and its phrases are
deliberately narrow — naming a part of Cortex, not any noun a screen also has.
*"Old laptop, the screen is broken"* is a fact about the person and must
survive, and a test says so.

## Rules and edge cases

- **Delete is not confirm-first.** The user said *delete kar do*; asking again
  is the form-filling this app exists to avoid. The struck card is the receipt,
  and the delete is soft.
- **Undo is not built.** A soft-deleted row cannot be restored through any
  route: `live_or_404` refuses it. Recovering one is a hand query today. An
  `Undo` chip on the struck card needs a restore endpoint — see *Open*.
- **Deleting the same row twice in one turn happens once.** `delete_` joins the
  runner's dedupe prefixes; the second call would 404 anyway.
- **An invented id returns "no such row"** from all four tools, as data.

## Decided against

- **Keeping rule 6.** Its reason — *a wrong write is a `PATCH`, and the
  correction is data* — is true of a wrong category or a wrong amount, where
  the `(estimated, actual)` pair is worth keeping. It is not true of *"I never
  ate this"*: there is no pair, only a row that should not exist. Forcing the
  user to the UI for that contradicts **agent hi app hai**. The narrower rule
  survives as a prompt rule: correct a wrong value, delete a wrong row.
- **One `delete_row(kind, id)` tool.** A `kind` switch across two tables is the
  hiding-tools-in-a-switch move the tool count was reduced *without*.
- **Asking before deleting.** Two taps for a reversible, soft, visible action.
- **A hard delete.** Never. Soft delete is what makes an unasked-for delete
  survivable.
- **Letting the model clear `note` itself to tidy up.** It would be undoing its
  own mess by writing again. The three polluted rows were cleaned by hand once.

## Verified

`backend/tests/test_agent_deletes.py` — thirteen tests: the day moves and takes
its clock; an explicit time is not overwritten; a row either side of midnight
moves exactly one day and not two; both correction tools offer `local_day`;
deleting a payment strikes its card and leaves it readable by id; deleting a
meal puts the food back on the shelf; a lending with repayments refuses; an
invented id is a refusal in all four tools; the same delete twice in one turn
happens once; a delete turn end to end; `remember` refuses four real bug
reports and still keeps a fact about a broken laptop screen.

Whole suite: 185 passing.

## Open

- **Restore.** No route un-deletes a row, so there is no `Undo` chip on the
  struck card. It is a small endpoint plus one tray action, and it is the
  natural next piece.
