# Chat cards

> Status: shipped 2026-09-13
> Surface: both — the card union on the wire, and how each card looks and acts

## The problem

The agent answers in two layers: prose it writes, and typed cards the runner
builds from the tools that actually ran. The prose is right. The cards are not
yet the product: a logged payment comes back as a four-line key/value block that
looks nothing like the same payment in `@paisa`, a meal suggestion comes back as
no card at all (the model names the dish in a sentence and the user retypes it
to log it), and fourteen of the nineteen tools return nothing but prose — a
saved person, a moved pantry item, a remembered fact, a changed target all
happen silently. Confidence is marked with a Hinglish word in a UI that is
otherwise English. There is no way to say *yes, that guess was right*, and there
is no way to act on a card without typing.

The user's own framing: **consistency.** A payment should look like a payment
wherever it appears, and a suggestion should be one tap from logged.

## What it does

Five kinds of card on the wire today: `agent`, `table`, `confirm`, `suggest`,
`ask`. This spec keeps the five, fills in the ones that are hollow, and gives
every card the same three affordances: a **number first**, a **⋮ tray** with
the same actions everywhere, and a **confidence dot** instead of a word.

### Cross-cutting rules

- **Copy is English.** Every label, action, lede and fallback string the UI or
  the runner produces is English: `Category`, `Confirm`, `Deleted`,
  `42 g protein left`, `Not recognised`. The agent's *prose* stays in whatever
  the user is speaking — the model already mirrors it. `· andaaza` as a UI
  string goes; the dot replaces it (below). `Paisa` and `udhaar` stay: they are
  names of things, not copy.
- **Confidence is a dot, not a word.** A field the agent worked out rather than
  was told carries a small amber dot (`color.amber`, 6 px) before the value.
  A field the user stated carries nothing. There is no green dot: certainty is
  the default and does not decorate itself.
- **Every card leads with a number** — the amount, the protein left, the count
  of rows. A card whose first line is a label is wrong.
- **One ⋮ tray.** `report/ItemList.tsx` and `messages/TableCard.tsx` already
  share one tray: row-specific actions first, then `Edit`, then `Delete`.
  Every card row in chat uses that tray. `Confirm` joins it as a row-specific
  action wherever the row has a guessed field. `Fixed` / `Repeat` stay
  paisa-only.
- **Live ids.** A card names rows by id and renders them from live data when
  the client holds the row. It never copies a number it could look up.
- **Tap logs; type explains.** Where a tap can only mean one thing — log this
  dish, accept this guess — it goes straight to the route, no model in the
  loop. The composer is for things that need interpreting.
- **A tap gets a receipt, not a message.** Its confirmation appears above the
  composer for about three seconds and goes, the way a payment app confirms a
  payment. Nothing joins the thread: the thread is for things that were said,
  the ledger holds the fact, and the tapped card reads `✓ Logged` from the
  ledger from then on.

### 1 · Ledger card — a payment looks like a payment

The `table` card already exists on both ends (`TableCard` in Python, `TableMsg`
+ `TableCard.tsx` in the client) and is never sent: `from_tool()` returns
nothing for reads, and `toChatMsg()` drops `table` from the wire. Both get
fixed, nothing new is designed.

**When the runner emits it:** a `paisa_report` or `diet_report` call that asked
for `rows` returns a `table` card carrying those row ids, after the prose. A
read that asked only for totals returns prose alone — the number belongs in the
agent's sentence.

**What it looks like:** the row layout `@paisa` has today, unchanged — date ·
name over category · amount · ⋮. The heading leads with the number the rows
add up to. Diet rows: `142 g protein · 4 meals`.

**Money coming in is not spending, and the card has to say so** (fixed
2026-09-13). The row was hardcoded to `−` in red, so a salary landing read as
the largest expense of the month:

> *13 Sep · Salary received · Salary · **−₹40,000***

A credit now draws `+` in green. The heading counts the two sides apart —
`₹651 out, ₹42,000 in · 3 rows · 13 days`, and rows rather than *payments*,
because a salary is not one. The closing note measures the spending only; with
credits left in it named the salary *"sabse bada"* and every share it computed
was against a total that included it.

**Rows outside the client's window.** The client's ledger comes from
`GET /deck?to=` — one window. A card can name a row from before it (*"last
month's Swiggy"*), and today that row silently vanishes from the table. The
card asks for the rows it cannot resolve by id: `GET /transactions?ids=a,b,c`
and `GET /meals?ids=` — two small read endpoints, live rows, same envelope.
Deleted rows come back with `deleted_at` set and render struck through, so the
card keeps telling the truth about a row that used to be there.

### 2 · Confirm card — the record of a write

Stays the shape it is (`lede`, `fields[]` with `guessed`, `unresolved`,
`needs_quantity`) with four changes.

**The dot replaces the word.** `· andaaza` after a guessed value becomes the
amber dot before it. The two fallback lines are English: *Not recognised:
paneer tikka — not in the total* and *2 roti — how much? No weight, no macros.*

**The ⋮ tray, on the card's lede row:**

| Action | Shown when | What it does |
|---|---|---|
| `Confirm` | any field is guessed | Row gets `confidence = 1`; every dot on the card clears. See *Data*. |
| `Fixed` / `Repeat` | `source = paisa` | The flags the ledger already has, same as the table row. |
| `Edit` | always | Drops the row's edit text into the composer, same as the table row. |
| `Delete` | the source has a row that can go: paisa, diet, pantry, places; `Forget` on memory | Soft-deletes through the route. The card stays, lede struck, `Deleted` in the tray's place. A deleted row is history, not an embarrassment. People have no delete route; a day's facts and a profile change have no row to delete. |

Tapping a field still opens the composer with that field's name — the
one-tap-fix the card was built for — and `Edit` in the tray is the same thing
for the whole row.

**Every write gets one.** Today only `log_meal`, `log_payment` and
`log_exercise` earn a card. The rest of the writes did happen, and the user
deserves to see what: 

| Tool | Lede | Fields |
|---|---|---|
| `correct_payment`, `correct_meal` | the row's lede again | the row, corrected — the card the user sees after *"woh 150 tha"* is the same card as after the log |
| `log_day` | `6 h 40 m sleep · 71.2 kg` (whatever was set) | one per value set — sleep, weight, each habit ticked |
| `pantry_move` | `Paneer · 200 g left` | food, moved by, kind (`bought` / `used` / `waste`) |
| `keep_dish` | `Saved · Paneer bhurji` | — (the ★ on a suggest card already shows this when the card is on screen) |
| `file_person` | `Mohan Lal · friend` | relation, note |
| `save_place` | `Blue Tokai · café` | kind, area |
| `remember` | `Remembered` | the text, one line. Tray: `Forget` — deletes the memory. |
| `update_profile` | `Protein target → 140 g` | field, old → new |

`source` widens from `paisa | diet | body` to add `pantry | people | places |
memory | profile`. The source picks which route `Edit`, `Delete` and `Confirm`
call; nothing else about the card changes per source.

**Live, not a snapshot.** The card resolves its `row_id` against the client's
rows like the table does. If the row was edited later, the card shows the live
values; if it was deleted, it shows the strike. The stored `fields[]` are the
fallback for a row the client does not hold, and the record of what the agent
guessed at the time — a `guessed` flag is a fact about the agent's own output,
not a sentence about the user's data.

### 3 · Dish card — a suggestion is one tap from logged

The `suggest` card carries `items[]`; for `type = dish` an item renders as a
dish card:

```
┌──────────────────────────────────────────────┐
│ [image]  Paneer bhurji                    ⋮  │
│  72×72   dinner · 15 min                     │
│          32 g protein · 410 kcal             │
│          missing: capsicum                   │
└──────────────────────────────────────────────┘
```

- **Image** from `dishes.image_url` — the column exists, nothing on the wire
  invents one. No image → a flat tile in `color.greenTint` with the dish's
  first letter. Never a stock photo, never a food emoji.
- **Name** in display type; **meal type and minutes** in mono below it;
  **protein and kcal** as the number line. Protein is required on a dish, so it
  is always there; kcal may be `—` (unknown is not zero).
- **`missing:`** appears only when the pantry has an opinion — the tool's
  `missing[]` for that dish. An untracked ingredient says nothing.
- **Tap the card → logged.** `POST /chat/act {name: "log_meal", args: {dish_id,
  text_said, meal_type, local_day}}`: the same tool the agent calls, run
  without the model. The dish is known by id, so the ladder is skipped and
  nothing is guessed. Under 300 ms, no tokens, the row lands in the ledger.
  The card flips to `✓ Logged`, and a receipt — *Tofu bhurji logged · 42 g
  protein left* — shows above the composer for three seconds and goes. No
  model in the loop: a tap on a suggestion can only mean *this one*.
- **⋮ tray:** `Save` (★ — the dish's save route) · `Not this` (removes the
  item from the card, sends nothing; the agent has one alternative, the user
  does not need a form to decline).
- **Two at most.** One suggestion and one alternative, stacked. The rule was
  already in `SuggestCard.tsx`; it stays.

**How the runner knows which dishes the model picked.** `suggest_dishes`
returns candidates, not a ranking; the model chooses in prose. The runner
matches the reply text against the *candidate names and aliases* returned in
that same turn (case-insensitive, whole-word) and builds the card from the
matches, first two in order of appearance. No matches → no card, prose stands.
The set it matches against is closed and small, so this is a lookup, not a
parse.

**The wire item** carries `dish_id` plus the display fields — `name`,
`meal_type`, `minutes`, `protein_g`, `kcal`, `image_url`, `missing[]`. These
are reference values on the dish, not claims about the user, so carrying them
is allowed (CLAUDE.md, *never store a sentence*). The client still resolves
`dish_id` against its dish library when it has the row, so an edited image or
macro shows the edit.

**Exercises** render on the same card with the fields that apply: `image_url`,
`kind`, muscle group, `tried ×N`; tap → `POST /chat/act` with `log_exercise`,
which bumps `tried`; the receipt flashes and goes. There is no `suggest_exercises`
tool and none is needed: `exercises` already plays the part `suggest_dishes`
plays — filtered candidates with their signals (`tried`, `last_tried`,
minutes), and the model ranks. The runner matches exercise names from the
prose against that turn's `exercises` result the same way it matches dishes.

### 4 · Ask card

Unchanged in shape. Its question is the model's prose, so it stays in the
user's language. The option chips stay mono. One rule added: an `ask` that
blocks a write shows the pending row's lede above the question, struck in
`color.faint`, so *"kitna chicken tha?"* is visibly about *dinner · 2 roti +
chicken* and not a question from nowhere.

### 5 · The live row

Verified 2026-09-12. While the agent works, the row shows the mascot in
`thinking` with the word `Thinking…` beside it (`role=status`, so it is read
aloud). When the reply lands, the newest reply's face takes the `done` state:
the amber ring closes and three sparks hold at the top-right, on the reply
itself, until the next turn starts. No `Done` text — the sparks are the word.
The sparks draw at every size now; they used to be gated to the 44 px mark and
so never appeared beside a reply.

### 6 · Failure row

A turn that never reaches the server, or comes back 5xx, renders a plain agent
bubble in English — *Didn't reach the server.* — with one `Retry` chip that
resends the same text. No mascot state for it; failure is not a mood.

## Data

**Wire — `cards[]` on `POST /chat` and `GET /chat`**

```ts
{ kind: 'agent',   text }                                   // markdown, rendered
{ kind: 'table',   source: 'paisa'|'diet', heading, ids[] }
{ kind: 'confirm', source, row_id, state: 'written'|'proposed', lede,
                   fields: [{ key, label, value, guessed }], unresolved[], needs_quantity[] }
{ kind: 'suggest', items: [{ type: 'dish'|'exercise', ref, name, why, saved,
                   meal_type?, minutes?, protein_g?, kcal?, image_url?, missing?[] }] }
{ kind: 'ask',     question, options[], pending_row_id? }
```

Changes from today: `confirm.source` widens; `suggest` items gain the display
fields; `ask` gains `pending_row_id`; `table` is actually emitted.

**Rows**

- `transactions.confidence` already exists (float). `log_payment` writes `0.7`
  unless the model passes `category_stated: true` (the user named the
  category); `Confirm` PATCHes it to `1`. The dot on a paisa card is drawn from
  the live row — `confidence < 1` — with the card's `guessed` as the fallback.
- `meal_logs.confidence` already existed, so `Confirm` means the same thing on
  a meal with no migration. A meal's confidence is the ladder's: `1` when every
  line matched and carried a quantity, `0.6` otherwise — the dot on kcal and
  protein reads it, because the macros are only as sure as the resolution.
- No column anywhere else. A person's relation or a place's kind is the user's
  word by construction; the card shows no dot and no `Confirm`.

**New reads:** `GET /transactions?ids=` and `GET /meals?ids=` — up to 50 ids,
live rows including soft-deleted ones (with `deleted_at`), same shapes the deck
returns.

**One new write:** `POST /chat/act {name, args, record?}` — a tool run from a
tap. The runner executes it, builds its cards and returns the same shape as
`POST /chat`, zero tokens. With `record: true` it also appends an agent turn
(text is the card's one line; `model = "tap"`); a tap leaves it off, because
its confirmation is a receipt. A tool that refuses returns the route's own
status. `@mention` shortcuts will take this path with `record: true`
(`mentions.md`): a card the user asked for belongs in the scrollback.

`log_meal` gained `dish_id` and `servings`: when the caller already knows the
dish, the ladder is skipped and the line is the dish, by id. `exercises` now
returns `aliases`, `image_url` and `last_tried`, so its rows can be matched
from the prose and drawn on a card.

**Client:** `toChatMsg()` maps `table`; `ConfirmMsg.source` widens; a
`Dot` component (6 px, `color.amber`) replaces the `· andaaza` string in
`ConfirmCard.tsx`. The same component should later replace the four other
`· andaaza` strings (HeroCard locked line, Profile, People, Places) — listed as
follow-up, not part of this spec.

## Rules and edge cases

- **A write with an error returns no card**, as today. The agent says what was
  refused; a card would claim a write that did not happen.
- **Two writes in one turn** stack two confirm cards under one prose bubble.
  The runner already dedupes the same write twice.
- **Tap-to-log twice.** The dish card disables after its tap; a second log of
  the same dish is typed, deliberately.
- **A dish without protein cannot exist** (column is `NOT NULL`); a dish
  without kcal shows `—`. The card never shows `0 kcal`.
- **Reload.** The thread comes from `GET /chat`; a tap left nothing in it, by
  design. What survives is the fact: the dish card's `✓ Logged` is derived from
  the ledger (a meal today with the dish's name, since the deck's meal rows
  carry no dish id; the Android app resolves by id), and the meal is in
  `@meals`. Tomorrow the same card reads `Tap to log` again, which is right —
  it is a new day. `@mention` replies are still client-only until
  `mentions.md` moves them onto `/chat/act` with `record: true`.
- **Markdown in prose** renders bold, lists, inline code, links and tables;
  raw HTML is stripped; headings flatten to bold. The prompt tells the model
  the reply is a sentence, not a document.

## Decided against

- **Tap-to-log through the agent** (send *"Paneer bhurji log kar do"* and let
  the model call `log_meal`). One write path is tidy, and it is how ★ works
  today. Rejected for the tap: five seconds and a model call to interpret a
  gesture that has exactly one meaning. The route is the write path; the agent
  is one of its callers, the tap is another.
- **The model emitting card JSON.** It would let it "pick" dishes explicitly.
  Rejected in `agent.md` already: a model asked for JSON about a write will
  eventually describe one that did not happen. Cards come from tool results.
- **A `pick_dishes(ids)` tool** for the model to name its choice. Honest, but a
  second round-trip on every suggestion. Name-matching against the turn's own
  candidate set costs nothing and cannot pick a dish the tool did not return.
- **Storing display fields on the table card** so rows outside the window
  render without a fetch. That is the snapshot the live-ids rule exists to
  forbid; a copied amount is wrong the moment the row is edited.
- **A green dot for confirmed.** Certainty is the default; marking it would
  make every card look like a checklist.
- **A separate "payment card" component.** The row already exists in
  `TableCard.tsx` and `ItemList.tsx`; a third copy is how the two drift.
- **Keeping `· andaaza` as a name** (CLAUDE.md lists it with `Paisa` and
  `udhaar`). It is a *state*, not a thing, and states are copy. `udhaar` names
  a kind of row and stays. CLAUDE.md's line changes when this ships.
- **A `Done` word beside the finished face.** Tested, removed the same day: the
  sparks say it, and a word under every reply is noise.
- **Appending the tap's confirm card to the thread.** Built, then taken out
  the same day. A receipt that lives forever in the scrollback is noise, and
  it records nothing the ledger does not: the row is there, the dish card
  reads it, `@meals` lists it. The user's own comparison decided it — a
  payment app's "paid" toast appears and goes. `record: true` stays on the
  endpoint for shortcuts, whose cards *are* the answer the user asked for.
- **`Open` in the dish card's tray.** There is no dish page to open — Your
  data expands a dish in place — so the action would have been a navigation
  to a list. Returns with a dish page, if one is ever wanted.
- **`old → new` on the profile card.** The route returns the row after the
  write; the old value would need a read before it. A second query for one
  card's decoration is not worth it; the card shows the new value.
- **Making the tray a third copy.** `messages/Tray.tsx` is the one tray now;
  the chat table and every card draw it. The report's `ItemList` keeps its own
  because its prompt-editing action (Repaid) has no chat equivalent yet.

## Verified

`backend/tests/test_chat_cards.py` asserts the wire: a rows read returns a
table of ids with a number-first heading and a totals read does not; a
category is `0.7` until `category_stated`, and `Confirm` raises it to `1`;
every write tool earns exactly one English confirm card; dishes named in the
prose become a card, first two in order, alias-aware, never a half-name;
rows by id come back deleted ones included, capped at 50; the deck still hides
deleted rows.

By hand in the browser, 2026-09-13: the confirm card's dot, tray and Confirm
(dot clears, and stays clear after reload); the dish card from a real
suggestion, tap → `POST /chat/act` → the receipt above the composer, gone
three seconds later, `✓ Logged` still on the card after a reload and nothing
added to the thread; the ledger card from a rows read. Not exercised by hand: the failure bubble's
Retry (code path only), and rows fetched from outside the deck's window (the
dev data is one month; the endpoint is tested).

## Open

Nothing. The two questions this spec was written with were answered the day
it shipped: a tap's confirmation is a receipt and does not need to persist —
the ledger and the tapped card carry the fact — and exercises get a card
through the `exercises` tool without a second suggest tool. `@mention`
persistence is `mentions.md`'s, via `/chat/act` with `record: true`.
