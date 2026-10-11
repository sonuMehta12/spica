# Ledger writes

> Built and verified — 22 API checks green, and the headline held in the browser:
> tap Commute, ₹3,400 → ₹3,530, reload, still ₹3,530.
> Reconciles `spec/api.md`'s write sketch with the schema actually built in
> `spec/done/{paisa,diet,work}-data-model.md`, which came later and overruled
> parts of it.

## Scope

**In:** creating, correcting and deleting ledger rows from the app — money,
meals, habit logs, tasks — and what the server derives when they land.
**Out:** the offline queue and `POST /events` (Android, with local SQLite),
notification capture (phase 6), and the chat endpoint (phase 3).

## What `api.md` got wrong, and why

That spec was written before the data model existed. Four of its rules are now
contradicted by built code, and the spec is the thing that is out of date:

| `api.md` said | Actually built | Why |
|---|---|---|
| `txnId = hash(package+amount+payee+minute)` | ULID `id` **plus** a separate `dedupe_key` | Hash-as-id binds identity to the dedupe rule, so changing the rule breaks every reference |
| `amount` in rupees | `amount_paise` | Float rupees drift under repeated summing |
| `motionState`, `locationHash` on the row | `predictions.signals` | A signal is what the model saw, not a fact about the payment |
| `POST /workouts` | `POST /habit-logs` | Workouts became one habit among several |

This spec supersedes those four points; the rest of `api.md` stands.

## The contracts

Rows go in the **same wire shape `/deck` returns** — snake_case, ISO dates,
integer paise, `NUMERIC` as a string. One adapter serves both directions, and
anything the client omits stays NULL rather than being invented.

Paths are the words a person would say: `/transactions`, not `/tx`. The
abbreviation is finance-code habit and fails the no-jargon rule.

**`user_id` is never accepted from the client.** Every write takes it from the
auth seam (`app/auth.py`), so a request cannot write into someone else's rows
even by accident.

Every write returns the **stored row**, so the client never has to guess what
the server made of its input.

### `POST /transactions`

```jsonc
// request
{
  "id": "01M13VDZ1E9XBTNM3Q880GTDMX",  // ULID, made on the device
  "occurred_at": "2026-08-28T14:22:09Z",
  "local_day": "2026-08-28",           // the DEVICE's local day, never derived here
  "amount_paise": 9800,
  "direction": "debit",                // debit | credit
  "kind": "expense",                   // expense|income|lent|borrowed|repayment|transfer
  "category": "Health/Diet",
  "description": "chai aur samosa",
  "source": "manual",                  // manual | notification
  // optional, all default NULL
  "note": null, "tags": [], "method": "cash", "counterparty_name": "MOHAN LAL",
  "confidence": 1.0, "settles_id": null, "dedupe_key": null
}
// 201 → the stored row, in /deck's TransactionOut shape
// 200 → the EXISTING row, if this id was already written — the body of the
//       repeat is ignored. A retry is a retry, not an edit; edits go to PATCH.
```

### `POST /meals`

```jsonc
{
  "id": "01M…", "occurred_at": "2026-08-28T13:10:00Z", "local_day": "2026-08-28",
  "meal_type": "Lunch",                // free text — 'Grazing' is a real value
  "dish": "Dal bhaat",
  "kcal": 615, "protein_g": "20.0", "carbs_g": "95.0", "fat_g": "15.0",
  "source": "manual",                  // manual | photo
  // optional
  "recipe_id": null,                   // set it and the pantry is spent — see below
  "ingredients": null, "cooked_home": true, "note": null, "tags": [],
  "confidence": 1.0
}
// 201 → { "meal": MealOut, "pantry_moves": [PantryMoveOut] }
```

The response carries the moves it wrote, so the card can show the pantry
dropping without a refetch.

### `POST /habit-logs`

```jsonc
{
  "id": "01M…", "habit_id": "habit-workout",
  "occurred_at": "2026-08-28T07:00:00Z", "local_day": "2026-08-28",
  "amount": 45,                        // null = it happened, that is all
  "note": "Workout B (back)", "source": "manual"
}
// 201 → HabitLogOut
```

### `POST /tasks` · `PATCH /tasks/{id}`

```jsonc
// POST — everything except title and source is optional
{ "id": "a7f2", "title": "Fix the retry flow", "source": "self",
  "status": "open", "due": "2026-09-05", "priority": 1, "labels": ["work"],
  "project_id": "novacart", "doc_ref": null, "blocked_by": null }

// PATCH — only the fields being changed
{ "status": "done" }
// 200 → TaskOut, with done_at stamped server-side
```

### `POST /pantry-moves`

For stock arriving or a correction the user states — consumption is written by
`POST /meals`, not by hand.

```jsonc
{ "id": "01M…", "food_id": "food-tofu", "local_day": "2026-08-28",
  "occurred_at": "2026-08-28T18:00:00Z",
  "quantity_g": 400,                   // signed: negative for waste or a correction
  "kind": "purchase",                  // purchase|opening|consumption|correction|waste
  "note": null }
```

### `PATCH /transactions/{id}` · `/meals/{id}` · `/habit-logs/{id}` · `/pantry-moves/{id}`

Fix a wrong row. Send **only the fields that change**; anything absent is left
alone, which is different from sending `null` (that clears it).

```jsonc
// request
{ "amount_paise": 43000, "category": "Khana/Grocery" }
// 200 → the updated row, in /deck's shape
```

Editable: everything the user typed or the agent guessed — amount, category,
description, note, tags, method, counterparty, macros, meal_type, dish, amount.
**Not editable:** `id`, `user_id`, `source`, `created_at`. Those are facts about
the row's origin, not about what happened.

Where a `predictions` row exists for the target, the patch also stamps
`actual_*` and `corrected_at` on it — see *Editing is editing*.

### `DELETE /transactions/{id}` · `/meals/{id}` · `/habit-logs/{id}` · `/tasks/{id}`

```
204, no body. Sets deleted_at; the row stays in the table.
```

### Errors

```jsonc
// 422 — the shape is wrong. FastAPI's own body, field-by-field.
// 404 — no such id, on correct / patch / delete.
// 409 — never used. A repeat POST is a 200, not a conflict.
```

## The client supplies the id

A ULID, generated on the device, sent with the write.

Three things fall out of it, which is why it beats a server-generated id:

- **Optimistic rendering is honest.** The row the card draws immediately has
  its final id, so nothing has to be swapped when the response lands.
- **Retry is idempotent for free.** `POST` of an existing id returns **200 with
  the existing row** — the rule `api.md` already set, now with an id that
  survives a rule change.
- **The offline queue later needs no id reconciliation.** Rows written on a
  plane already have their permanent identity.

`dedupe_key` stays what it is: NULL for hand-typed rows, set by capture. Two
₹40 chais on one day are two rows, and always were.

## Optimistic, but never silently

The prototype's logging feels instant because it is local, and that is the
premise working — *agent hi app hai* dies the moment logging shows a spinner.
So writes stay optimistic:

```
row lands on the card immediately, marked pending
     ↓
POST in the background
     ↓  ok            → pending cleared, nothing moves
     ↓  4xx / 5xx     → row STAYS, marked failed, with a retry
```

**A failed write must never roll the row back quietly.** Someone said they
spent ₹340; making that vanish because the network blinked is the app losing
data the user handed it. The row stays, visibly unsaved, and retries.

## Editing is editing

A wrong row gets **fixed in place** — `PATCH /transactions/{id}`, and the same for meals,
habit logs and pantry moves. No second row, no supersede dance.

An earlier draft of this spec said every correction must write a superseding
row to preserve the training signal. That was wrong, and the schema says so:
**`predictions` already holds the correction trail** — `actual_category`,
`actual_description`, `user_feedback`, `corrected_at`, with an index whose own
comment reads *the training set is exactly the corrected rows*. Putting a
second trail in the ledger duplicated a job that already had a home.

So one path, and the signal still lands:

```
PATCH /transactions/{id}  { "amount_paise": 43000 }
     ↓
row updated in place, updated_at bumped (sync sees it)
     ↓
if a predictions row exists for this transaction:
     actual_category / actual_description ← the new values
     corrected_at                        ← now
```

**A typo is not training data.** If nothing predicted the row — you typed it
yourself and meant ₹430 — there is no prediction to stamp and nothing is
learned, which is correct. The signal exists only where a guess was made.

**`supersedes_id` stays, for machines.** It is still right when a *new event*
replaces an earlier one — a captured payment arriving pending and settling at a
different amount. That is two facts about the world, not a person fixing a
number, and only the second reading is true.

## Editing before the write

The agent parses what you said, shows the row, you fix it, *then* it saves.
This needs **no endpoint** — the row has not been written, so it is composer
state until you accept it. Named here only so nobody builds an API for it.

## Tasks update in place — the one exception

`PATCH /tasks/{id}` for the done toggle. A task is **state**, not an event, and
`spec/done/work-data-model.md` already carries that exception. `done_at` is set
server-side when status becomes `done`, and **cleared** when it leaves `done` —
un-ticking a task must not leave a stale completion time behind. The card's
*stays visible today* behaviour derives from `done_at`.

## What the server derives on write

**A meal logged against a recipe spends the pantry.** `POST /meals` with a
`recipe_id` writes the `consumption` moves from `recipe_items`, in the same
database transaction, carrying the meal's id.

Server-side, not client-side, for two reasons: the rule lives with the data
(`spec/done/diet-data-model.md`), and putting it in the client means Android
reimplements it and the two drift.

**Only tracked foods are spent.** A consumption move is written for a recipe
item's food only if that food already has an inbound move (a purchase or an
opening). The diet model reads *no moves at all* as *present, amount unknown* —
the family's atta — and a lone `−40 g` against it would silently flip it into a
tracked row with a negative balance. Untracked staples stay untouched.

Nested recipes expand through `recipe_items.component_recipe_id`, multiplied by
`servings`: Ghar ka dinner spends two rotis' worth of atta.

**Deleting the meal takes its moves with it.** That is the whole reason the
moves carry `meal_log_id`, and it is what makes the pantry a sum that cannot
drift. The moves are soft-deleted alongside the meal, so sync sees both.

**Changing a meal's `recipe_id` rewrites its moves** — the old consumption
rows are soft-deleted and new ones written, in one transaction. Editing any
other field leaves the moves alone.

## Deletes are soft

`deleted_at`, never a row removed. Sync sees the removal, and *"per-item delete
is the user-facing control"* (`CLAUDE.md`) means the button is real — the row
stops existing for the user, which is what they asked for. Hard delete is a
separate, later decision about retention.

## Frontend changes

- `logPaisa` / `logDiet` gain a `pending` flag on the row and a POST; the maths
  files stay untouched, since a pending row is still a row
- `deleteRow` calls `DELETE`, keeps its optimistic removal, restores the row on
  failure with a message
- `toggleTodo` calls `PATCH`
- `editRow` (today: drops text back in the composer) becomes a `PATCH` once the
  composer can carry the id it is editing

## Definition of done

| Check | Expected |
|---|---|
| Log a chai, reload | it is still there |
| Log with the backend stopped | row stays, marked unsaved, retry works |
| POST the same id twice | 200 both times, one row |
| Edit a row | the row changes in place, `updated_at` bumps, no second row |
| Edit a row that had a prediction | `actual_*` and `corrected_at` stamped on the prediction |
| Edit with one field | only that field changes; the rest are untouched |
| Delete a row | gone from the deck, `deleted_at` set, still in the table |
| Log a meal with a recipe | pantry drops by the recipe's grams |
| Delete that meal | pantry goes back up |
| Tick a task, reload | still ticked, `done_at` set |
| Un-tick it | `done_at` is NULL again |
| Log a recipe meal whose food is an untracked staple | no move written for that food |
| POST the same id with a different body | 200, the original row, unchanged |
| Two ₹40 chais in one day | two rows |
