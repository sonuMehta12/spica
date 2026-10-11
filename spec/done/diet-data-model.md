# Diet + health — data model

> Built and verified — 15/15 checks green against the imported data.
> Source of truth for the data: `Healthy_Eating_Tracker.xlsx`, 4–27 Aug 2026.
> Reads from: `spec/done/paisa-data-model.md`, `spec/diet-logging.md`, `spec/workout.md`

## Scope

Food and movement in one schema. They are one card, one streak and one question
— *did I look after myself today* — so splitting them costs two migrations to
answer it.

**In:** meals, macros, habits, the recipe and exercise libraries, the pantry.
**Out:** money (Paisa owns it), sets and reps, the suggestion feedback loop.
Both deferred with reasons in `spec/notes.md`.

## What the workbook contains

| Sheet | Rows | Use |
|---|---|---|
| Meal Log | 119 | the ledger — one row per meal |
| Daily Summary | 24 | entirely derived, except weight and habit columns |
| Portion Defaults | 37 | phrase → grams |
| Nutrition Ref | 14 | per-100 g values |
| Recipes | 12 | dish templates |
| Purchases | 23 | what came into the house |
| Pantry Stock / Staples | 15 / 25 | what is at home |
| Profile & Targets | — | daily macro targets |

Facts the schema has to accommodate:

- **119 meal rows over 23 days, 98 distinct dishes.** `Daily Summary` is a
  formula sheet — the meal is the ledger row, the day is derived.
- **12 meal slots**, and `Grazing` was invented mid-experiment. An enum written
  before the experiment would have rejected it.
- **`Used so far` was filled 0 times in 24 days** — but the user stated
  consumption in *conversation* whenever a suggested recipe was cooked
  (*"is recipe ke hisaab se ingredient kam kar do"*). Inventory is never
  maintained; consumption is stated as a side effect of cooking.
- **Water answered 1/24; last-meal-time and post-meal-walk 0/24.** These went
  unanswered because the user already knows them — they are advice, not
  questions. Weight is 1/24 because it is a weekly question, not a daily one.
- **7 Aug logged breakfast only (580 kcal); 16 Aug logged nothing (0 kcal).**
  Both render as the day's intake, and both are false.
- **KitKat estimated at 180 kcal, label said 93.** Estimated and label-read
  values are not equally trustworthy.
- **Three portion corrections** — sattu 21→7 g, tofu 200→50 g, dahi 200→100 g.
- **Whey was in the pantry two days before it was delivered.**

---

## `...envelope` in the DDL below

Every table carries the same six columns, written once here rather than repeated
in each block:

```sql
id         TEXT PRIMARY KEY,      -- ULID: sortable by creation time, opaque
created_at TIMESTAMPTZ NOT NULL,
updated_at TIMESTAMPTZ NOT NULL,  -- the sync cursor reads this
deleted_at TIMESTAMPTZ            -- soft delete, so sync can see a removal
```

Same envelope as `spec/done/paisa-data-model.md`. A hard `DELETE` would vanish
without trace, and a client syncing on `updated_at` would never learn the row
was gone.

**`REFERENCES` means a foreign key.** `forked_from_id TEXT REFERENCES foods(id)`
says: this column holds the `id` of another row *in the same `foods` table*, and
Postgres refuses to store an id that does not exist there. It is how a forked
recipe points back at the Cortex one it came from.

## The reference library

Shipped content and the user's own live in the same tables — one table per kind,
never a separate one for the user.

**Who made it is a foreign key, not an enum.** `created_by_id` is NULL for
anything Cortex ships and holds the user's id for anything they wrote. This is
strictly more information than an `origin` column: *"all the recipes I created"*
becomes a `WHERE`, and *"who wrote this one"* has an answer at all.

```sql
created_by_id TEXT REFERENCES profile(id)   -- NULL = Cortex shipped it
```

**`foods` has neither column.** A food's nutrition is objective — 100 g of tofu
has the same protein whoever logs it — so there is nothing for a user to own. If
someone photographs a label, the app reads it and the food becomes everyone's.

That is also the privacy-preserving choice, and it is the stronger reason: a
`created_by` on `foods` would record **who eats what**, which is exactly the kind
of trail this app is not supposed to leave. Recipes are something you made;
foods are a fact about the world.

**Editing a Cortex row forks it** rather than changing it. Worked example:

> Cortex ships **Rajma chawal** — rajma 80 g, 695 kcal, 24 g protein.
> You always make it with extra rajma, so you change it to 110 g.
>
> *Edited in place:* three weeks later the app ships a corrected Rajma chawal —
> the protein figure was wrong. Your 110 g is overwritten. Nothing tells you.
>
> *Forked:* your edit writes a **new row**, `origin = 'user'`,
> `forked_from_id` → the Cortex row. Cortex keeps updating its copy; yours never
> moves. Your meals point at yours.

The cost is two recipes with the same name in search, and the fix is to hide the
Cortex original once a fork of it exists.

This is the rule the ledger already follows — a correction is a new row that
supersedes the old one, never an edit — applied to reference data.

**`visibility` is the user's to set,** and only on things they made. A recipe or
exercise you invented stays private unless you publish it. Cortex's own rows are
public by definition and carry no such choice.

### `foods`

An ingredient or a packaged product. Per 100 g, which is how both labels and the
reference sheet already express it.

```sql
CREATE TABLE foods (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  -- The app's data is English, the user speaks Hindi: 'dahi' and 'Curd' are one
  -- food. Without this every portion default fails to resolve.
  aliases         TEXT[] NOT NULL DEFAULT '{}',
  brand           TEXT,
  category        TEXT,                       -- Pulses, Dairy, Protein, Treat
  -- Nullable: you can own a thing before you know its macros. 11 of the
  -- workbook's 40 foods have nutrition; the other 29 are still real.
  kcal_100g       INTEGER,
  protein_g_100g  NUMERIC(6,1),               -- exact decimal, not float
  carbs_g_100g    NUMERIC(6,1),
  fat_g_100g      NUMERIC(6,1),
  fibre_g_100g    NUMERIC(6,1),
  -- A label-read value and a guessed one must not render the same.
  nutrition_source TEXT CHECK (nutrition_source IN ('label','reference','estimate')),
  confidence      REAL,
  -- No created_by and no visibility. Nutrition is a fact, not a possession, and
  -- recording who added a food would record who eats it.
  forked_from_id  TEXT REFERENCES foods(id),
  ...envelope
);
```

**`NUMERIC`, not `REAL` and not integer minor units.** Labels carry one decimal
— KitKat is 6.6 g of protein per 100 g — and the app sums macros constantly, so
binary float would drift. `NUMERIC` is exact decimal arithmetic in Postgres and
stores `15.2` as `15.2`.

Paise work for money because a paisa is a unit people actually use. There is no
equivalent for grams, so scaling to integers would mean inventing one, and every
reader would have to decode it. The rule is the same as elsewhere: prefer the
representation that needs no explanation.

### `measures`

**Only true units of measurement — seven rows.** A spoken quantity resolved to
grams, with no nutrition of its own:

```
1 katori · 1 bada katora · 1 glass · 1 chammach · 1 chhoti chammach ·
1 muththi · 1 chutki
```

```sql
CREATE TABLE measures (
  id             TEXT PRIMARY KEY,
  phrase         TEXT NOT NULL,               -- 'katori', 'muththi', 'chammach'
  grams          INTEGER NOT NULL,
  created_by_id  TEXT,                        -- NULL = Cortex shipped it
  forked_from_id TEXT REFERENCES measures(id),
  ...envelope
);
-- One 'katori' per definer, not one in the world: your katori may be 200 g.
CREATE UNIQUE INDEX ON measures (phrase, COALESCE(created_by_id, ''));
```

**An earlier draft had 37 rows here, and it was wrong.** The portion sheet has
its own divider, and only the seven rows below it are measurement — they carry
zero kcal because they are not food. The 25 rows above it look like this:

```
1 katori dal     → 30 g sukhi dal + tadka    130 kcal   7 g
1 katori chawal  → 150 g pakka hua           195 kcal   4 g
Office thali     → roti/chawal + dal + sabzi 650 kcal  18 g
```

Those are not measurements. They are **typical servings of a dish, with the
answer already worked out** — which is exactly `recipes`. They move there.

**This is what solves cooked versus raw.** Looking up "dal" in `foods` gives per
100 g of *dry* dal — 343 kcal, 24 g protein. Multiplying that by a katori's 150 g
gives 515 kcal and 36 g, against a truth of roughly 130 and 7. Nearly four times
wrong.

The workbook never made that mistake, because it never looked anything up: it
wrote down what a katori of dal contains. A cooked dish is a recipe with stored
nutrition; a raw ingredient is a food with per-100 g values. The two never get
confused because they live in different tables.

### `recipes` and `recipe_items`

```sql
CREATE TABLE recipes (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,              -- 'Dal (1 katori)', 'Office thali'
  -- What a person might say for this. 'dal', 'daal', 'arhar ki dal' all resolve
  -- to one recipe, which is what makes free-text logging land somewhere.
  aliases         TEXT[] NOT NULL DEFAULT '{}',
  meal_type       TEXT,                       -- free text, see meal_logs.meal_type
  serving_label   TEXT,                       -- '1 katori', '1 plate', '1 roti'
  kcal            INTEGER NOT NULL,           -- per serving
  protein_g      NUMERIC(6,1) NOT NULL,
  carbs_g        NUMERIC(6,1) NOT NULL,
  fat_g          NUMERIC(6,1) NOT NULL,
  prep_minutes    INTEGER,
  -- Sprouts need 24 hours. A plan made this evening has to know that.
  needs_prep_ahead BOOLEAN NOT NULL DEFAULT FALSE,
  steps           TEXT,                       -- how to cook it, markdown
  image_url       TEXT,
  confidence      REAL NOT NULL DEFAULT 1.0,
  created_by_id   TEXT REFERENCES profile(id),  -- NULL = Cortex shipped it
  visibility      TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','public')),
  forked_from_id  TEXT REFERENCES recipes(id),
  ...envelope
);

CREATE TABLE recipe_items (
  id        TEXT PRIMARY KEY,
  recipe_id TEXT NOT NULL REFERENCES recipes(id),
  -- Exactly one of these. A component is another recipe: 'Ghar ka dinner' is
  -- 2 roti + dal + sabzi, and without nesting the commonest Indian dinner
  -- decrements nothing from the pantry.
  food_id             TEXT REFERENCES foods(id),
  component_recipe_id TEXT REFERENCES recipes(id),
  -- Grams of that food in ONE serving, as bought — dry weight for dal and oats,
  -- because that is what leaves the pantry. NULL for a component.
  grams     INTEGER,
  CHECK (num_nonnulls(food_id, component_recipe_id) = 1)
);
```

**Recipe nutrition is stored, not computed from items.** `Office thali — 650
kcal, 18 g` has no ingredient breakdown and never will; the plate arrives full.
Computing only from items would refuse to record it. Storing it is also what lets
a *cooked* dish carry honest numbers when its ingredients are measured dry.

**Sabzi does not need a recipe per vegetable.** One generic `Sabzi (1 katori)` at
140 kcal covers most of them, because home sabzi's calories are dominated by oil,
not by the vegetable — the workbook's own note says *"tel ghar me hamesha zyada
hota hai"*. A specific sabzi earns its own row only when it genuinely differs:
aloo is carb-heavy, palak is not. Estimate, not precision.

**`recipe_items` exists for the pantry, not the macros.** It is what lets a
logged meal decrement stock. Optional, so the thali stays loggable.

### `exercises`

A library for suggesting, not for recording. Answering *"aaj kya workout karu?"*
requires knowing what exists — the same reason `recipes` exists.

```sql
CREATE TABLE exercises (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,              -- 'Bench press', 'Surya namaskar'
  muscle_group    TEXT,                       -- so push and pull can be balanced
  equipment       TEXT,                       -- includes 'none', or it only works on gym days
  typical_minutes INTEGER,
  created_by_id   TEXT REFERENCES profile(id),  -- NULL = Cortex shipped it
  visibility      TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','public')),
  forked_from_id  TEXT REFERENCES exercises(id),
  ...envelope
);
```

**`typical_minutes` is load-bearing.** Two gym sessions in ten days, and the
barrier was time, not food. A library that cannot answer *"मेरे पास 20 मिनट हैं"*
repeats that failure.

---

## How a sentence becomes macros

The division of labour, because it is the part most easily got wrong: **the model
reads language, the tables hold numbers.**

```
"do roti aur ek katori dal"
  ↓  model parses            [{qty 2, unit —,      thing "roti"},
                              {qty 1, unit katori, thing "dal"}]
  ↓  match thing             recipes.aliases first, then foods.name
  ↓  recipe matched          multiply the stored per-serving macros
     food matched            measures resolves the unit to grams, then per-100 g
  ↓  no match                the model estimates, row marked `· andaaza`
```

**Recipes are matched before foods, and that is what keeps cooked food honest.**
"dal" hits the recipe `Dal (1 katori)` — 130 kcal — rather than the raw food
entry at 343 kcal per 100 g. `measures` only ever applies to a raw ingredient,
where per-100 g is the right basis.

**The model is not asked to invent numbers it can look up.** Its job is parsing
and matching — turning *"thoda sa seeds daale"* into `{qty 1, unit chutki, thing
"sunflower seeds"}`. Estimating grams fresh each time would make the measuring
instrument move, so a protein figure dropping from 135 to 90 could not be read as
*you ate differently*.

**Where the model must guess, it guesses once and gets corrected.** Fried dal or
plain dal, thick or thin — the app takes the default and marks the row rather
than interrogating. The workbook proves both halves: three corrections happened
in 24 days when an estimate was badly off, and every habit question asked daily
went unanswered. *"Estimate tabhi correct karta hai jab bahut off ho"* — so
defaulting plus a correction path beats asking.

## The ledger

### `meal_logs`

```sql
CREATE TABLE meal_logs (
  id            TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL,
  occurred_at   TIMESTAMPTZ NOT NULL,
  local_day     DATE NOT NULL,
  meal_type     TEXT NOT NULL,                -- 'Breakfast', 'Snack', 'Grazing' — free text
  dish          TEXT NOT NULL,
  recipe_id     TEXT REFERENCES recipes(id),  -- NULL for food eaten out
  ingredients   TEXT,                         -- as said: 'Rolled oats 60 g, Milk ~150 ml'
  kcal          INTEGER NOT NULL,
  protein_g    NUMERIC(6,1) NOT NULL,
  carbs_g      NUMERIC(6,1) NOT NULL,
  fat_g        NUMERIC(6,1) NOT NULL,
  cooked_home   BOOLEAN,
  source        TEXT NOT NULL CHECK (source IN ('manual','photo')),
  confidence    REAL NOT NULL DEFAULT 1.0,
  note          TEXT,
  tags          TEXT[] NOT NULL DEFAULT '{}',
  supersedes_id TEXT REFERENCES meal_logs(id),
  dedupe_key    TEXT,
  ...envelope
);
-- Two users can receive the same notification text; dedupe is per person.
CREATE UNIQUE INDEX ON meal_logs (user_id, dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX ON meal_logs (user_id, local_day);
```

**`meal_type` is which meal it was** — Breakfast, Lunch, Dinner, Snack, Drinks,
Pre-workout. **Free text, not an enum.** Twelve values appear in 24 days and
`Grazing` was invented mid-experiment; an enum written beforehand would have
rejected it. Same rule as `exercises.name` — the agent must not refuse to log
what happened.

**Named `meal_logs`, not `meals`.** A row is what you ate on a day, not a meal in
the abstract — the abstract one is a `recipe`. It pairs with `habit_logs`, and
the pair is the whole ledger.

**Macros are on the row, not looked up.** They are what was believed at log time.
Fixing a portion later supersedes the row rather than silently changing history.

### `habits` and `habit_logs`

One model for everything that is a **choice** — smoking, beer, workout, running,
meditation, fasting. Modelling them separately would be six tables for one
question.

Sleep is not one of them, and neither is water. See below.

```sql
CREATE TABLE habits (
  id        TEXT PRIMARY KEY,
  user_id   TEXT NOT NULL,                    -- your habits, not a shared list
  name      TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('build','break')),
  unit      TEXT,                             -- 'minutes', 'km', 'hours', NULL to just count
  ...envelope
);

CREATE TABLE habit_logs (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL,
  habit_id    TEXT NOT NULL REFERENCES habits(id),
  occurred_at TIMESTAMPTZ NOT NULL,
  local_day   DATE NOT NULL,
  amount      REAL,                           -- NULL = it happened, that is all
  note        TEXT,                           -- 'Workout B (back)'
  source      TEXT NOT NULL CHECK (source IN ('manual','photo')),
  ...envelope
);
CREATE INDEX ON habit_logs (user_id, local_day);
```

**A skipped day is not a row.** Absence is the rest day, and the strip counts
done rather than marking missed. This only works because every habit here is
voluntary: a blank day means *it did not happen*, which is true.

**Fasting is a habit.** It is the row that explains an empty day — a day with no
meals and a fasting log is complete, not a gap.

**This makes the workbook's sharpest finding a query.** *Beer → cigarette, 4
times out of 5* is two habit logs sharing a `local_day`. No correlation code.

### `days`

Only what cannot be derived from meals and habits.

```sql
CREATE TABLE days (
  id           TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL,
  local_day    DATE NOT NULL,
  -- UNIQUE (user_id, local_day): one row per person per day. A DATE primary
  -- key would let exactly one person exist — the first single-user bug the
  -- multi-user audit caught.
  -- NULL = unknown. FALSE = the user said there is more. TRUE = that was the day.
  log_complete BOOLEAN,
  weight_kg    REAL,                          -- weekly, not daily
  sleep_hours  REAL,
  note         TEXT,
  UNIQUE (user_id, local_day),
  ...envelope
);
```

**Sleep lives here, not in `habits`.** Sleeping is not a choice you make on a
given day — it happens whether or not it is logged, so a blank is *unreported*,
not *did not happen*. That is the same asymmetry that separates meals from
habits, and it puts sleep on the same side as weight: a measurement of the day,
nullable, asked occasionally.

**`log_complete` is the fix for the worst bug in the workbook.** 7 Aug shows 580
kcal because only breakfast was logged; 16 Aug shows 0 because nothing was. Both
render as the day's intake. Without this column the app cannot tell a fast from
a failure, and *"jo yaad hi nahi"* has no diet equivalent.

The column only records the answer. How the app *gets* the answer — a nudge or
two, then the agent raising it in ordinary conversation — is in `spec/notes.md`.

---

## The house

### `pantry` and `pantry_moves`

Everything at home that could become a meal, and every change to it. Two tables
because they answer different questions: `pantry` is *what is here and when do I
re-buy it*; `pantry_moves` is *how it got that way*.

```sql
CREATE TABLE pantry (
  id              TEXT PRIMARY KEY,
  user_id         TEXT NOT NULL,
  food_id         TEXT NOT NULL REFERENCES foods(id),
  reorder_at_g    INTEGER,        -- below this, it goes on the list
  -- Curd: 'buy every 2-3 days'. Tofu: 'use within ~5 days of opening'.
  -- Quantity alone is not enough — 780 g of curd bought two weeks ago is not
  -- 780 g of curd.
  shelf_life_days INTEGER,
  note            TEXT,
  -- One tofu row per HOUSE, not per world. Plain UNIQUE(food_id) was the
  -- second single-user bug: the first user to own tofu would block everyone.
  UNIQUE (user_id, food_id),
  ...envelope
);

CREATE TABLE pantry_moves (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL,
  food_id     TEXT NOT NULL REFERENCES foods(id),
  local_day   DATE NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  -- Signed. +400 when tofu arrives, -50 when a recipe spends it.
  quantity_g  INTEGER NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN
                ('purchase','opening','consumption','correction','waste')),
  -- What caused it, so deleting the meal takes its consumption with it.
  meal_log_id TEXT REFERENCES meal_logs(id),
  note        TEXT,
  dedupe_key  TEXT,
  ...envelope
);
CREATE UNIQUE INDEX ON pantry_moves (user_id, dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX ON pantry_moves (user_id, food_id, local_day);
```

**Not called `purchases`.** The app also handles payments, so an unqualified
`purchases` reads like money. And stock does not only arrive by being bought —
the family's atta, food carried from home, a gift. `pantry_moves` says what it
is: things entering and leaving the house.

### The quantity is a sum, not a column

```
what is left  =  SUM(pantry_moves.quantity_g) for that food
```

Tofu, from the real data:

```
04 Aug  purchase     +400
11 Aug  purchase     +200
22 Aug  purchase     +400
        consumption  -260   (seven meals used tofu)
                     ────
                      740   ← matches the workbook exactly
```

**Why a sum and not a stored counter.** A counter must be adjusted by every path
that touches stock, and it silently drifts the first time one forgets — delete a
meal and the ingredients it spent stay deducted forever. A sum cannot drift:
delete the meal, its `consumption` rows go with it, and the number is right
again. Same rule the app already applies to card notes.

**A negative total is a feature.** Importing the real data, curd reaches −40 g
on 13 Aug. That is impossible — and it is the ledger reporting that something is
missing, which turns out to be true: the Staples sheet says curd *"ghar par roz
aati hai, kharidne ki zaroorat nahi"*, so it arrives daily and was never recorded
as arriving. A stored counter would have shown a confident wrong number and said
nothing.

**Shelf life makes a quantity untrustworthy, not zero.** Curd bought on 11 Aug
with a 3-day life is not curd on the 27th, so arithmetic alone overstates what is
in the house. But the app must **not** write a `waste` move on its own — nobody
observed that spoilage, and if it was actually finished in time the write-off is
a lie. Instead the age makes the row *stale*: it goes on the shopping list, and
the agent asks once — *"dahi 16 din purani hai, bachi hai ya khatam?"* The answer
becomes a `waste` or `correction` move. An observation, never an assumption.

**A stock-take is just another move.** The workbook's `Remaining` column is the
user stating what is actually there, exactly as `balance_checks` states the bank
balance in Paisa. It enters as an `opening` move and everything after counts from
there, so a drifted estimate is corrected by observation rather than by
recomputing history.

`opening` is that stock-take, and it is **not** a running total that other moves
get written into. It is one observation — *I looked, there is 740 g* — and the
quantity reads as the latest `opening` plus every move after it. Same semantics
as `balance_checks` in Paisa.

**Present but unmeasurable is a pantry row with no moves.** No arithmetic is
attempted for the family's atta or the spices. A row whose moves sum to zero is
*finished*; a row with no moves at all is *here, amount unknown*. The two must
not look alike.

### How consumption gets recorded

This is already the user's behaviour, so nothing new is being asked for:

1. A meal is logged against a recipe — *"aaj soya keema banaya"*
2. `recipe_items` says one serving spends 60 g of soya chunks
3. The agent writes a `consumption` move of −60 g, carrying the meal's id
4. It says what it did, so a wrong assumption is corrected in the same breath

Meals with no recipe — the office thali, food eaten out — spend nothing, which is
correct: none of it came from the house.

### Generating the shopping list

Still no table. Three conditions, any one of which puts a food on the list:

```sql
SELECT f.name,
       SUM(m.quantity_g) AS left_g,
       MAX(m.local_day) FILTER (WHERE m.kind = 'purchase') AS last_bought
FROM pantry p
JOIN foods f             ON f.id = p.food_id
LEFT JOIN pantry_moves m ON m.food_id = p.food_id
GROUP BY f.name, p.reorder_at_g, p.shelf_life_days
HAVING SUM(m.quantity_g) <= p.reorder_at_g                      -- running out
    OR SUM(m.quantity_g) IS NULL                                -- never tracked
    OR MAX(m.local_day) FILTER (WHERE m.kind = 'purchase')
         < CURRENT_DATE - p.shelf_life_days;                    -- gone off
```

`LEFT JOIN` matters: a food with no moves disappears from an inner join, and
those are exactly the staples that also run out.

Ranking — what the coming week's suggested recipes need, what is cheapest per
gram of protein — is deliberately not decided here. The query above is the part
that has to be right.

### Whose row is this: `user_id`

The app is being built for many users — the target is 10,000-plus, not one — so
every personal table carries `user_id` from day one. The split falls out of the
ownership decision already made:

| | |
|---|---|
| **Shared, no `user_id`** | `foods`, and everything Cortex ships. Nutrition is a fact about the world, and a `user_id` here would record who eats what |
| **Yours, `user_id` on the row** | `meal_logs`, `habit_logs`, `habits`, `days`, `pantry`, `pantry_moves` |
| **Yours but shareable** | recipes, exercises and measures you wrote, through `created_by_id` + `visibility` |

**The audit this section came from.** Designing as if for one user leaves traps
that only spring when the second user signs up. Walking every table with
"what happens when two people use this?" found six:

1. `days` had `local_day` as its primary key — one row per date *in the world*.
   The second user could not log a day. Now `UNIQUE (user_id, local_day)`.
2. `pantry` had `food_id UNIQUE` — the first person to own tofu would block
   everyone else. Now `UNIQUE (user_id, food_id)`.
3. `dedupe_key` was globally unique, but two users can receive the *same
   notification text* on the same day. Dedupe is per person:
   `UNIQUE (user_id, dedupe_key)`.
4. `measures.phrase` was unique in the world — but your katori may be 200 g.
   Now unique per definer.
5. Every index on a personal table now leads with `user_id`
   (`(user_id, local_day)`, not `(local_day)`), so a query for one person's
   week never scans everyone's rows.
6. **The Paisa tables have all of these problems too** — built before this
   decision, single-user throughout: `counterparties.raw_name` UNIQUE,
   `transactions.dedupe_key` UNIQUE, no `user_id` anywhere, every index
   personal-blind. They get the same retrofit in the same migration set,
   while the only data in them is one user's and the fix is cheap.

**Enforced by the database, not by remembering.** Postgres row-level security
attaches the `user_id` filter to the table itself, so a query that forgets its
`WHERE` returns nothing rather than everyone's rows. Forgetting is the single
most common way multi-tenant apps leak, and this makes it structurally
impossible rather than merely discouraged.

**`user_id` stays a plain TEXT column until after kaam**, when the profile /
users table is designed and it becomes a real foreign key. The import fills it
with a constant. Auth — how a request proves which user it is — is part of that
later work; the schema just has to be ready, and now it is.

### Scale sanity

Rough arithmetic at the target scale, using the real per-user rates from the
24-day workbook (≈5 meals, ≈3.5 pantry moves, ≈0.6 habit logs per day):

```
            per user/year      10,000 users       100,000 users
meal_logs        ~1,800            18M/year          180M/year
pantry_moves     ~1,250            12M/year          125M/year
```

Postgres handles hundreds of millions of rows on one machine when every query
is `(user_id, …)`-indexed — which after this audit they all are. If it ever
outgrows that, tables keyed by `user_id` partition mechanically, with no schema
change. Nothing here needs to be decided today beyond keeping `user_id` first
in every index, which is done.

### Targets have no home yet

Daily targets — 2,050 kcal, 135 g protein — belong on a profile, and the profile
model is **deliberately not designed here**. It is built last, once diet and kaam
are both done, when what it must hold is known rather than guessed one mode at a
time.

Nothing here depends on it. `created_by_id` stays a nullable text column until
there is a user table for it to reference.

---

## Decided against

| Option | Why not |
|---|---|
| A row per day, not per meal | 119 rows over 23 days, 98 dishes. `Daily Summary` is already a formula sheet |
| `slot` as an enum | `Grazing` was invented mid-experiment. An enum would have rejected the most interesting row |
| Tracking water at all | Answered 1/24, and measuring it is not possible. Not a column and not a habit — an occasional line from the agent, like any other dietary guidance |
| `last_meal_time`, `walk_after_meals` | Asked daily for 24 days, answered 0 times. Not columns; questions to stop asking |
| A `used_so_far` column on pantry | Filled 0/24, while the same information was said aloud when cooking. The question is wrong, not the data |
| Asking about last meal time or post-meal walks | Answered 0/24 because the user already knows them. They are advice the agent offers, not fields it fills |
| Separate staples and stock tables | Two amounts of certainty, one nullable column. Paneer is on both sheets today |
| A separate workout table for sessions | A session is a habit log. The library is the part that needed a table |
| Sleep as a habit | Sleeping is not a choice — a blank is unreported, not skipped. It is a measurement, so it sits on `days` with weight |
| An `energy` column | Filled 2/24, and nothing reads it. `days.note` holds it until something does |
| Cost on meal rows | Paisa owns money. The one insight it gave is a `Dost & Bahar` query |
| A `shopping_list` table | Out of date the moment anything is used |
| A stored `quantity_g` on pantry | The genuinely simpler design, and for this data (suggestions, not money) its failure mode is acceptable — the user is right about that. Kept the ledger anyway because it costs the same to *use* (the quantity is one query), it is the pattern Paisa already established, and when the number does drift it can say *why*. Comfort either way: an ~1,250-rows-per-user-per-year table is small |
| Calling the table `purchases` | The app also handles payments, and stock arrives without being bought |
| Designing `profile` now | Built last, once diet and kaam both know what they need from it |

---

## Tasks

1. One migration set: `user_id` retrofit on the Paisa tables **and** the new
   diet tables — cheap now, expensive after
2. SQLAlchemy models for the diet tables
2. Seed `foods`, `measures`, `recipes` from the workbook's reference sheets
   — `profile` is **not** part of this; it is designed after kaam
3. `scripts/import_diet_workbook.py` — idempotent via `dedupe_key`, like Paisa's
4. Verify against the table below
5. Then `work-data-model`, then `GET /deck`

## Definition of done

The import is correct only if all of these hold:

| Check | Expected |
|---|---|
| `meal_logs` rows | 119, across 23 distinct days; 14 Aug totals 2,590 kcal / 135 g |
| Daily macro totals | match `Daily Summary` for all 24 days |
| Meal types | 12 distinct, `Grazing` present |
| `cooked_home` | 86 true, 33 false |
| Coverage | 7 Aug `log_complete = FALSE`; 16 Aug has no meal rows and no `days` row |
| Foods | 40 named across the sheets; 11 carry nutrition, 14 carry aliases |
| Measures | 7 — the units below the sheet's divider, nothing else |
| Recipes | 37 — 25 portion defaults plus 12 from the Recipes sheet |
| Visibility | the two user recipes `private`; Cortex rows `public` |
| `foods` | no `created_by_id` and no `visibility` — nutrition is a fact, not a possession |
| User recipes | 2 — chana salad, moongphali keema |
| Habit logs | cigarettes **7** days, alcohol 5, workout 3 — `Rest`, `No` and an explicit `0` are not rows. The workbook's eighth filled cigarette cell is a `0` on 21 Aug: the beer-without-cigarette day, recorded as absence |
| `days` | sleep on 3 days, weight on 1 — the rest NULL, not zero |
| Beer → cigarette | a query over `habit_logs` returns 4 shared days out of 5 |
| Pantry | 15 rows with grams, staples rows with `quantity_g IS NULL` |
| `pantry_moves` | 23 `purchase` + 60 `consumption` rows, none with a price |
| Tofu | +1,000 in, −400 parsed out. No `opening` row: the sheet's `Remaining` claimed 740 and cannot be trusted |
| Curd | reaches −40 g, correctly — daily home delivery was never recorded as arriving |
| Re-run the import | `added 0, skipped N` |

The beer/cigarette query is the real test, the way ₹6,921 was for Paisa: it is a
finding the workbook made independently, so reproducing it means the model holds.
**It passes on the CSVs** — 4 of 5 drinking days also logged a cigarette, and the
exception is 21 Aug.

## CSV first, database second

`backend/scripts/diet_workbook_to_csv.py` writes one CSV per table into
`backend/data/diet/`. Nothing touches the database until those are read.

The point is that a wrong column shows up as a wrong CSV rather than as a
migration. It earned its place immediately: three schema changes above — food
aliases, nullable nutrition, nested recipe components — exist because the export
failed without them, and none were visible from the sheet alone.
