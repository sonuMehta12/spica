# Categorise — the nightly batch, and the skill file it reads

> Status: in progress — 2026-09-15. Supersedes **§5–§7** of
> `spec/paisa-categorise.md` (the engineering half: signals, tiers, skill file,
> tests). **§4 there stays owed and unchanged** — the phone's inbox, the 9pm
> review notification, monthly reconciliation — it needs a phone.
> Surface: backend. One function, two doors, no route.
> Source material: `spec/reference/product-log.md` — the August research diary
> the heuristics came from.

## The problem

The Aug-27 spec was written for a phone that captures notifications. The
backend it now lands in differs in five ways the spec does not know, and each
one changes a decision below:

1. **Rows arrive through the agent, already categorised once.** `log_payment`
   picks a category at 0.7 unless the user named one. The batch is the *second
   look*, with what the agent did not have at log time: the payee's history,
   the learned bands, the weekday, and every correction so far.
2. **82 of 109 rows have no payee.** They are the user's own words — *Rapido*,
   *Doodh*, *Beer - dost ko treat*. A dictionary keyed on the payee covers a
   quarter of the ledger.
3. **`confidence` is 0–1** in the schema; the spec says 0–100. `local_day`
   exists. Two of the spec's three "settle before code" items are settled by
   the code.
4. **The imported clock is a sentinel.** Noon UTC — 17:30 IST — means *day
   known, time unknown* (`spec/done/paisa-import.md`). Hour-of-day is a dead
   signal on 80 rows, and the spec's rules lean on it.
5. **`predictions` exists and has never been written.** The feedback half — a
   correction closes the prediction — is already inside `patch_transaction`.
   The learning has a write path and nothing to learn from.

## What it does

### One function, two doors

```
categorise(session, user, day=None, dry=False) -> Report
```

| Door | Who | When |
|---|---|---|
| `categorise_now(local_day?)` | the agent, as a tool | *"aaj ke payments dekh lo"* — on demand; the runner draws the cards |
| `scripts/categorise.py` | the terminal, and later a schedule | prints the report. **No cron is installed** — `spec/in-progress/schedules.md` is where "nightly" actually comes from |

**No `POST /categorise`, no `GET /skill-file`.** `agent.md` Phase C and
`api.md` said route; decided against 2026-09-15. A route is a third caller with
its own auth and error shape for a function that already has two, and the
phone, when it exists, talks to the agent. `GET /skill-file` returns when there
is a screen to show it on — the skill file is a *report* (below), so serving it
later is a read, not a design.

### The sub-agent

Tier 2 is a **second model call with a different system prompt** — the skill
file — no tools, one batch in, JSON out. It runs through the same seam
(`llm.respond()`, the Responses API, `store=false`); `llm.categorise()` stops
being a stub. Moved to the Responses API with everything else on 2026-09-15
and re-measured: 85% overall, 16/16 where it wrote, on the Aug 22 split — the
same as `chat.completions` within the noise of 48 rows. It is a
sub-agent in the only sense that matters: the main agent's prompt does not
grow, its cache prefix does not move, and the categoriser can be given a
cheaper or a stronger model without touching the conversation.

### Which rows

`kind = 'expense'`, not deleted, no open prediction, and one of:

- `confidence < 1` — an agent guess the user never confirmed;
- `category = 'Other'` — the user said *I don't know*.

**Rows the user categorised at 1.0 are ground truth and are never re-examined.**
Lent, borrowed, repayment and income are addressed by `kind`, which the user
states — the batch never changes `kind`. A row that *looks* like udhaar (round
thousands to a person, `kind = expense`) is proposed, with the reasoning, and
left to the user. An open prediction means the user was asked and has not
answered; silence is not a second question.

### Four tiers

| Tier | Costs | Fires when | Result |
|---|---|---|---|
| 0 · dictionary | ₹0 | the payee key has ≥ 3 prior rows, ≥ 80% in one category, and this amount is inside that payee's band | that category, 0.95 |
| 1 · rules | ₹0 | the scoring table lands ≥ 0.85 | that category |
| 2 · sub-agent | one call | everything left, in one batch | the model's guess, validated |
| 3 · the user | one tap | anything below 0.85 | `to_review`, state `proposed` |

**The payee key** is `counterparties.raw_name` when the row has one, else the
description lowercased with digits and punctuation stripped. *Rapido* logged
eleven times is a payee for this purpose; that is what makes the dictionary
cover the 82 rows, not the 27.

### What a tier may write

| The row | Prediction ≥ 0.85 | Prediction < 0.85 |
|---|---|---|
| `confidence < 1`, a different category | **written**: category and confidence | proposed |
| `confidence < 1`, **the same category** | **agreed**: confidence only | **agreed**: confidence only |
| `Other` at 1.0 | proposed | proposed |

A silent write goes over a guess, never over a fact. *Other* at 1.0 is the user
saying they did not know, which is a fact about the user, not the payment — so
the batch may propose but not decide.

**Agreement is not a question.** When the second look lands on the category the
row already has, the row is not asked about: its confidence moves up to the
better of the two estimates, the category does not move, and the amber dot
stays — only the user's own word makes a row certain. This is not the write
line being dodged; nothing is *overwritten*, and two independent estimates
agreeing is evidence about a number that only ever meant *how sure are we*.

The first live run is why this rule exists: five of nineteen questions were
*EMI → EMI?*, *Doctor → Health/Diet?*, *Rapido ride → Transport?*. A queue that
asks about rows it agrees with is a queue that stops being read.

**Description** is rewritten in exactly one case: when it *is* the raw payee
name (`description == counterparty_name`) — the notification shape, where the
whole point is turning *MOHAN LAL* into what the user calls it. A description
the user typed is their words and is never touched. The learned label is
`display_name` when the user set one, else the mode of that payee's past
descriptions.

**Every examined row gets a `predictions` row** — snapshot signals, tier,
model, guess, confidence, reasoning — whether or not anything was written. The
training set starts the first night.

Writes go through `writes.patch_transaction`, the same path the agent and the
UI use; the prediction is inserted **after** the patch, because the route
closes any open prediction it finds and the batch's own write must not read as
the user's correction.

### Signals — snapshotted, never recomputed

```
amount_paise, method
hour_of_day            null when the clock is the import sentinel
day_of_week, is_working_day        Mon–Fri; holidays when there is a table
payee_key, payee_seen_count
payee_band             {lo, hi, median} over the payee's prior rows, n ≥ 3
amount_in_payee_band
amount_band_match      the categories whose learned band holds this amount
has_bidirectional      counterparties.is_peer
in_contacts
mins_since_last_txn    null when either clock is the sentinel
last_txn_category
description_is_raw_payee
```

`motion_before` and `location_cluster` from the Aug spec are `null` until the
phone captures them; the JSONB takes them the day it does.

### Bands are learned, never typed

Per category, over labelled rows only (confidence 1.0): sort the amounts; a gap
wider than 40% of the range starts a new band; a category with fewer than 5
rows has no band. Per payee: `[lo, hi]` of its rows when it has 3 or more.

The Transport split the research found — 40–60 (toto) and 114–160 (Rapido)
with nothing between 61 and 113 — falls out of this on the research's nine
amounts, and that is the test. **On the live rows it no longer holds**: ₹90
and ₹260 rides since then close the gap, and the band is 40–160 with 260 on
its own. A finding from nine payments did not survive twenty-one; a hardcoded
band would still be asserting it. The algorithm is what is kept, not the split.

### Rules — Tier 1, starting weights

```
+0.50  payee seen ≥ 3, amount in the payee's band
+0.15  payee seen ≥ 3, amount outside it          the payee says where, not what
+0.30  amount inside exactly one category band
−0.30  …and that category's rows are ≥ 70% on working days, but today is not one
+0.10  within 15 min of the last payment             (both clocks known)
−0.20  payee never seen
```

The weekday gate is learned, not typed: the Aug spec said "commute band, not a
working day" and named the category; here the category is whichever one the
ledger shows to be a weekday habit, so it holds for a gym or a canteen too. The
category is the payee's dominant one, else the single band's; no candidate, no
Tier 1 result. **These are starting values.** The eval below tunes them;
the spec records the shape, not the numbers.

## The skill file

Two halves, one document, read by the sub-agent as its system prompt.

**Static — `backend/app/agent/skills/categorise.md`.** In the repo, hand-edited,
versioned. Who the reader is (a categoriser, not the agent). What the categories
in this ledger mean. The heuristics the August research produced, **as
principles**: a repeat payee with small varied amounts is a shop; a payee seen
for the first time at a commute-band amount on a working day is a ride, because
ride captains differ every time and shops repeat; a commute band means nothing
on a non-working day; round thousands to a person are not a purchase; a payee
tells you the place and not the purpose, so an amount far outside its band
lowers confidence; time of day only when the clock is real. The confidence
contract. The output contract. **Nothing about this user's specific rows.**

**Generated — at run time, from rows, never stored.** The live category list
with three sample descriptions each; learned payees (key, label, category, n,
band, weekday habit, last seen); learned bands; routines, only over rows whose
clock is real; and *rules learned from corrections* — every `predictions` row
where `actual_category ≠ pred_category`, phrased as the fact it is: *"MOHAN
SHYAM at ₹700 on Thu 27 Aug was Health/Diet · Gym fees, not the paan shop."*

Why the split is the house rule and not tidiness: a stored sentence about the
user's data starts lying when a row is deleted. The Aug spec's *"Sunday ka 150 =
phal"* is a user fact, so it is derived from the correction that taught it,
every night, and disappears if that correction is undone.

### Not in the main prompt

The agent's system prompt does **not** carry the skill file. Every turn would
pay its tokens for a document the batch reads once a night; the log-time guess
stays at 0.7 and the batch upgrades it a few hours later. This is now
measurable — `predictions` records how often the 0.7 guess was right — and the
day it is wrong often, the learned payees join layer 4 of the prompt as
`agent.md` drew it.

### The call, and what stands between it and the ledger

System = the skill file. User = the batch, compact JSON, one object per row:
`{id, amount, payee, seen, band, hour, weekday, working_day, mins_since_last,
last_category, description}`. Response = a JSON list,
`[{id, category, description | null, confidence, why}]`, nothing else.

Validation before anything is written, in this order:

1. Not parseable as that list → the whole batch falls to review at confidence 0.
2. `category` outside the live set → that prediction dropped; the row falls to review.
3. `confidence > 0.85` on a payee with `seen == 0` → capped at 0.84. A model is
   sure about a name it has never met; the cap is the spec's rule that a new
   payee is always asked about once.
4. `description` returned for a row whose description is not the raw payee →
   ignored.

### Review

`paisa_report(fields=["to_review"])` — specified in `agent-tools.md`, built
here — returns rows with an open prediction: id, amount, payee, and the guess
with its reasoning. The runner renders one `confirm` card per row, **state
`proposed`**, the guessed fields dotted. *Haan* → `correct_payment(id,
{category})`; the `Confirm` tap → confidence 1. Either way `patch_transaction`
closes the prediction — already built, already tested. One tap, nothing new to
learn.

The 9pm notification and the phone's inbox stay in `paisa-categorise.md` §4.

## The evaluation comes before the UI

`scripts/categorise_eval.py` — **dry**, writes nothing. Ground truth: expense
rows at confidence 1.0 and not *Other* — 78 rows on 2026-09-15. Split by a
cutoff date: the skill file and the bands are built from rows before it; every
row from it on is predicted blind. **The cutoff is chosen by row count, not by
the calendar.** `agent.md` said "the first 14 days"; the workbook's daily log
only begins mid-August, so 14 days is 11 labelled rows and a skill file that
knows nothing. Two cutoffs are run so one lucky split cannot pass the bar.
Per tier: how many rows it took, how many it got right. Overall: the share
decided without asking (≥ 0.85) and the accuracy of those.

Two bars, from `agent.md` Phase C, and the rule for each:

- **≥ 70% correct overall, or the skill-file approach is wrong** and a trained
  model moves up the list.
- **≥ 95% correct where confidence ≥ 0.85, or the threshold rises** until it is.

The numbers land under *Verified* below before a single card is drawn.

## Verified — 2026-09-15, `gpt-5.6-luna`, one call per run

| cutoff | learned from | predicted | dictionary | model | **overall** | **auto ≥ 0.85** | decided without asking |
|---|---|---|---|---|---|---|---|
| Aug 22 | 30 rows | 48 | 8/8 | 32/40 | **40/48 · 83%** | **14/14 · 100%** | 29% |
| Aug 25 | 44 rows | 34 | 7/7 | 18/27 | **25/34 · 74%** | **9/9 · 100%** | 26% |

Both bars cleared on both splits. **Twenty-three silent decisions, none
wrong** — the number that matters most, because a silent write is read as fact
tomorrow. The rules tier fired nothing above 0.85 on its own and deferred to
the model, as designed.

Every miss sat below 0.85 and would have been asked about. They are two kinds:

- **The user's own filing is split.** *Chai* → Khana/Grocery; *Chai + samosa
  (dost ke saath)* → Health/Diet; the model said Dost & Bahar. Four of the
  eight misses at the first cutoff. Not a model error — a category boundary
  the ledger itself does not draw consistently. The review card is the right
  answer here, and the correction becomes a rule the next night.
- **A category the training half had never seen.** EMI, Rent, Subscriptions,
  Ghar each have one labelled row, dated 13 Sep — in the test half at both
  cutoffs. They were not even in the allowed list, so the model chose the
  nearest (Bills/Recharge) at ≤ 0.84. In production the list is the whole
  ledger and this class largely disappears; it stays in the table because
  hiding it would flatter the number.

Free tiers alone (`--no-model`): 17–21% of rows decided, 100% precision, the
rest unanswered. That is the ₹0 floor the model call is bought above.

### Effort and model — same day, same splits

The user asked for `medium` everywhere on 2026-09-15. The provider allows it
here — this call has no tools — and refuses it for the agent on the same
endpoint (`agent.md` § Open). So the categoriser runs at `medium`
(`CATEGORISE_EFFORT`) and was measured on both candidate models; the `none`
rows above are the baseline.

| model @ effort | cutoff | model tier | **overall** | **auto ≥ 0.85** | decided without asking |
|---|---|---|---|---|---|
| luna @ none | Aug 22 | 32/40 | 83% | 14/14 | 29% |
| luna @ none | Aug 25 | 18/27 | 74% | 9/9 | 26% |
| **luna @ medium** | Aug 22 | 34/40 | **88%** | 14/14 | 29% |
| **luna @ medium** | Aug 25 | 21/27 | **82%** | 13/13 | 38% |
| terra @ medium | Aug 22 | 34/40 | 88% | 14/14 | 29% |
| terra @ medium | Aug 25 | 22/27 | 85% | 14/14 | 41% |

**Effort matters; the model does not, yet.** Medium is +5 and +8 points over
none on luna, and decides more rows without asking at the same 100%
precision. Terra and luna at medium are tied on the first split and one row
apart on the second — inside the noise of 34 rows. Across all six runs, **78
silent decisions, 78 right.**

The misses that remain are the same on every model: the chai/samosa boundary
the ledger draws inconsistently, and the four categories with one labelled
row in the test half. Neither is an intelligence problem; a smarter model
answers them with a *more confident wrong guess* — terra put EMI→Bills at
0.78–0.81 where luna said 0.48 with "no learned EMI category exists". The
lower number is the better answer, because it is the honest one.

**Decided:** the categoriser runs on **luna @ medium** — the agent's model,
one fewer moving part, better-calibrated where it is unsure. Terra is one
`.env` line (`CATEGORISE_MODEL=gpt-5.6-terra`) and every prediction row
carries `model@effort`, so a month of corrections can reopen this with data
rather than with a rerun of 34 rows.

### The first live run — 2026-09-15, 20 rows

| | |
|---|---|
| written silently | **0** |
| agreed (confidence raised, category untouched) | **5** |
| asked | **14** |
| categories changed without the user | **none** |

Two things this exposed, one fixed and one accepted:

**Fixed — agreement was being asked about.** Five of the nineteen questions
proposed no change. The rule above came from this run.

**Accepted — nothing wrote silently, and that is correct today.** Every pending
row is a first-time payee: no payee key yet has three labelled rows, so the
new-payee cap holds every prediction at 0.84, one hundredth under the write
line. The cap exists precisely so a name met once is asked about once, and on
a cold ledger that describes every row. It resolves itself as answers land —
each one is a labelled row, and a payee reaching three rows moves into the
dictionary tier at 0.95. The eval's 23-for-23 silent decisions were all on
payees with history, which is what the second week looks like.

The model's own calibration is visible here and worth keeping: *T-shirt* →
0.62 with *"clothing purchase has no matching learned category"*, and
₹1,100 *"Kharcha - kya tha?"* → 0.35. It is unsure exactly where the ledger
is thin.

## Decided against

- **A route.** Above.
- **Writing `default_category` on counterparties.** Derived from the payee's
  rows at run time; storing it is a sentence about the user's data, and
  `people.md` already reads the learned payee from rows.
- **Hashing payee names before the call** (`api.md`). One user, their own key,
  their own data — and the name is the only strong signal a new payee has.
  Returns the day the categoriser runs on a server that is not theirs. →
  `notes.md`.
- **Re-categorising rows the user set at 1.0.** Ground truth.
- **Changing `kind`.** The user states it; the batch proposes.
- **A taxonomy change** — *Bills*, `is_bill`, folding *Udhaar* out of
  `category`. `commitments.md`'s problem, argued there.
- **Training a model.** 83 labelled rows. The pairs are kept so it is possible
  later; the skill file is the model until then.
- **Tier 2 on the day's rows only.** All pending rows, capped at 40 a night —
  the backlog is small and the call is one either way.

## Definition of done

| # | Claim | How |
|---|---|---|
| 1 | The sentinel clock yields `hour_of_day: null`; a real clock yields the IST hour | test |
| 2 | Bands: the research's nine Transport amounts split 40–60 / 114–160; a flat list is one band; a category under 5 rows has none | test |
| 3 | Tier 0 fires in band and not out of band | test |
| 4 | Validation: bad list → all to review; unknown category dropped; unseen payee capped at 0.84 | test |
| 5 | Nothing below 0.85 writes a category; a 1.0 row is never rewritten; a user-typed description is never rewritten; `kind` is never touched | test |
| 5b | Agreement moves confidence only, never the category, never to 1.0, and is not asked about | test |
| 6 | Every examined row gets a prediction with snapshot signals; `correct_payment` afterwards closes it | test |
| 7 | `to_review` lists the open ones; `categorise_now` returns the report; the cards are `proposed` | test |
| 8 | A second run the same night examines nothing | test |
| 9 | The eval prints per-tier coverage and accuracy over the labelled rows | by hand — *Verified* above |

## Open

- The Tier 1 weights. On the current rows the rules tier never reaches 0.85 on
  its own — the dictionary takes the sure cases first and the rest need the
  model. Whether it earns a place at all is a question for a month of
  `predictions`.
- Whether *Other* at 1.0 should count in the eval's ground truth as *unknown*
  (excluded, as now) or as a class the model must refuse (a wrong category on
  an *Other* row is worse than leaving it).
