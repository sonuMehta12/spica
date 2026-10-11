# Dishes — what you eat, described once

> Shipped 2026-09-04 — tables, import, backfill and the Your data section.
> Suggestion is deferred to the agent; see that section. Replaces the `recipes` table, whose 37 imported rows are being
> thrown away: 23 of them were portions (*1 roti*, *1 katori dal*) and only a
> handful were things anyone would call a dish. Nothing here is built.

## The word

Neither *recipe* nor *meal*.

- **Meal** is taken. `meal_logs` is the ledger — one row per thing you actually
  ate, at a time, on a day. A library that is also called meals makes every
  sentence about the app ambiguous.
- **Recipe** fails the app's own examples. Nobody cooks *Office thali*, and
  *whey + 2 bread + 2 eggs* has no method. Half the library would be lying
  about what it is.

**A dish is a thing you eat, described once, with a serving and its macros.** A
dish that happens to carry ingredients and steps is one you can cook. That is a
property, not a different entity.

The template/instance pattern is unchanged (`spec/substrate.md` §1): the library
holds the dish, the ledger holds the meal log that points at it.

## What it is for

Not a recipe app. **A dish exists so the agent can suggest the next one.** Two
questions it has to answer:

1. *"What should I eat now?"* — from what is in the pantry, the time of day, the
   protein still owed, and what you have eaten lately.
2. *"What is this?"* — when you log *"office thali + whey"*, the dish is what
   gives it macros without guessing.

Everything in the model is there to serve one of those two. Nothing else.

## Yours, and everyone's

Dishes are **global**, like posts: there is one pool, and each row knows who
made it and whether it is public.

**Your library is only what you have a relationship with** — and there are
exactly two kinds:

| State | Where it comes from | Stored? |
|---|---|---|
| **Tried** | a `meal_item` on any of your meals points at the dish | **No — derived.** Count the lines: the ledger already knows how many times and when. Omelette counts even when it arrived on a plate with two other things |
| **Saved** | you starred a suggestion to try later | **Yes** — a bookmark is a fact nothing else records |

Same rule the pantry settled on: derive the measurement, store the declaration.
Tried shows a tick and a count (*3×, last on 22 Aug*), saved shows a star, and a
dish you starred and then cooked shows both.

Suggestion draws from the **whole pool**; the library shows **your slice**. That
is the entire visibility model.

## Portions leave

*1 roti*, *1 katori dal*, *1 glass doodh*, *muththi bhar dry fruit* — 23 of the
37 imported rows — are not dishes. A portion is **a food plus a measure**, and
both tables exist already (`spec/done/diet-data-model.md`): `foods` holds macros
per 100 g, `measures` holds *katori → 150 g*. That pairing is exactly what the
agent needs to turn *"2 roti aur dal"* into numbers, and it does not need a dish
row to do it.

A dish carries **one serving** — *1 plate*, *1 glass*, *1 bowl* — and its macros
are per serving. Serving and portion are the same idea; there is no second one.

## Data

```sql
CREATE TABLE dishes (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  aliases         TEXT[] NOT NULL DEFAULT '{}',   -- 'dahi', 'curd' are one dish
  -- When it is eaten. Free text, like meal_logs.meal_type: twelve values appear
  -- in 24 days and 'Grazing' was invented mid-experiment.
  meal_type       TEXT,
  serving_label   TEXT NOT NULL,                  -- '1 plate', '1 glass', '2 roti + sabzi'
  -- Per serving, as believed when written. Protein is required because the
  -- whole diet mode turns on it; the rest are nullable — unknown is not zero.
  kcal            INTEGER,
  protein_g       NUMERIC(6,1) NOT NULL,
  carbs_g         NUMERIC(6,1),
  fat_g           NUMERIC(6,1),
  fibre_g         NUMERIC(6,1),
  -- Cookable dishes only. The library's real question is 'mere paas 20 minute hain'.
  minutes         INTEGER,
  needs_prep_ahead BOOLEAN NOT NULL DEFAULT false, -- bhigona, marinate
  steps           TEXT,
  image_url       TEXT,
  -- What the agent ranks on beyond ingredients: 'veg', 'high-protein',
  -- 'summer', 'office', 'no-cook'. Free tags, not a taxonomy.
  tags            TEXT[] NOT NULL DEFAULT '{}',
  source_url      TEXT,                            -- where it was shared from
  created_by_id   TEXT REFERENCES users(id),       -- NULL = came with the app
  visibility      TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','public')),
  forked_from_id  TEXT REFERENCES dishes(id),
  ...envelope
);

CREATE TABLE dish_items (
  id           TEXT PRIMARY KEY,
  dish_id      TEXT NOT NULL REFERENCES dishes(id),
  food_id      TEXT REFERENCES foods(id),
  -- A dish can contain a dish: 'Ghar ka dinner' is 2 roti + dal + sabzi.
  component_dish_id TEXT REFERENCES dishes(id),
  grams        INTEGER,                            -- with food_id
  servings     NUMERIC(4,1) NOT NULL DEFAULT 1,    -- with component_dish_id
  note         TEXT,
  CHECK ((food_id IS NULL) <> (component_dish_id IS NULL)),
  ...envelope
);

-- A meal is a bill; these are its lines. Most meals are composite — of 127
-- imported logs, the majority are sentences joined by '+' — so a single
-- dish_id on the meal would either drop everything after the first dish or
-- force a made-up composite dish per plate.
CREATE TABLE meal_items (
  id           TEXT PRIMARY KEY,
  meal_log_id  TEXT NOT NULL REFERENCES meal_logs(id),
  -- A line is a dish (omelette) or a plain food (2 roti = 60 g of atta).
  -- Portions have no dish, by design, and an array of dish ids could not
  -- hold them at all.
  dish_id      TEXT REFERENCES dishes(id),
  food_id      TEXT REFERENCES foods(id),
  servings     NUMERIC(4,1),                     -- with dish_id
  grams        INTEGER,                          -- with food_id
  -- What the user's words were for this line, before it was resolved.
  said         TEXT,
  CHECK ((dish_id IS NULL) <> (food_id IS NULL)),
  ...envelope
);

CREATE TABLE dish_saves (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id),
  dish_id    TEXT NOT NULL REFERENCES dishes(id),
  ...envelope,
  UNIQUE (user_id, dish_id)
);
```

`meal_logs.recipe_id` is **dropped**, not renamed. It assumed one dish per meal,
and a plate is *"2 ande ki omelette + roti + moongphali chutney"* — three lines,
two of them dishes and one a portion. The column is empty on every imported row,
so nothing is lost. `meal_logs.dish` keeps the user's own words for the whole
plate; the lines carry what those words resolved to.

**No score, no rank, no popularity column.** The agent ranks, with what the data
already carries: the ingredients (against pantry stock), the time of day, the
minutes, the tags, and your own history from the ledger. A stored rank would be
a number nobody could explain a week later, and it would be wrong the moment the
pantry changed.

## How a spoken meal becomes lines

The agent is the extraction layer: your sentence in, resolved lines out. It
matches each part against the pool in a ladder, cheapest first, and stops at the
first confident hit — `pg_trgm` and `vector` are both installed already:

| Step | How | Example |
|---|---|---|
| 1 | exact name | *Whey shake* |
| 2 | alias | *protein shake* → Whey shake |
| 3 | trigram similarity | *sattu drnk* → Sattu drink |
| 4 | embedding | *peanut keema* → Moongphali keema |
| 5 | nothing confident | the line stays unresolved. If the same text appears twice, ask once |

It always says what it matched, so a wrong guess costs one correction. **Matching
never creates a dish** — that is the deliberate act, and only the user makes it.

## Rules

- **A dish with no `dish_items` is still a dish.** Office thali cannot be broken
  into grams and does not need to be. It simply never appears in *cook now*.
- **Cooking a dish spends its ingredients**, exactly as meals already do — the
  server walks the meal's lines: a dish line spends `dish_items × servings`, a
  food line spends its grams directly, and only for foods the pantry tracks.
- **Macros live on the dish, and on the meal log too.** The log keeps what was
  believed at the time (`spec/done/diet-data-model.md`), so editing a dish later
  never rewrites history.
- **Saving is not copying.** A star is a row in `dish_saves`; the dish stays the
  author's. Changing someone else's dish means forking it, which is what
  `forked_from_id` is for.
- **Unsaving deletes only the save.** History — the meals you logged against it —
  survives, so it stays in your library as *tried*.

## Decided against

| Option | Why not |
|---|---|
| Keeping the word *recipe* | Office thali is not a recipe, and half the library would be one |
| Calling the library *meals* | `meal_logs` owns that word; the ambiguity would be permanent |
| Separate tables for tried and saved dishes | The same dish is often both. Moving a row when you cook is how data goes missing |
| Storing `tried` / `times_cooked` on the row | The ledger already knows. A stored count drifts the first time a meal is deleted |
| One `dish_id` on the meal log | Most meals are plates. It would drop every dish after the first, or force a made-up composite dish per plate |
| An array of dish ids on the meal log | No room for the quantity (*1.5 katori*), and no room at all for a portion line like *2 roti*, which points at a food |
| A rank or score column | The agent ranks, from live pantry and live history. A stored score is stale and unexplainable |
| Keeping portions as dishes | *1 roti* is a food plus a measure. Two tables already do it, and the agent needs them there anyway |
| A per-dish rating | Not asked for, and "did you cook it again" is a better signal than a star you gave once |

## Deferred to the agent (phase 3), recorded so it has a starting point

Built now: the tables, the import, the backfill, and *Your data → Dishes*.
**Not built now: anything that suggests.** Ranking is the agent's job and the
agent does not exist. What is settled, so phase 3 starts from a decision rather
than a blank page:

**Extraction.** The agent splits a spoken meal at the separators it already
uses in the logs — `+`, `aur`, `,`, `with` — into candidate lines, and resolves
each one through the ladder above. It returns lines, not prose: `{said, dish_id
| food_id, servings | grams, confidence}`. The composer shows what matched.
Below a confidence threshold the line stays unresolved rather than guessing;
`spec/paisa-categorise.md` already sets that pattern for money.

**Search.** All four rungs run server-side over the pool, since only the server
has the index: `pg_trgm` for the fuzzy rung (already used for counterparties,
`gin_trgm_ops`), `vector` for the embedding rung, computed once per dish and
cached against its id (`spec/substrate.md` §9). A dish's embedding covers name,
aliases and tags — not its steps, which would drown the name in method words.

**Suggestion.** The agent ranks; there is no score in the database. What it has
to work with, all live at ask time:

| Signal | From |
|---|---|
| can I cook it now | `dish_items` against pantry stock, the query in `spec/done/pantry-view.md` |
| protein still owed today | the day's meals against the profile target |
| have I had it lately | this dish's `meal_items` in the last N days — repetition is a cost, not a bonus |
| do I have 20 minutes | `minutes`, `needs_prep_ahead` |
| does it fit the moment | `meal_type`, tags (`summer`, `office`, `no-cook`) |
| have I liked it before | tried count, and whether it is saved |

**Bookmarking a suggestion** is `spec/capture.md`'s Door 1, unchanged: the reply
carries typed dish objects with ids, and the star writes a `dish_saves` row. A
suggestion that is not in the pool yet is created on save, private, credited to
the user.

## Cook now — the rule, and what it deliberately allows

A dish qualifies when it has ingredients and nothing on that list is short.
`GET /dishes` sends the ingredients **already flattened**: a component dish's
foods arrive as ordinary lines with their grams scaled, so nesting is checked
rather than skipped. Without that, *Ghar ka dinner* claimed to be cookable on
the strength of its dal alone, having never looked at the atta or the sabzi
inside its component.

| Ingredient | Verdict |
|---|---|
| the dish has none at all | never cookable — Office thali |
| a staple | present, always |
| tracked but never counted (`new`) | **present** — unknowable is not absent |
| not in the pantry at all | present — same reason |
| stock ≤ 0, or below the grams needed | **missing**, and the dish is out |
| past its shelf life (`stale`) | **cookable, and said**: *"tofu is stale"* |

The last two rows are the judgment calls. Blocking on stale would be the app
deciding food is spoiled, which the pantry explicitly refuses to do — you are
the one who can look in the fridge. Counting an untracked food as missing would
nag about eggs nobody logged, which is the confident wrong answer this app
exists to avoid.

## Definition of done

Verified in a cold browser tab against the running API.


| Check | Expected |
|---|---|
| Twenty dishes imported from a reviewed CSV | drawn from what the ledger says the user actually eats |
| A dish with items | *Moong dal chilla + tofu bhurji* lists tofu and moong with grams |
| A dish without items | *Office thali* exists, has macros, and never claims to be cookable |
| Your data → Dishes | your slice only: saved (★) and tried (✓ 3×), with everything else reachable by search |
| Cook now | 8 of 10; Ghar ka dinner's component is expanded and checked; a stale ingredient warns without blocking |
| Star a dish you have not tried | it appears in the library as saved; unstar removes it |
| Log a plate of three things | three `meal_items`: two dish lines and one food line for the roti |
| Log a meal against a dish | it shows as tried with a count, and the pantry spends the lines' ingredients |
| Delete that meal | its lines go with it; the count drops and the stock returns |
| Backfill the 24 imported days | 34 of 127 logs resolve by name or alias, across 10 dishes; the rest stay unresolved rather than guessing |
| Portions | no dish is called *1 roti*; the agent gets those from `foods` + `measures` |
