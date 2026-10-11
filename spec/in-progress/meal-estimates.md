# Meal estimates — the model values the plate, the ladder names it

> Status: built and verified 2026-09-19. Fills the stub `spec/diet-logging.md` §2
> admits to: *"Meals · portion → kcal, macros · **Partly — estimation is a
> stub**"*.
> Surface: backend. No new tool, no new route — `log_meal` is unchanged from
> the model's side.

## The problem

`log_meal` resolves each item against the dish and food library and reads the
macros off whatever it matched. Nothing else produces a number. So a plate the
library has never seen is logged at **0 kcal, 0 g protein** — which is the
dishonest-looking output the honesty rule exists to prevent:

```
"2 roti and 2 egg omletes"
    → Logged · macros unknown · Calories 0 · Protein 0
```

Three separate things are wrong, and each was verified against the live data
rather than argued:

**1. The library was never a nutrition authority.** `spec/done/dishes.md` line
28: *"A dish exists so the agent can suggest the next one"*, and *"your library
is only what you have a relationship with"* — **specified to be incomplete**.
Asking it to price every plate gives it a job its own spec declines.

**2. Its numbers have no stated provenance.** Of 41 `foods`, **11** say
`reference` and **30 say nothing at all**; `dishes` has no `nutrition_source`
column whatsoever. Preferring those over a fresh estimate means preferring an
unsourced number from an import over one made now with context.

**3. A dish is a fixed bundle, and a count multiplies the bundle.** Real rows:

| key | name | serving | kcal |
|---|---|---|---|
| `roti-sabzi` | 2 roti + seasonal sabzi | 2 roti + 1 katori | 310 |
| `anda-bhurji-roti` | 2 ande bhurji + 2 roti | 2 ande + 2 roti | 420 |

So *"3 roti"* × `roti-sabzi` is **6 rotis and 3 sabzis**. And
`anda-bhurji-roti` carries the alias *"omelette + roti"* — written so
suggestion could find it — so saying *"omelette"* can attach two rotis nobody
ate. The aliases are being read against their purpose.

## The split

The ladder is not deleted and not weakened. It answers a different question:

```
LADDER  →  IDENTITY   which foods, which pantry rows to spend.
                      Conservative on purpose: spending the wrong shelf
                      is a real error. Unchanged.

MODEL   →  WORTH      kcal, protein, carbs, fat, fibre for what was said.
                      Library rows and the user's own past portions go in
                      as CONTEXT — never applied blindly, never multiplied
                      by a count.
```

One conflation caused every failure above: the ladder answered *"what is
this?"* and the code took that as also answering *"what is it worth?"*
Identity is a database question. Worth is an estimation question.

## Measured before building

`scripts/estimate_eval.py`, 30 logged meals, one batched call each run. Ground
truth is the user's own tracker, so this is **agreement with how they already
count**, not absolute truth — which is the right target, because agreement is
what makes the switch invisible.

| | cold | calibrated on their own portions |
|---|---|---|
| kcal — median error | 22% | 22% |
| kcal — within 35% | 60% | **70%** |
| protein — median error | 18% | 18% |
| protein — mean error | 44% | **37%** |
| protein — within 35% | 57% | **67%** |
| fat — median error | 48% | **33%** |

**Calibration moves the tail, not the middle.** The model already knows what an
apple is; it does not know that *this* person's oats bowl is 690 kcal. Median
barely moves, catastrophes drop sharply. Since a day's totals are a **sum**,
the tail is what poisons them — so calibration is load-bearing, not a later
nicety.

Against the plates that fail today, judged by eye:

```
3 roti                    330 kcal   10 p   66 c    8 fibre
2 egg omelette            200 kcal   13 p    4 c    0 fibre
1 katori dal aur 2 roti   400 kcal   15 p   68 c   12 fibre
chai aur 2 biscuit        150 kcal    4 p   23 c    1 fibre
```

All sane, fibre included. **22% beats the 100% error of showing zero** — and is
nowhere near good enough to write silently. That is the whole interaction
design, and it is `diet-logging.md` §1's four steps unchanged:

> estimate → **state it** → let the user correct → store the pair as calibration

## What it does

### Estimating is not a rung — it runs after them

The ladder returns its lines as it does today. Then one model call values the
whole plate at once, with what the ladder found as context:

```
said: "2 roti and 2 egg omletes"
ladder: roti → Atta (whole wheat), needs_quantity
        egg omletes → unresolved
              ↓  both facts go to the model, with the user's recent portions
model: kcal 460, protein 23, carbs 52, fat 18, fibre 4
```

A library hit is **evidence, labelled as such** — *"this person has a dish
called X, serving '2 ande + 2 roti', 420 kcal"* — and the model decides whether
the plate in front of it is that thing. It is never multiplied by a count and
never applied because it matched.

### Nothing is ever silent

The write lands at `confidence 0.6` with the amber dot, and the reply states
the assumption in one line. `Confirm` raises it to 1.0 and clears every dot —
machinery that already exists and is already used by Paisa.

**Never zero, never a refusal.** A considered estimate is the point; an item so
vague that no estimate is possible (*"thoda"* with no food) is the `ask` case,
and asking stays available.

### The pair, and why it must be captured now

```sql
ALTER TABLE meal_logs ADD estimated_kcal INTEGER,
                          ADD estimated_protein_g NUMERIC,
                          ADD estimated_carbs_g NUMERIC,
                          ADD estimated_fat_g NUMERIC,
                          ADD estimated_fibre_g NUMERIC,
                          ADD corrected_at TIMESTAMPTZ;
ALTER TABLE meal_logs ADD fibre_g NUMERIC;          -- the only fibre column missing
ALTER TABLE dishes    ADD nutrition_source TEXT;    -- label | reference | estimate | llm
```

`estimated_*` is frozen at the moment of writing and never touched again.
`kcal` and the rest are what the user settled on. **The difference between them
is the error, recorded.**

This cannot be added later. Correct 420 → 186 without having saved 420 and the
guess is gone for ever — and it cannot be recomputed, because knowing what the
estimator *would have said* in September needs September's model and September's
version of the person's history, both of which have moved. `diet-logging.md` §2
says exactly this: *"keep every (estimated, corrected) pair — that is the
calibration set for portion defaults, and it cannot be backfilled."*

`patch_meal` stamps `corrected_at` when a macro changes, the same way
`patch_transaction` already stamps `predictions.corrected_at`.

### What may move a shelf, and who says how much

Subtraction was blind to certainty: any line with a food and a quantity spent,
including one the ladder had only found by trigram. **A fuzzy hit is a guess
about identity** — fine to draw on a card, fine to hand the estimator as
context, not fine to silently empty a shelf. `meal_items.rung` records how the
line was named and only `exact`, `alias` and `id` may spend. A new rung must be
added to that list, so forgetting the planned embedding rung costs a
subtraction rather than a wrong one.

`NULL` is not "uncertain" — it is *nobody guessed*: a client POSTing a
`food_id` is the caller naming the food, not the ladder matching a word. Those
spend.

### The model says how much, the database says what

Restricting the rung makes subtraction safer and leaves it mostly blind, which
the live data shows plainly:

| | |
|---|---|
| foods where a spoken **count** can become an amount | **6 of 41** |
| foods that always land on `needs_quantity` | **35 of 41** |
| dishes with a recipe (`dish_items`) to spend | 17 of 20 |

*"2 roti"* moves nothing, every time, because atta is sold in grams and nobody
knows what a roti weighs — and the ladder is right to refuse to invent it.

So the estimator, which is already reading the plate, also returns **what it
was made of**:

```json
"ingredients": [{"food": "atta", "grams": 80}, {"food": "eggs", "grams": 100}]
```

**Names, never ids.** Each name is resolved server-side through the same
matcher, accepted only at `exact` or `alias`, and converted into that food's
own unit — 100 g of eggs becomes 2 pieces via `grams_per_unit`. An ingredient
the model invents simply fails to resolve and spends nothing; it can never
reach a shelf the person does not have. Identity stays a database lookup; only
the **quantity** comes from the model, which is exactly the part the
deterministic path openly declines to guess.

When the model returns usable ingredients they are the meal's lines. When it
does not, the ladder's lines are, as before — one source, never both, so
nothing is subtracted twice.

**Two costs, accepted deliberately:**

1. **A ledger stops being reproducible.** The same plate twice may take 75 g of
   atta once and 85 g the next. Today it takes *nothing*, which is also wrong
   and merely quieter. `is_tracked` bounds it to food actually bought, and
   `unspend()` reverses it on correction or delete.
2. **The pantry gains a dependency on a model call.** With the model down there
   is no subtraction, where the deterministic path still handled its six foods.
   The fallback keeps that path, so the loss is the new coverage, not the old.

### Two stores, two jobs

| | `dishes` | the calibration pairs |
|---|---|---|
| **holds** | things worth suggesting | what this person's portions are worth |
| **grows by** | the user's ★, deliberately | automatically, on every correction |
| **shape** | curated, sparse | dense, messy, fine |
| **feeds** | the suggestion model | the estimator's context |

*"KitKat (2 bars)"* must teach the estimator that a KitKat is 186 kcal, and
must **never** appear when the agent suggests dinner. Promoting corrections
into `dishes` would fill the menu with `Tofu (thoda)` and `chai aur 2 biscuit`
— the mirror of the mistake this spec is fixing, and the thing `dishes.md`
warns about: *"inventing one is how a library fills with typos."*

**`keep_dish` is unchanged.** The user decides what enters the library, by
starring it. The machine never does.

### The skill file

Two halves, like `categorise.md` — the same architecture, second instance.

**Static**, `app/agent/skills/estimate.md`, hand-edited: how to read Indian
food. A katori is ~150 g. *Ghar ka* means household oil, not restaurant. A
count means pieces — *"3 roti"* is three. Calibrated over generous, because a
wrong number the person believes is the failure that matters.

**Generated**, at call time from rows, never stored: their most recent
corrected pairs, their typical portions, and any library rows the ladder
matched this turn. A stored sentence about their data would start lying the day
a row changed — the house rule.

### No cron, and that is not an oversight

Paisa needs a nightly pass because it re-examines rows written hours earlier.
Diet estimates **at the moment of logging** and can read everything that exists
right then — so a correction made at 2pm is already in the 8pm plate's context.
There is nothing to schedule.

## Decided against

- **Keeping library lookup as a first branch.** It looks safe and is not: an
  unsourced number and a bundle-multiplying `servings` are how the zeros and
  the phantom rotis happened. The library informs the estimate instead.
- **Promoting corrections into `dishes` automatically.** Above.
- **A separate `calibration` table.** The pair belongs on the row it describes;
  a second table would need the same keys and could drift from it.
- **Estimating per item and summing.** The plate is valued whole: *"chicken
  fried rice jisme chicken na ke barabar thi"* is one judgement, and splitting
  it loses the clause that matters.

## Definition of done

| # | Claim | How |
|---|---|---|
| 1 | An unmatched plate gets non-zero macros, at `confidence < 1`, never silent | test |
| 2 | `estimated_*` is written at log time and never changed by a correction | test |
| 3 | `patch_meal` stamps `corrected_at` when a macro changes, and not otherwise | test |
| 4 | Fibre is estimated and stored | test |
| 5 | A correction reaches the next estimate's context | test |
| 6 | Correcting a meal writes nothing to `dishes` | test |
| 7 | The ladder still resolves identity and the pantry still spends | existing tests stay green |
| 8 | A model that returns nonsense, or fails, does not lose the log | test |
| 8a | A `similar` line never spends; `exact`, `alias` and a NULL rung do | test |
| 8b | An ingredient name that resolves at `exact`/`alias` spends, in the food's own unit; an invented one spends nothing | test |
| 8c | Ingredients and ladder lines never both spend the same meal | test |
| 9 | The whole loop: log → wrong number → correct → next estimate is better | by hand, `scripts/smoke_estimates.py` — below |

All of 1–8 are green: `backend/tests/test_meal_estimates.py`, 12 tests.

## Verified — the live loop, 2026-09-19

`scripts/smoke_estimates.py` against the real model and the real ledger, which
writes its rows, checks them, and deletes them again.

```
I eat 2 roti and 2 egg omletes      409 kcal  20 p  6 fibre  conf 0.6
    assumed: 2 roti ~40g each; omelette cooked with ~1 tsp oil
3 roti                              330 kcal  10 p  9 fibre
    assumed: 3 medium rotis, ~30g atta each          ← not six, from a bundle
chicken fried rice jisme chicken
  na ke barabar thi                 470 kcal   8 p            ← read the clause
Whey shake                          120 kcal  24 p            ← library's own number
```

Every one of those was **0 kcal, 0 g protein** before. The qualifier case is
the skill file working: *"chicken na ke barabar"* took the protein to 8 g while
the calories stayed where a plate of fried rice belongs.

Then the loop:

```
correct 409 → 310      estimate still reads 409, corrected_at set
next estimate's context:
    "I eat 2 roti and 2 egg omletes: 310 kcal, 18 g protein (we had said 409)"
same plate re-logged →  310 kcal
```

`dishes` unchanged at 20 throughout, and the ledger came back to 145 meals with
no orphaned `meal_items` or `pantry_moves`.

**One fix this run found.** *"I eat 2 roti"* left the ladder unresolved — its
`NOISE` pattern stripped Hinglish filler (*khaya*, *maine*) but no English, so
the count never reached the quantity parser and **the pantry did not spend the
atta**. The estimate was right and the identity was wrong, which is exactly the
split this spec draws: two jobs, two failure modes. English filler is stripped
now.

## Open

- **Proposing a dish update after repeated corrections.** *"Tumhara Malai
  paneer teen baar ~420 nikla hai, dish update kar dun?"* Agreed in principle,
  and deliberately not in this build: it needs correction history that will not
  exist until this ships. One correction is a bigger plate that day; three in
  the same direction is a fact about the dish. Ask-before-writing, as habits do.
- **Whether `confidence` should carry the model's own certainty** rather than a
  flat 0.6. Worth revisiting once the corrected pairs show whether its
  self-reported confidence means anything.
