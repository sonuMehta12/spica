# Agent tools — the functions the model may call

> Status: **settled 2026-09-12 — companion to `agent.md`.** Twenty tools, down
> from forty-five; the ceiling is twenty-five and this stays under it without a
> second agent. Work is out until after release. *Twenty-three on 2026-09-15:
> the two deletes (`done/agent-deletes.md`), `manage_habit` (`done/habits.md`)
> and `categorise_now` (`in-progress/categorise.md`) — the last is the batch's
> door, not a new capability. Twenty-five on 2026-09-27: `manage_project` and
> `save_task` (`done/projects.md`) — adding and changing a task share one
> tool so the ceiling holds. **Twenty-six on 2026-09-27, the ceiling raised on
> purpose:** `work_report`, because the agent could not read a task at all and
> answered *"aaj kya due hai?"* with `paisa_report`. **Twenty-seven on 2026-10-10:**
> `manage_commitment` (`done/commitments.md`) — the money side's only way
> to change what is owed was a flag on a payment that had already happened, so
> *"is mahine ka rent kam hai"* had no path at all. The ceiling is a guideline
> that makes each new tool a decision; `tests/test_agent.py` holds the current
> number, and raising it means writing the reason here.*
> Surface: backend.
>
> **Prerequisites shipped 2026-09-12** (`backend/tests/test_paisa_summary.py`,
> `test_days.py`): the daily-limit math moved to the server as
> `app/paisa_summary.py`, served as `GET /paisa/summary?fields=` — the
> `paisa_report` tool over HTTP, and the deck stays rows-only; `PUT /days/{day}`
> exists; a `lent` or `borrowed` row without a counterparty is a 422 for every
> caller; `llm.py` reads `LLM_PROVIDER` / `LLM_MODEL` (`openai` /
> `gpt-6-luna`) so switching vendor is two env lines.

A *tool* is a function the model may call: a name, a one-line purpose it reads,
a JSON schema for the arguments, a typed return. The model **picks the tool and
fills the arguments itself** — `paisa_report(from, to, fields=["daily_avg"])`
— the function runs, returns JSON, the model reads it and answers. It chooses
what to ask for; the tool computes only that. Every tool below wraps a route
that already exists, so replays, derived fields and the tests come with it.

## What lives in the prompt instead of a tool

Three things every turn needs and no turn changes, so they are **assembled into
the system prompt** rather than fetched:

| In the prompt | Why not a tool |
|---|---|
| **Today** — `local_day`, weekday, time, days left in month, salary day | Always needed. The model does "is hafte", "kal", "pichhle mahine" against these; a round-trip for a fact that never moves mid-turn is waste |
| **Memories** — the thirteen facts about the person | Small, always relevant, and the reason the agent sounds like it knows you |
| **Targets** — protein, kcal band, sleep, savings, salary | The goals are facts the app computes with; the model should never have to ask what the goal is |

## Seven rules every tool follows

1. **One read per domain.** It returns only the computed fields the model names,
   and rows only when `rows` is one of them — capped at 30 a call, with a
   cursor. The model can always ask for less; it can never be handed 180 rows.
2. **Ranges are two dates**, `from` and `to`, never "7 days". The model computes
   them from the date in the prompt.
3. **Every write takes a client ULID** the agent mints. A retried call returns
   the same row. Every write returns the row.
4. **Unknown is `null`, never 0** — with the count beside it (`sleep: { avg:
   null, days_logged: 0 }`) so the model says *"no data"*.
5. **Money is integer paise on the wire**, formatted only in the card.
6. **Correct a wrong value; delete a wrong row.** A wrong category or amount is
   a `correct_*` call, because the `(estimated, actual)` pair is training data.
   A row that should not exist at all is a `delete_*` call. Deletes are soft.
   *This rule read "a tool never deletes" until 2026-09-13; `spec/done/agent-deletes.md`
   is why it changed.*
7. **Teaching is the server's side effect, not the model's job.** Correcting a
   payment closes its prediction and updates the learned payee; the model calls
   one write and the learning happens behind it.

## The question: computed fields, or rows and let the model derive?

**Computed fields the model names, by default. Rows only when it asks, never
more than thirty.**

A model summing forty payments is off by a rupee often enough to be distrusted.
Some numbers are **policy**, not arithmetic — today's limit is salary minus
savings minus fixed minus locked, over days left — and a model re-deriving it
disagrees with the Paisa card. And three months is 180 rows of context spent on
data it will then add wrongly.

So `fields[]` is a **closed list** — exactly the numbers the cards show, plus
`by_day`, `by_category`, `by_counterparty` so *"kaunse din"* and *"kahan"* are
answered without rows — each computed by the **same function the deck uses**.
`rows` is one more field, opt-in, thirty at a time with `total_matching`, so a
page is never mistaken for the whole. In most conversations no row is fetched;
when the user says *"pichhle 30 din ke payments dikhao"*, thirty come, and the
agent offers the next thirty.

**Decided, and done:** the daily limit was computed on the client
(`dailySpendLimit()`). It is now `app/paisa_summary.py`, one function with two
callers — `GET /paisa/summary` for the deck and the report, the `paisa_report`
tool for the agent. **Not `/deck`**: that contract is rows-only
(`spec/done/deck-api.md`) and its test asserts no `limit` key; the derived set
gets its own read, asked for by name, which is what the tool is anyway.

---

## Paisa — 4

### `paisa_report(from, to, fields[], category?, counterparty_id?, rows_limit=30, after?)`

```
fields — any of:
  spent · income · daily_avg · days_in_range
  within_limit          { n, of }
  limit_today           { limit, spent_today, left, pool, locked, days_left }   when `to` is today
  udhaar                { out, owe, open_lendings, open_borrowings }
  fixed                 { fixed_paise, repeats_paise }
  by_day[]              { local_day, spent }            ≤ 92 numbers
  by_category[]         { category, paise, share }
  by_counterparty[]     { id, name, paise, n }          top 20
  to_review[]           { transaction_id, amount, payee, guess: { category,
                          description, confidence, why } }
                        — payments the batch was unsure about and the user has
                          not answered. **This is the daily review card.**
  rows[]                the transactions, every field, ≤ 30, + next_after, total_matching
→ only the keys asked for
```

*"Is mahine ka average"* → `["daily_avg"]`, one number. *"Sunday ko kya kharcha
kiya"* → `from = to = Sunday, ["rows"]`, six rows. *"Aaj ke doubtful payments"*
→ `["to_review"]`.

### `log_payment(id, amount_paise, direction, kind, category, description, local_day, occurred_at, counterparty_name?, place_id?, method?, note?, fixed?, repeats?, settles_id?, category_stated?)`

`POST /transactions`, so the counterparty row is created from the name, flags
couple, and `settle()` guards a repayment. **`kind` covers udhaar**: `lent`,
`borrowed`, `repayment` are values here, not separate tools — and the server
refuses `lent` or `borrowed` without `counterparty_name`, which is the rule the
separate tools were enforcing. Returns the row → a `confirm` card.

### `correct_payment(id, patch)` · `delete_payment(id)`

`PATCH /transactions/{id}` — any field but the fix, including `place_id` (*"wo
₹285 Mohan Lal ki dukaan pe tha"*) and the gift flow.

**It is also how a prediction is answered.** When the row has an open
prediction, this write closes it: the server records `actual_category`,
`corrected_at`, and updates the learned payee. Accepting a guess is sending the
guessed value back — the user's *Haan* makes the guess a fact, so the model
writes `{category: "Health/Diet"}` and the server sees it matched. Nothing else
to call.

### `categorise_now(local_day?)`

Tier 0 → 1 → 2 over every transaction of the day with no `predictions` row.
Fills PAKKA rows silently, leaves the rest for `to_review`. **The nightly cron
calls this; so does *"aaj ke payments dekh lo"* before bed.** One function.

## Diet — 8

### `diet_report(from, to, fields[], meal_type?, rows_limit=30, after?)`

```
fields — any of:
  avg_protein_g · avg_kcal · logged_days · days_in_range
  protein_hit_days · kcal_in_band_days
  today             { protein_g, kcal, protein_left_g, kcal_left, meals_logged }   when `to` is today
  by_day[] · by_meal_type[] · top_dishes[]
  sleep             { avg_hours | null, days_logged }
  weight            { latest_kg, latest_day, change_30d | null }
  habits_week[]     { habit, days[] }                   the strip
  pantry[]          { food, stock, unit, status }        what is in the house — a read of diet state
  rows[]            meals with their lines, ≤ 30      · habit_rows[] · day_rows[]
→ only the keys asked for
```

`today.protein_left_g` is the number the agent leads with — computed here, never
in a head. *"Ghar pe kya hai"* is `["pantry"]`.

### `log_meal(id, local_day, occurred_at, meal_type, text | lines[], note?)`

Give it the sentence or the lines. With text it **resolves** each part through
the ladder — exact name → alias → trigram → embedding — writes what matched,
and returns the row with every line marked `matched` or `unresolved`. Nothing
is blocked on one uncertain word (`diet-logging.md` §1); the card shows the gap
and `correct_meal` fills it. **Matching never creates a dish.** The server
computes macros and spends pantry stock.

### `correct_meal(id, patch?, lines[]?)` · `delete_meal(id)`

Fields, or the whole line set. *"Nahi chicken zyada thi"* re-derives the macros.

### `log_day(local_day, sleep_hours?, weight_kg?, habits[]?, note?)`

The day's facts in one write: *"gym gaya, 2 sutte, 6 ghante soya, 78 aaya"*.
`habits[]` is `{ habit, amount?, note? }` → `habit_logs`; sleep and weight go to
`days` and `weigh_ins`. **Needs `PUT /days/{local_day}`** — the one new route,
Phase B.

### `pantry_move(id, food_name, quantity, kind: purchase | opening)`

*"18 ande laaye"*, *"600 g atta bacha hai"*. The only pantry write the agent
makes; consumption follows from meals on its own.

### `suggest_dishes(minutes?, meal_type?, must_use?)`

Candidates with signals, **not a ranking**: `cookable_now`, `missing[]`,
`protein_g`, `minutes`, `last_had_days_ago`, `times_last_7d`, `tried`, `saved`,
plus `context { protein_left_g, slots_left, pantry_unknown[] }`. The model
ranks — the prompt is the engine. `pantry_unknown[]` is what lets it ask about
paneer instead of assuming it.

### `dishes_search(q)`

The same ladder over the whole pool, for *"paneer wali koi dish hai?"*.

### `keep_dish(dish_id? | new: { name, items[], … })`

The ★. Given an id, saves it; given a definition, creates a private dish and
saves it — from a suggestion the pool lacked, or the agent's proposal after the
same unresolved line has appeared three times: *"'moongphali chutney' 3 baar
likha — dish bana doon?"*. `capture.md`'s Door 1.

## Body — 2

### `exercises(kind?, muscle_group?, equipment?, minutes?, tried?)`

The library, filtered. *"Leg lagana hai, 20 minute"* is one call; the model
picks and says why.

### `log_exercise(exercise_id? | new: { name, kind, muscle_group, … }, did=true, local_day?)`

*"Aaj squats kiye"* → `tried += 1` and the date. *"Ye YouTube wala rakh lo"* →
a new row with `source: 'chat'` and the link, `did=false`.

## People — 2

### `people(kind?, with_money_open?)`

Every counterparty with sent, received, **still out, you owe, typical days**,
and their open lendings. *"Dost 2 ka kya hua"* is `with_money_open=true`. This
is the udhaar read; a separate one was the same query.

### `file_person(counterparty_id? | raw_name, kind?, relation?, note?, display_name?)`

With an id, updates; with only a name, creates — *"Wasim ko ₹500 cash dene
hain"* before any payment exists. **`source` is set by the server from the
caller**: the agent's writes land as `source='agent'`, unconfirmed, `· andaaza`
— and only past the threshold (money came back, or three separate days). The
user's *"ye meri behen hai"* through the UI lands confirmed.

## Places — 2

### `places(kind?)`

Pins with payments, spent, last seen.

### `save_place(place_id? | new: { name, lat, lng, kind }, radius_m?, counterparty_id?, note?)`

Create or edit; `counterparty_id` is *"ye dukaan Mohan Lal ki hai"*, after
which the pin shows four payments with nothing tagged. Placing a *payment* at a
pin is `correct_payment(id, {place_id})`.

## Memory — 2

### `remember(slug, kind, text)`

Only when the user said *yaad rakhna* or confirmed an `ask` card. Never a side
effect of logging. Facts about the person, never about their data.

### `update_profile(field, value)`

*"Protein target 140 kar do"* → `PATCH /users/me`. Reading the profile needs no
tool; it is in the prompt.

---

## How the pieces call each other

```
"2 roti aur dal khai, protein shake bhi"
   → log_meal(text=…)                       3 lines: 2 matched, "dal" via alias
   → diet_report(today, ["today"])          protein_left_g 58
   ← confirm card: "58g bacha hai · 2 roti · Dal · Whey shake" — guessed: dal katori

"pichhle teen mahine ka average kya raha"
   → paisa_report(2026-06-12, 2026-09-12, ["daily_avg", "by_category"])
   ← agent card: one number, three categories — zero rows fetched

"aaj ke payments dekh lo"
   → categorise_now()                       4 silent, 2 unsure
   → paisa_report(today, ["to_review"])
   ← two confirm cards, state proposed. Haan → correct_payment(id, {category: guess})

"kya khaun, 20 minute hain"
   → diet_report(today, ["today"])          protein_left_g 67
   → suggest_dishes(minutes=20)             candidates + pantry_unknown []
   ← suggest card: one dish, one alternative, ★ → keep_dish(id)
```

## What was merged, and why

| Was | Now | Reason |
|---|---|---|
| `today()` | the prompt | A fact every turn needs and no turn changes |
| `paisa_summary` + `paisa_rows` | `paisa_report` with `rows` as a field | The safety was *not dumping rows blindly*; one tool with rows opt-in and capped does that |
| `pending_review` | `paisa_report(["to_review"])` | It was a filter, not a tool |
| `confirm_prediction` | `correct_payment` | Answering a guess *is* correcting the row; closing the prediction and teaching the payee are the server's side effects |
| `udhaar_status` | `people(with_money_open)` | The same query with a filter |
| `log_lending` · `log_borrowing` · `log_repayment` · `mark_gift` | `log_payment` (`kind`) · `correct_payment` | They are `kind` values on one route; *name the person* is now a server rule, which is where it belonged |
| `place_payment` · `link_place` · `add_place` | `correct_payment(place_id)` · `save_place` | A payment's place is a field on the payment; create/edit a pin is one upsert |
| `diet_summary` + `diet_rows` + `habit_rows` + `day_rows` | `diet_report` | Same as paisa |
| `pantry_state` | `diet_report(["pantry"])` | Stock is a read of diet state |
| `resolve_dishes` | inside `log_meal` | The ladder runs on the way to the write; the card shows what matched. A separate lookup is `dishes_search` |
| `log_habit` · `log_weight` · `log_day` | `log_day` | "The day's facts" is one sentence from the user and one write |
| `save_dish` · `create_dish` | `keep_dish` | Both are the ★; one takes an id, one a definition |
| `did_exercise` · `add_exercise` | `log_exercise` | Same shape as `keep_dish` |
| `propose_person_kind` · `add_person` | `file_person` | `source` is set from the caller, not chosen by the model |
| `recall` · `profile` | the prompt | Thirteen facts and six targets are context, not a lookup |
| `set_target` | `update_profile` | Rename |

**Forty-five to twenty**, then twenty-one when delete arrived. Not by hiding tools in `action` switches — every tool
above is one verb on one kind of thing — but by moving constants into the
prompt, making filters into fields, and letting the server own the rules that
were being enforced by having two tools instead of one.

## On a second agent

**Not planned.** Twenty tools is inside the range where one model chooses
reliably. If Phase A's measurement says otherwise, the first fix is **gating,
not delegation**: show the Paisa tools when the message is about money, the
Diet tools when it is about food — decided by `@mention` or a keyword, with no
extra model call. A sub-agent adds a round-trip, a bill and a seam for context
to fall through; gating adds an `if`.

## Decided against

| Option | Why not |
|---|---|
| Rows on every read | Three months is 180 rows of context spent on data the model then adds wrongly; and it has no way to say *less* |
| Two reads per domain (summary / rows) | Right instinct, wrong shape — one tool with `rows` opt-in gives the model the same choice with half the surface |
| A free-text `fields` | A field the model invents is a number nobody checked. Closed list = every number is one the deck also computes |
| One `log_diet(kind, …)` mega-tool | Meals have lines and a resolver; the day's facts are scalars. Two honest shapes beat one with a switch |
| `query(sql)` | Unbounded. Typed tools mean the model cannot ask what the product did not decide to answer |
| A sub-agent per domain | Latency, cost, and a place for context to fall through. Gating does the job with an `if` |
| The model choosing `source` on a person | Then a guess can claim to be the user's word. The server knows who called |
| ~~Letting the agent delete~~ | **Reversed 2026-09-13.** The reason held for a wrong *value*, not for a row that should not exist. See `spec/done/agent-deletes.md` |

## Open

- **Tool gating.** Whether to show all twenty on every turn or gate by mode.
  Measure in Phase A: if the wrong tool is picked more than rarely, gate.
- **`log_meal` with text vs lines.** Text is the normal path; whether the model
  should ever pre-split into lines itself, or always hand the sentence over,
  decides how much the prompt must explain the ladder. Lean: always text.
