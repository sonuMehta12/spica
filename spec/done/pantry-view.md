# Pantry — the list over the ledger

> Shipped 2026-09-04. The `pantry` and `pantry_moves` tables are built and hold the
> real 24 days (`spec/done/diet-data-model.md`). Nothing here adds a table or a
> screen: one section in *Your data* with two views, the writes the tables
> already imply, and the shopping list is the stock list filtered. Suggestions,
> the agent's "dahi 16 din purani hai?" question and prices wait for phase 3.

## What is being built, in one example

The ledger today, no UI:

```
Tofu     +400 (4 Aug) +200 (11 Aug) +400 (22 Aug)  −400 across nine meals   → 600 g
         5-day life, last bought 22 Aug                                       → stale since 27 Aug
Paneer   +50, −65                                                            → −15 g  → out
Curd     +780 (2 buys), −430                                                 → 350 g, 3-day life → stale
Milk     ten consumptions, never a purchase                                  → unknown (amount unknowable)
Spices   no moves at all                                                     → unknown
```

*Your data → Pantry* shows exactly that, across four tabs — **Buy**, **Stock**,
**Moves**, **Staple**:

```
BUY                       Paneer      −15 g   out
                          Tofu        600 g   stale · bought 22 Aug, 5-day life
                          Curd        350 g   stale · bought 22 Aug, 3-day life
STOCKED                   Rolled oats 620 g   ok · reorder at 200
                          Sattu       465 g   ok
ALWAYS HERE               Milk · Spices · Onion, tomato · Cooking oil · …
```

**Buy is the shopping list.** There is no second list, no table, no cadence:
things appear here when they run out or go stale, which is §6's rule
(*"triggered by real depletion, never a calendar"*).

⋮ on a row → **Bought** → a one-field prompt, grams, pre-filled with the last
purchase size → a `purchase` move. Enter saves; the row moves from Buy to
Stocked on the spot.

## Two views, because there are two tables

The section has *Stock* and *Moves*, the way the Paisa report has Pending and
All. Stock is the derived picture; Moves is the ledger it comes from.

```
STOCK                                    MOVES
Buy / Stocked / Always here              24 Aug  −100 g  Tofu   Tofu + anda + roti
grouped, one line per food               22 Aug  +400 g  Tofu   bought        Undo
                                         19 Aug  −150 g  Milk   Oats + fal
```

A move line reads *amount · food · cause*. Consumption names the meal that
caused it and has **no Undo** — it belongs to that meal, and deleting the meal
already takes it. Purchases, openings, corrections and waste are things the
user wrote, so each carries Undo. Tapping a food in Stock filters Moves to it.

## The writes, and which table each one touches

| Action | Writes | Why it is that and not an edit |
|---|---|---|
| **Add** — name, then grams | a `pantry` row; **blank grams** = row only, **a number** = row + an `opening` move | Adding tofu you already have and adding the family's atta are different facts. Blank is *here, amount unknowable*; a number is a stock-take, the pantry's `balance_checks` |
| **Bought** | a `purchase` move | Stock only ever changes by a move |
| **Have <n> g** (stock-take) | an `opening` move | *I looked, there is 600 g.* Everything after counts from it |
| **Settings** — reorder level, shelf life | the `pantry` row, in place | These are inputs about the food, not observations about its quantity |
| **Undo** on a user-written move | soft-deletes that move | A wrong Bought is a wrong row, not a wrong number |
| **Stop tracking** | soft-deletes the `pantry` row; its moves stay | The history that it was once tracked is still true |

**A quantity is never edited.** A number that turned out wrong gets a
`correction` move; a number that drifted gets an `opening`. That is the same
rule as the ledger's: the row records what was believed at the time, and the
fix is another row.

## Staple is declared, status is derived

**Revised 2026-09-04.** Staple was first derived from the moves — no purchase
ever meant *always here*. That was wrong in both directions: eggs, whey, carrot
and fruit cycle constantly and simply had no purchase logged, while atta never
will. Which foods are counted is the **user's declaration**, so it is a column:
`pantry.staple`.

The moves still decide everything else. And the two stay honest together:
**writing a purchase or an opening on a staple flips it off** — once you are
counting a thing, it is not a staple any more.

| Status | When |
|---|---|
| `staple` | the flag is set. No number, no arithmetic, no shopping list |
| `new` | tracked, but **no `purchase` or `opening` move yet** — no stock figure exists, however negative the consumption sum runs (eggs read −530 g, which says nobody records eggs arriving, not that there are minus eggs) |
| `out` | sum ≤ 0 |
| `stale` | last purchase older than `shelf_life_days` |
| `soon` | sum ≤ `reorder_at_g` |
| `ok` | otherwise |

`staple` and `new` are decided first because the import wrote consumption for
foods nobody ever bought in the app — milk at −1,500 g, eggs at −530 g. A
negative number on the family's milk would be the confident wrong figure the
whole design exists to avoid, so neither state shows a quantity at all.

`stale` outranks `soon`: 350 g of three-day curd bought two weeks ago is not
350 g of curd. The number still shows, greyed, because it is what the ledger
says; the word says why not to trust it.

## Data and API

No schema change.

```
GET    /pantry              → [{ id, food_id, name, stock_g, reorder_at_g,
                                 shelf_life_days, note, last_in, last_in_g, inbound }]
POST   /pantry              → { id, food_name | food_id, reorder_at_g?, shelf_life_days? }
PATCH  /pantry/{id}         → reorder_at_g, shelf_life_days, note
DELETE /pantry/{id}         → stop tracking; the moves stay

GET    /pantry-moves?food_id=&limit=   → the ledger, newest first, each with its meal's dish
DELETE /pantry-moves/{id}              → Undo; refuses `consumption` (409)
```

`GET /pantry` is one query — the done spec's own `SUM` with a `LEFT JOIN`, plus
the last inbound move and its size (the prompt's default) and the count of
inbound moves (which decides `unknown`). Per-food sums are rows about foods, not
totals about the person, so this stays inside the deck's rule. Status words are
computed on the client, where the words live.

`POST /pantry` takes a **food name** and resolves it: an existing food by name or
alias, otherwise a new `foods` row with no nutrition (`origin = 'cortex'`,
nutrition null — unknown, never zero). The opening move, when grams were given,
is a separate `POST /pantry-moves`; the client writes both, so a failed second
call leaves a tracked food with no stock rather than a phantom quantity.

## The section

- The grid card's hint: *"3 to buy"* in the urgent tone; *"all good"* when Buy
  is empty.
- Rows: name · stock in grams (greyed for `stale`, absent for `staple` and
  `new`) · a sub-line of **when it came in, then what that means now**:
  *11 Aug*, *22 Aug · 2d left*, *22 Aug · 1d over*, *11 Aug · nothing left*,
  *4 Aug · below 200 g*, *not counted yet*. The date says which purchase this
  is; the days say whether it can still be eaten. Short form (`2d left`)
  because it sits beside the number, not in a sentence. A staple shows
  nothing — the tab already said it.
- **No heading inside a tab.** The tab names the list and carries its count.
- ⋮ → **Bought**, **Have** (stock-take), **Settings** (reorder, shelf life),
  **Always here** / **Count it** (the flag), **Stop tracking**. Staple rows get
  Bought and Have too — the first purchase is exactly how a staple becomes
  counted, and it flips the flag itself.
- **+ Add item** at the foot of the list: a name, optional grams, Save.
- The **Always here** group is a single quiet line of names, not rows. Nothing
  to do there, by design.
- The recipe library in *Your data* is still prototype data with its own ids;
  its *"N abhi ban sakti hain"* count does not read the live pantry yet. It
  joins when recipes go live, not here.

## Rules

- **`waste` is never written by the UI, and never by the app.** Nobody observed
  the spoilage. Stale is a status, not a write; the agent will ask (*"bachi hai
  ya khatam?"*) and the answer becomes a `waste` or `correction` move.
- **`opening` is an observation, not a total.** It is *I looked, there is 600 g*;
  the stock reads as the latest opening plus every move after it.
- **Unknown rows never reach Buy.** The done spec's query listed *never tracked*
  foods for shopping; §5 since decided staples are not counted at all. The
  section follows §5. If a staple runs out, the user says so and it becomes a
  tracked food with its first purchase.
- **Each food is counted in its own unit** — see below. A dish ingredient is in
  that unit too: 60 g of atta, 2 eggs.
- **Data debris stays visible, not hidden.** Two whey rows, a `Eggs / chicken
  (bahar)` row that is really restaurant food: they show as the ledger has them.
  Cleanup is a data pass, not a UI rule (the user maintains the data by hand).

## The item pass of 2026-09-04

Reviewing the imported rows against the four tabs settled three rules that were
not obvious until the real list was on screen:

- **Fruit is one counted row, not one per fruit.** Mango is seasonal, apple and
  banana are interchangeable, and a per-fruit gram count is stale within days —
  the app still read *apple 1,000 g* from 4 August. You buy a kilo of whatever
  is in season and log it once.
- **What arrives without being bought is a staple**, even when it is
  perishable: curd, the day's green vegetable, the seasonal sabzi.
- **A name that describes where you ate is not a pantry fact.** `Eggs / chicken
  (bahar)` became `Eggs`.

`backend/scripts/fix_pantry_items.py` holds the pass, idempotent, so a re-import
does not restore the old shape. Untracking left every move in the ledger.

## Units — the food says what it is counted in

**Decided 2026-09-04.** Eggs come by the dozen, milk in millilitres, atta in
grams. Storing everything as grams meant the prompt asked for grams even for
eggs, and a weight per egg the app made up would sit in the ledger looking
observed.

So `foods.unit` is one of `g`, `ml`, `piece`, and the move stores **what you
actually count** — the columns lost their `_g` suffix. `grams_per_unit` is
there for macro maths later, since macros are per 100 g, and is nullable
because an unknown weight per egg is not a zero one.

- **A dozen is not a unit.** It is twelve pieces, and the prompt takes it as
  shorthand. Storing dozens would make six eggs 0.5 of something.
- **Fruit cannot be one row.** A bucket cannot say which fruit came in, and it
  cannot carry a piece weight — a kela is 100 g and a seb is 180. Per-fruit
  rows, and one you stop buying gets untracked rather than lingering. Mango
  comes back when the season does.

## A stock-take resets the count

**Fixed 2026-09-04.** The stock summed *every* move, so saying *"I have 18
eggs"* landed as 18 on top of the old consumption and read 7. That made a
stock-take mean nothing.

Stock now counts from the **last `opening`**: everything before it is history,
not arithmetic. That is what the data model always said an opening was — an
observation, the pantry's `balance_checks` — and the read path now agrees.

## Review pass, 2026-09-04

Before moving to the plugin, a sweep of the whole surface turned up four
things, all fixed:

- **The one-row-per-food rule blocked re-tracking.** `UNIQUE(user_id, food_id)`
  was not partial, so a food untracked once could never come back — Banana
  could not return after the fruit pass. Now partial on `deleted_at IS NULL`,
  like every other uniqueness in the schema.
- **Add had no unit.** A new food is created in the unit you pick (g · ml ·
  pcs); an existing food keeps the unit it has.
- **The chat's `@pantry` and `@recipes` cards were still the prototype's
  invented rows.** They now read the same live state as Your data, and load at
  boot so the first `@pantry` is not empty.
- **`alembic check` had drift**: the FK columns to `users` were declared without
  a type and four newer tables used VARCHAR. All TEXT now; the check is quiet.

## Decided against

| Option | Why not |
|---|---|
| A shopping-list table or a "list" state on rows | The list *is* the Buy group; a stored list goes stale the moment a meal is logged |
| A stock-take ("I have 600 g") action | The Excel pantry died on *"kitna bacha hai"*. Not asked; the agent will ask about the stale ones, one at a time |
| Prices and a total (§6 point 3) | `foods` has no prices yet; inventing them would be exactly the number nobody checks |
| Status server-side | Words are UI; the server sends the numbers that decide them |
| Editing a move's quantity | A correction or an opening is another row. Editing one destroys what was believed when it was written |
| Deriving staple from the moves | Tried first, and wrong both ways: eggs and fruit cycle with no purchase logged, atta never will. Only the user knows, so only the user says |
| Listing `unknown` foods for shopping | §5: staples are not counted. A list that nags about the family's atta is the list that gets ignored |

## Definition of done

Verified in a cold browser tab against the running API on the deck's anchor day
(28 Aug). Add, Settings and Stop tracking were verified at the API; the Bought
and Undo round trip was clicked through.


| Check | Expected |
|---|---|
| `GET /pantry` | 32 rows; Tofu `stock_g 600`, `inbound 3`, `last_in 2026-08-22`, `last_in_g 400`; Milk `inbound 0` |
| Your data → Pantry | Buy: Paneer `out`, Tofu and Curd `stale`; Stocked: oats, sattu…; Always here: the seven no-move foods plus milk and the other never-bought ones |
| Grid card hint | *"3 to buy"*, urgent |
| ⋮ → Bought on Tofu → 400 → Enter | a `purchase` move of +400 dated the anchor day; Tofu reads 1,000 g `ok` and leaves Buy at once |
| Reload | the same, from the server |
| ⋮ → Stop tracking | it leaves the list; its moves remain in the ledger |
| Four tabs | Buy (3), Stock (22 counted foods), Moves, Staple (10: atta, brown rice, oil, dal, milk, onion/tomato/garlic/ginger, rajma, rice, spices, tomato) |
| ⋮ → Always here on Carrot, then Count it | it moves to Staple and back; the counts follow |
| Bought on a staple | the flag flips off and it appears in Stock |
| Moves view | newest first; 24 Aug −100 g Tofu names its meal and has no Undo; 22 Aug +400 g Tofu has one |
| Undo on the 22 Aug purchase | the move soft-deletes; Tofu reads 200 g and moves to Buy |
| Tapping Tofu in Stock | Moves filtered to Tofu, nine rows |
| + Add item → "Soya chunks", blank | a tracked row with no moves; it appears under Always here |
| + Add item → a new name, 500 | a `foods` row with null nutrition, a `pantry` row, and an `opening` move of +500 |
| ⋮ → Settings → reorder 300 | the row updates; Tofu at 600 g is unaffected, at 250 g it would read `soon` |
| Recipes section | unchanged |
