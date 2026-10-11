# The agent — one brain, many mouths, typed cards

> Status: **Phases A and B shipped 2026-09-12** (`backend/tests/test_agent.py`).
> Model: OpenAI `gpt-6-luna` behind the seam (`gpt-5.6-luna` until 2026-10-01),
> vendor and model as two env lines. Phase C — the nightly categorise batch and the skill file — is next
> and deliberately not started. `agent-tools.md` holds the tools.
>
> **How it is called.** The **Responses API**, non-streaming, `store=false`,
> `reasoning.effort="none"` (`LLM_EFFORT`) — since 2026-09-15. It was
> `chat.completions` at `"none"` before that, chosen for a message shape that
> maps one-to-one onto Anthropic's and for 2.7s over 4.8s a turn. What
> changed the decision: the user wants the agent to think, and this model
> allows thinking together with function tools only on `/v1/responses`. The
> seam holds in a different place now — `llm.respond()` is the one call
> shape, and an Anthropic `respond()` would wrap `messages.create` the same
> way. **Effort stays `none` for the agent**, measured the day it moved and
> not from single samples: three runs an effort on one prompt showed a
> greeting spending zero reasoning tokens at *every* effort, with a 2-6s
> spread that is network jitter; only a multi-step turn thinks at all
> (~200 tokens, ~1-2s), and at both efforts it picked the same two tools. No
> visible gain, paid on the slowest turns. The nightly categoriser keeps
> `medium`, where the gain is measured. Statelessness costs one thing: the
> model's reasoning items travel back with the tool outputs, encrypted
> (`include: reasoning.encrypted_content`), so nothing of the ledger is kept
> on the provider's side.
> Surface: backend (the brain) · frontend (the cards) · later, Claude surfaces.

## Why this file exists

The premise is *agent hi app hai*, and the agent is the one thing not built.
Its pieces are already decided in six places: the seam (`backend.md` § llm),
the endpoint shape (`api.md` § /chat), the tiers and skill file
(`paisa-categorise.md`), the estimate→correct loop (`diet-logging.md` §1–2),
the extraction ladder (`done/dishes.md`), the suggestion inputs
(`spec/in-progress/meal-suggestion.md`), and the *many mouths* requirement
(`agent-everywhere.md`). This file does not re-argue any of them. It joins them,
names what is still open, and cuts the work into phases that each ship with
tests.

## The one-paragraph version

The user types or dictates a loose Hinglish sentence. The agent turns it into
**rows** — a meal with its lines, a payment with its category, an exercise done —
writes them through the **same endpoints the app already has**, and answers with
**typed cards** the composer can draw: what it wrote, what it guessed, one
question if it must. Payments arrive on their own; a nightly batch classifies
them cheaply and puts only the uncertain ones in front of the user. Everything
the agent believes is marked until the user confirms it. Work is deferred, as
decided; this is Paisa and Diet.

## What is already decided (and stays decided)

| Decision | Where | What it fixes here |
|---|---|---|
| One module imports the SDK — `llm.py`, three functions | `backend.md` § llm | Every LLM call in this spec goes through it. Changing model or vendor is one file |
| `POST /chat` returns typed cards, by **id** | `api.md` § /chat | The output contract below extends the card union the composer already renders |
| Payments classify in **tiers**: dictionary → rules → one batched LLM call → user | `paisa-categorise.md` §5.4 | The "cron" the user described *is* Tier 2. No new buffer |
| Confidence bands PAKKA ≥85 · SHAYAD 50–84 · PATA NAHI <50; below PAKKA is **always a suggestion** | `paisa-categorise.md` §4.1 | What the agent may write silently and what it must ask |
| End-of-day review, not per-payment interruption | `paisa-categorise.md` §4.2 | The review card, once a day |
| The skill file — learned payees, bands, routines, rules from corrections; regenerated nightly | `paisa-categorise.md` §5.6–5.7 | The money half of the system prompt |
| **estimate → state it → correct → store the pair** — one primitive, four callers | `diet-logging.md` §2 | The shape of every write the agent proposes |
| Log what parsed, flag what did not; ask **only when the answer changes the number** | `diet-logging.md` §1 | When a card carries a question |
| The extraction ladder: exact → alias → trigram → embedding → unresolved. **Matching never creates a dish** | `done/dishes.md` | How a sentence becomes `meal_items` |
| Suggestion inputs are all live at ask time; **no score column** | `done/dishes.md`, `spec/in-progress/meal-suggestion.md` | Ranking is a prompt over retrieved state, not a rules engine |
| One suggestion, one alternative; lead with what is **left**; never invent stock | `spec/in-progress/meal-suggestion.md` §8 | Tone and the suggest card |
| Udhaar detection is a score over four signals, inside classification | `udhaar.md` §4.5, §6 | Lands in Tier 2's output, not a separate pass |
| Memory is facts about the **person**, never sentences about their **data** | `done/users-profile.md` | What the agent may write to `memories` |
| The agent guesses a person's `kind` only after 3 separate days or money coming back; places only after 3 days at one spot | `done/people.md`, `done/places.md` | Thresholds the batch respects |
| Inferred is marked `· andaaza`; confirmed is not | CLAUDE.md | Every card the agent emits |
| One agent, several mouths — Claude Code and the Claude app later, via one plugin | `agent-everywhere.md` | The tool layer is built so it can be re-exported as MCP without rewriting |

## Architecture — three decisions

### 1. There is no buffer. Rows land at once; the agent reads them later.

The alternative — hold captured payments in a bucket until a cron runs — was
considered and is worse. A payment that exists only in a buffer is invisible to
the deck, the report and the daily limit until the agent gets to it, and a
crashed cron loses money.

So: **a captured payment is written to `transactions` immediately** with what
capture knows (amount, payee name, time, fix) and `confidence` low. "The agent
has not looked yet" needs no new column — it is a transaction **with no
`predictions` row**. The nightly batch writes the prediction, fills `category`
and `description` on rows it is PAKKA about, and leaves SHAYAD rows for the
review card. A correction updates the row and stamps `predictions.corrected_at`.

| State | How it is represented | Who moves it |
|---|---|---|
| Captured, unseen | transaction exists, no prediction | capture |
| Seen, confident | prediction with `confidence ≥ 0.85`; category written | the batch |
| Seen, uncertain | prediction `< 0.85`; category **not** written; review card | the batch |
| Confirmed / corrected | `corrected_at` set; `actual_*` filled | the user, via a card or the ledger |

`predictions` was built for exactly this ("what the model saw and what it
guessed — separate from the ledger because a prediction is not a fact"). It gets
used, not replaced.

### 2. The tools are the endpoints that exist. No second write path.

The full list, with each tool's arguments and return, is in
**`agent-tools.md`** — twenty tools, down from forty-five. One read per
domain returning only the computed fields the model names, with rows opt-in
and capped at thirty; writes that mirror the routes; and today's date, the
memories and the targets in the prompt rather than behind a tool. Two
consequences are decided there: the daily-limit math moves to the server in
Phase A, and `PUT /days` lands in Phase B.

Forty-two routes already do idempotent writes with client ids, replays, soft
deletes and derived fields (`done/ledger-writes.md`). The agent calls **those**,
in-process, as functions — not a parallel `agent_tools` layer that re-implements
`settle()` or `couple_flags()` and drifts from them.

```
tools/                          each one: a name, a JSON schema, and a call into an
  paisa.py     log_payment      existing route function or its service helper
               correct_payment
               history          (GET /deck slice)
  diet.py      log_meal         → extraction ladder → POST /meals with meal_items
               correct_meal
               pantry_state
               suggest_dish     (reads; returns dish ids for the suggest card)
  body.py      log_habit · log_sleep · log_weight · did_exercise · suggest_exercise
  people.py    who_is           (GET /people slice)
  memory.py    remember · recall
```

Two consequences, both wanted. **Tests already cover the writes**, so agent tests
cover only *did it pick the right tool with the right arguments* — the seam is
mocked, the tools are real. And **`agent-everywhere.md` becomes a re-export**:
the same tool table served over MCP is the plugin, not a second implementation.

### 3. Cards, not prose. The card union grows by three.

*Composer* is the input bar at the bottom of the deck. A *card* is one typed
object in the agent's reply — a bubble, a table of ledger rows held by **id**,
a suggestion with a ★ — rather than a paragraph. The conversation renders a
list of them. The point: a suggestion can be kept only if it is an object, and
a number stays true only if the card points at the row rather than copying it.

The composer renders `user · agent · table · flow · todo · pantry` today, and
`table` already holds **ids, not rows**, so deleting a payment updates every card
that showed it. The agent's replies are lists of these, plus three new kinds:

```ts
/** A write the agent made or proposes, with the fields it guessed marked. */
interface ConfirmMsg {
  kind: 'confirm';
  id: string;
  source: 'paisa' | 'diet' | 'body';
  /** The row it wrote (write-then-show) or would write (ask-first). */
  rowId: string | null;
  state: 'written' | 'proposed';
  /** Each field: value, whether it was guessed, and what to send to change it. */
  fields: { key: string; label: string; value: string; guessed: boolean }[];
  /** Diet: what is left today, first. Paisa: what the limit now reads. */
  lede: string;
}

/** A grid of things, each keepable with one tap — dishes, exercises. */
interface SuggestMsg {
  kind: 'suggest';
  id: string;
  items: { type: 'dish' | 'exercise'; ref: string; why: string; saved: boolean }[];
}

/** One question, only when the answer changes a number. */
interface AskMsg {
  kind: 'ask';
  id: string;
  question: string;
  /** Tapping one sends it back as the user's next message. */
  options?: string[];
  /** The write this question is blocking, if any. */
  pendingRowId?: string;
}
```

**Write-then-show for meals, ask-first only when a number is at stake.** The
user's own description of the flow: *"log kar diya, phir display dikhayega taaki
verify kar sake."* So `log_meal` writes, then returns a `confirm` card in state
`written`, guessed fields marked. Editing a field on the card is a `PATCH` — the
same edit the ledger already allows. The card is the estimate→correct loop with
a UI on it. The one exception is `diet-logging.md` §1's rule: if a word changes
the macros materially (*"kitna chicken tha"*), the agent asks first with an
`ask` card and the row waits.

**Payments follow the tiers.** PAKKA writes silently and appears in the log.
SHAYAD and PATA NAHI never write a category; they come back in **one review
card** a day — a `confirm` per uncertain row, stacked — per §4.2.

## The prompt — assembled, never stored

The system prompt is **built per request** from live rows. Nothing in it is a
stored sentence about the user's data — the house rule — so it cannot drift.

```
1. Who you are talking to        memories (kind, slug, text) + profile targets
2. What today is                 local_day, weekday, time, days left in month,
                                 salary day — so no tool is needed for dates
3. What today looks like         the /deck slice for today: spent vs limit,
                                 protein vs target, sleep, the habit strip
4. What the agent has learned    the skill file — learned payees, bands,
                                 routines, rules from corrections (paisa) ·
                                 portion calibration pairs (diet)
5. The tools                     the twenty, with schemas
6. The rules                     the twelve lines below
7. The conversation              last N turns
8. The message
```

The rules block, verbatim in the prompt:

```
- Answer in the user's register: Hinglish as they write it. Copy is English.
- Lead with what is LEFT, not what was consumed or spent.
- Every number you did not read from a row is a guess: mark it.
- Unknown is not zero. Say "no data", never 0.
- Never invent stock, a payee, or a dish. Match or ask.
- Ask only when the answer changes a number. One question, not a form.
- One suggestion, at most one alternative. No menus.
- Write through tools only. Never describe a write you did not make.
- A row you write must come back as a card with its id.
- Confidence below 0.85 is a suggestion, never a silent write.
- Memory is about the person, never about their data.
- Do not lecture. A missed target is logged flat.
```

The skill file is `paisa-categorise.md` §5.6's markdown, generated nightly from
`counterparties` (learned payees), `predictions` (bands, corrections) and the
ledger (routines) — **a report, regenerated, not a document that is edited**. It
is served by `GET /skill-file` so the user can read what the agent believes about
them, which is the fastest way to catch it learning something wrong.

## The two entry points

```
POST /chat        { message, local_day }  →  { reply: ChatMsg[] }       conversation
categorise_now()  the tool · scripts/categorise.py  the cron            the batch
                  — no route; decided 2026-09-15, spec/in-progress/categorise.md
```

Both call `llm.py`. `/chat` uses tool-calling; `/categorise` is also a tool —
`categorise_now` — so the nightly run and *"aaj ke payments dekh lo"* before bed
are the same function, never two computations. It uses one structured call
over the day's unseen transactions with their signals, exactly as §5.6 lays
out, and validates the output before anything touches the ledger (category not
in the set → drop; `confidence > 0.85` on a payee seen 0 times → cap at 0.84;
unparseable → confidence 0, falls to the user).

## Phases — each ships with its tests

Answering the four questions asked of this file first. **Flow before UI?** The
output contract comes first, because the prompt, the tools and the UI all hang
off what a reply *is*. **Prompt before tools?** The prompt is assembled from the
same rows the tools read, so they are built together per phase; neither is
written once. **Tools?** They exist; each phase wraps the ones it needs. **Skill
files?** Two of them, already specified: the paisa skill file (§5.6) and the
person's memories. Phase C generates the first; the second is already a table.

| Phase | What ships | Proves | Tests |
|---|---|---|---|
| **A · Read** ✅ | `llm.py` real; `POST /chat` and `GET /chat`; one thread, a 20-turn window and a rolling summary; the assembled prompt; `paisa_report` and `diet_report` with the closed field lists. **The composer sends free text to it**, and the thread reloads from the server on boot | The seam, the prompt, the card contract | 19 tests, seam mocked |
| **B · Writes** ✅ | All nineteen tools wired to the routes that already exist. `log_meal` runs the ladder on the way to the write; `MealIn` gained `items`, so the pantry is actually spent — it never was before. `confirm` cards with guessed fields marked | The estimate→correct loop; the ladder end to end | ladder rungs, measures, refusals, savepoints, the window |
| **C · Paisa batch** | `POST /categorise` nightly over unseen rows; `predictions` written; PAKKA filled silently; one daily review card of SHAYAD rows; corrections update `actual_*`; skill file generated and served | Tiers, cost control, and the accuracy check `backend.md` step 5 asks for: train on 14 labelled days, predict 13, **≥70% or the approach is wrong** | validation rules; the cap; nothing below 0.85 writes a category; the eval script over the 27 labelled days |
| **D · Suggest** | `suggest_dish` / `suggest_exercise` → `suggest` grid card; ★ saves; *"20 minute hain"*, *"leg lagana hai"*, *"kya khaun"* | Ranking as a prompt over live state; the keep-a-suggestion door from `capture.md` | pantry-unknown → asks, never invents; repetition lowers rank; a saved item is a `dish_saves` row |
| **E · Udhaar + people + places** | the §4.5 score inside the batch; round-thousand and money-back as signals; `kind` proposed after the threshold; repayment matching | Detection without a form | the scoring table; the three-same-day repayments close separately; nothing below threshold speaks |
| **F · Many mouths** | the tool table served as MCP for Claude Code; memory read/write from there | `agent-everywhere.md`, first slice | same tool tests, different transport |

Work stays out until after release, as decided. Phase A is small on purpose: it
is the whole shape at one-tenth the size, and every later phase is a new tool
and a new card kind on the same spine.

## Rules and edge cases

- **Replays are the agent's problem too.** Every write carries a client ULID the
  agent mints; a retried tool call returns 200 and the same row. The agent never
  writes twice because the model said the sentence twice.
- **Two meals in one sentence are two rows.** Splitting is at the separators the
  logs already use (`+`, `aur`, `,`, `with`) and at slot words (*subah*, *raat*).
- **A payment the agent cannot classify still counts against the limit.** Amount
  is fact; category is interpretation. The limit reads amounts.
- **The agent corrects a wrong value and deletes a wrong row.** A wrong
  category or amount is a `PATCH`, and the correction is data. A row that
  should not exist is `delete_payment` / `delete_meal`, soft, through the same
  routes the UI uses. It read *"the agent never deletes"* until 2026-09-13,
  when the missing tool turned into an invented excuse — `spec/done/agent-deletes.md`.
- **Corrections are stored as pairs.** `(estimated, actual)` for meals and
  `(signals, predicted, actual)` for payments — the calibration and training
  sets that cannot be backfilled, collected from day one whether or not a model
  is ever trained.
- **Memory writes are rare and explicit.** *"Yaad rakhna, main Sunday ko gym
  nahi jaata"* is a `remember`. *"Aaj ₹500 lagaye"* is not. The agent asks
  before writing a memory unless the user said *remember*.
- **Free text is the agent's.** There is no `@mention` syntax; the `+` tray
  tools build their cards from rows already on the device.
- **Editing is said, not filled in.** Tapping a field on a `confirm` card puts
  the correction in the composer rather than opening a form: the agent already
  understands sentences, and *"nahi, transport tha"* is the shortest correct
  thing to type.
- **Every agent turn refetches, and that is the point.** A reply is followed by
  `GET /deck`, `/paisa/summary`, `/pantry` and `/exercises`. Four calls, kept
  deliberately: the agent's writes are the only ones in the app the client
  cannot predict — it sent a sentence, and what came back could be one row,
  three, or a refusal — so guessing the new state would be guessing. Fresh data
  is worth the round-trip. Settled 2026-09-12; revisit only if a turn feels
  slow.
- **A tool failure undoes only that tool.** Each call runs in a savepoint; a
  plain rollback would discard the conversation row and any tool that already
  succeeded in the same turn.
- **The same write twice in one turn happens once.** A model repeating itself
  is not the user asking twice, and ids are minted server-side so nothing else
  would catch it.
- **Nothing runs on the phone yet.** The prototype's server holds the rows and
  the agent reads them there; the local-first question in `notes.md` stays
  open and this spec does not close it.

## Decided against

| Option | Why not |
|---|---|
| A buffer table for unseen payments, drained by a cron | A payment in a buffer is invisible to the limit and the deck until the cron runs, and a crashed cron loses money. The ledger plus a missing `predictions` row already says *unseen* |
| A `status` column on `transactions` for agent-seen | Same thing; `predictions` is that column with history attached |
| A separate agent tool layer that writes to the DB directly | Re-implements `settle()`, `couple_flags()`, the pantry walk, replays — and drifts from them. The routes are the tools |
| Prose replies | A suggestion can only be kept if it is an object; a number can only stay true if it is an id. `api.md` decided this and every later spec depends on it |
| Ask-first for every meal | The user logs at night in a batch and corrects rarely. A confirmation on every line is the form this product exists to not be. Write, show, let them fix |
| Silent writes for every payment | Below PAKKA a wrong category the user believes is worse than a visible gap — `paisa-categorise.md` §4.1, and the whole review design rests on it |
| A stored system prompt | A sentence about the user's data drifts the first time a row changes. Assembled per request from rows, it cannot |
| A rules engine for suggestions | `spec/in-progress/meal-suggestion.md` §11: this is a prompt over retrieved state. The rules are few and the state changes hourly |
| Training a model | V1 has 27 labelled days. The skill file is the model; the pairs are kept so a trained one is possible later |
| Work in this pass | Deferred until after release, by decision. Its tools exist (`tasks`); its cards do not. Work data arrives through `spec/work-sync.md` |

## Open

1. **`meal_logs.kcal` is NOT NULL, so an unknown meal stores zero.** Most foods
   in the library have no nutrition on file, and the agent can now log a plate
   made only of those. The row keeps 0; the card and the reply say *unknown*,
   which is honest at the edge but not in the table — and the deck averages
   that zero. Making the column nullable touches the deck, the report and
   `diet_summary`, so it is a decision rather than a patch.
2. **`2 roti` has no weight.** The ladder refuses to invent one and asks
   instead, which is correct but happens on nearly every Indian plate. The fix
   is data, not code: `measures` needs *roti*, *chapati*, *anda* and the rest,
   the way it already has *katori* and *muththi*. Listed in `TODO.md`.
3. **Where the batch is scheduled.** A `cron` on the laptop, an APScheduler job
   inside the API, or a hand-run endpoint until Android exists. Recommendation:
   the endpoint now, scheduled later; nothing in the prototype runs overnight.
4. **How the daily review is surfaced in the prototype.** A card at the top of
   the conversation on first open, or a badge on the Paisa card. `§4.2` says a
   notification at 9pm; the web prototype has none.
5. **Voice.** `diet-logging.md` says no in-app STT; the composer has a mic. The
   honest resolution recorded there is *the mic focuses the composer*; confirm
   it still stands for the prototype.
6. ~~Thinking for the agent means the Responses API.~~ **Decided and done
   2026-09-15** — see *How it is called* above. The migration was what it
   looked like: `runner.py`'s two calls, `llm.py`, the tool-schema wrapper
   and the test fake; 243 tests unchanged in what they assert.
7. **What "correction" costs the agent.** Whether a correction on a `confirm`
   card should also produce a `remember` when it looks like a rule (*"Sunday ka
   150 = phal"*), or whether only the skill file learns it. Recommendation: the
   skill file; memory stays about the person.
