# Users, profile and memory — the table, not the lock

> Amended 2026-10-11 by `spec/done/onboarding-goals.md`: `users` gains
> `gender` and `diet`; `dob` may hold 1 January of a birth year worked out from
> an age, shown as an age; Profile shows both new fields, and every field but
> the name can be cleared.

> Shipped 2026-09-04. Everything below is built except the platform sync, which
> is deferred in `spec/notes.md` § Memory sync.
> Unblocked by the user's own rule: *"profile banayenge jab diet aur kaam ho
> jayein."* Both are done. Reads from every `user_id` column already in place,
> `spec/notes.md` (Auth and the users table · RLS), `spec/task-sync.md` (the one
> plugin), `spec/agent-everywhere.md` (context sharing), and the deck's stubbed
> *Edit goal*.

## Scope

**In:** one `users` table replacing the single-row `profile`, with a real id;
every personal table's `user_id` becomes a real foreign key; the targets the app
hardcodes move onto the row; the facts about the person that today live
scattered across ChatGPT, Claude and Gemini get one home — a `memories` table in
our own format; a settings surface; `/deck` serves the profile.
**Out — deliberately:** login and tokens (auth is *who are you*; this is *where
your facts live*); pushing memory into other platforms (see *Decided against*
and `notes.md`); the plugin tools themselves — they are one section of
`spec/task-sync.md`, and this spec only defines what they read.

## Two shapes, not one

The word "profile" was carrying two different things:

| | Profile | Memory |
|---|---|---|
| **What** | Facts the **app computes with** | Facts an **agent reads** to know the person |
| **Examples** | protein target, DOB, height, savings target | profession, interests, how they like to be spoken to, how they learn |
| **Shape** | typed columns — a number is a number | many small free-text facts, each named and dated |
| **Changes** | rarely, by the user, deliberately | often, by any agent, in conversation |
| **Wrong shape costs** | a `bio` blob nobody can compute from | forty nullable columns, one per fact anyone thought of |

So: **columns for what has a unit, rows for what has a sentence.** A learning
style is a row. A protein target is a column.

## The `users` table

```sql
CREATE TABLE users (
  id                   TEXT PRIMARY KEY,           -- ULID, see "A real id"
  -- identity
  display_name         TEXT NOT NULL,
  dob                  DATE,
  height_cm            NUMERIC(4,1),
  city                 TEXT,
  timezone             TEXT NOT NULL DEFAULT 'Asia/Kolkata',
  -- money
  savings_target_paise BIGINT,
  -- food
  kcal_target          INTEGER,
  protein_g_target     NUMERIC(6,1),
  carbs_g_target       NUMERIC(6,1),
  fat_g_target         NUMERIC(6,1),
  fibre_g_target       NUMERIC(6,1),
  weight_target_kg     NUMERIC(5,1),
  -- rest and movement
  sleep_target_min     INTEGER,
  step_target          INTEGER,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Each column earns its place by something that reads it: `dob` and `height_cm`
are the inputs a kcal-target derivation needs; `city` is where local prices and
weather will attach; `timezone` already decides `local_day`. **Targets are
nullable** — unset is unset, and a ring with no target shows the value with no
denominator, never an invented 2,050. Same rule as carbs: unknown is not zero.

**Current weight is not a column.** It is the one number a diet app exists to
watch move, and a single overwritten field cannot show movement. It is a
measurement, so it is a ledger:

```sql
CREATE TABLE weigh_ins (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id),
  local_day  DATE NOT NULL,
  weight_kg  NUMERIC(5,1) NOT NULL,
  ...envelope,                                    -- created_at, updated_at, deleted_at, note, dedupe_key
  UNIQUE (user_id, local_day)
);
```

*"Aaj 78.4"* is a row. The profile holds the target; the ledger holds the truth.

## The `memories` table — our format

```sql
CREATE TABLE memories (
  id          TEXT PRIMARY KEY,                    -- ULID
  user_id     TEXT NOT NULL REFERENCES users(id),
  slug        TEXT NOT NULL,                       -- 'profession', 'learning-style', 'communication-style'
  kind        TEXT NOT NULL,                       -- identity | preference | style | interest | project | reference
  text        TEXT NOT NULL,                       -- the fact, in the user's words
  source      TEXT NOT NULL,                       -- 'user' | 'claude-code' | 'claude' | 'chatgpt' | 'gemini' | 'cortex'
  confirmed_at TIMESTAMPTZ,                        -- last time the user said "yes, still true"
  ...envelope,
  UNIQUE (user_id, slug)
);
```

Design choices, each with its reason:

- **Small facts, not one bio.** A bio is written once and read never; an agent
  needs *the* fact about communication style, not a paragraph to mine it from.
  Separate rows also let one fact change without retyping the rest.
- **`slug` is the stable handle.** "profession" is the same fact whichever agent
  wrote it, so a second write updates rather than duplicates. That is the whole
  fix for *scattered across three apps*: one slug, one row.
- **`kind` is a coarse shelf**, six values, so a reader can ask for *everything
  about style* without knowing the slugs. Not a taxonomy; it can grow.
- **`source` and `confirmed_at` make trust visible.** A fact Gemini inferred in
  March is not a fact the user stated yesterday. The deck's own rule applies —
  inferred is marked, confirmed is not.
- **The app's oldest rule holds:** memory is facts about the *person*, never
  sentences about the person's *data*. "Prefers short answers" is memory.
  "Spent ₹3,290 on Rakhi" is a query.

**This is the format** — the standard the user asked for. Frontmatter-shaped on
purpose: `slug · kind · text · source · dated` maps one-to-one onto the memory
files Claude Code already keeps, so the plugin can write those files from these
rows without translation.

## A real id, even for one user

`'me'` was a placeholder that leaked into every table. The migration:

1. creates `users`, generates **one ULID**, inserts the single row with it;
2. rewrites every `user_id = 'me'` across every personal table to that ULID;
3. adds `REFERENCES users(id)` to each of those columns;
4. drops `profile`.

The auth seam stops holding a constant. `current_user()` returns the id of the
only row in `users`, read once at startup and cached. When auth lands, it returns
the id the token proves — one function, same as before, and no `'me'` anywhere
to hunt down.

## What the API adds

```
GET    /users/me                 → the row
PATCH  /users/me                 → any subset of the editable columns; id, created_at locked

POST   /weigh-ins                → { id, local_day, weight_kg, note? }; same-day repeat replaces (dedupe on user+day)
DELETE /weigh-ins/{id}

GET    /memories?kind=           → rows, newest confirmed first
POST   /memories                 → { id, slug, kind, text, source }; same slug → update, not a second row
PATCH  /memories/{id}            → text, kind, confirmed_at
DELETE /memories/{id}
```

Same conventions as every other write: client ULIDs, `user_id` never accepted
from the body, soft deletes. `/deck.profile` grows from `{savings_target_paise}`
to the whole row, and `frontend/src/data/config.ts` loses every target and the
hardcoded name.

> **Archived 2026-09-26:** the plugin half below is parked —
> `spec/archive/shared-memory.md`. The table and API above are unaffected.

**The plugin** (`spec/task-sync.md` § An MCP server) gains three tools that are
thin wrappers on the above: `profile_get`, `memory_search { kind?, query? }`,
`memory_add { slug, kind, text }`. Their contract is the API's; they are listed
here only so the two specs agree. Cortex remains the store and MCP the tool
interface — the decision already recorded in `spec/diet-logging.md`.

## The settings surface

Not a screen of forms, and not a conversation either. **Quick edit, in place**,
the way a settings app does it:

- **Drawer → Profile** lists the row in groups — *Finance* (the saving goal;
  income sources and fixed costs will join it as views), *Health* (calories,
  protein, carbs, fat, fibre, sleep, steps), *Weight* (target and weigh-ins),
  *About you*, *Memory*. One long list of targets read as clutter.
- **Tap a row and it opens into a small editor right there** — current value,
  unit, Save. Enter saves, Esc closes, and the row shows the new value the
  moment it is typed. A refusal keeps the editor open and says so.
- **Paisa ⋮ → Edit goal** and **Diet ⋮ → Edit targets** open the Profile page
  with that row already in edit mode. The deck recomputes on return.
- **Memory** rows edit the same way; *Add memory* is a slug, a kind (a
  dropdown of the six) and the fact. *Weigh-in* is one number for today.
- The **composer floats over the page** as it does over the report — for
  asking the agent, not for editing. Sending closes the page so the answer is
  visible underneath.

## Rules

- **`user_id` is still never accepted from the client.**
- **The seam does not change shape.** One function, one return value.
- **No second user is created by this spec.** A `users` table with one row is
  the honest state of the product. Signup is auth's problem.
- **Memory flows *out* by being asked for, never by being pushed.** A tool call
  fetches the facts an agent needs for this conversation. There is no "send my
  memory to X" button — that is the *No data export* constraint, applied here.

## Decided against

| Option | Why not |
|---|---|
| Building login now | *"Aadha-adhoora auth banana usse bura hai ki auth ho hi na."* The table costs nothing; the lock is a separate decision |
| Keeping targets in `config.ts` | The bank-balance lesson: a client constant is quietly wrong the day it changes |
| A `weight_kg` column | An overwritten weight cannot show a trend, which is the only reason to record it |
| One `bio` text field | Unqueryable; every agent would re-mine the same paragraph and disagree |
| A column per memory fact | Forty nullable columns, and a migration every time a new kind of fact appears |
| A separate memory plugin | Two plugins, two auths, two sync loops for one brain. The task-sync MCP server already exists on paper; memory is three more tools on it |
| Pushing memory into ChatGPT / Gemini | Neither has a write API for memory; and a bulk push is the export leak the product refuses. Deferred with the realistic paths in `notes.md` |
| Keeping `'me'` | A placeholder id in every table is a bug waiting for the second user |

## Definition of done

Verified in a cold browser tab against the running API; the weigh-in and memory
editors were verified at the API (same-day replace, slug upsert) and by code review.

| Check | Expected |
|---|---|
| `users` exists, `profile` gone, one row with a ULID id | migration reversible; `grep -rn "'me'" backend/app` finds nothing |
| Every personal table's `user_id` | a real FK to `users(id)`; every existing row rewritten to the ULID |
| Paisa ⋮ → Edit goal | Profile page opens with Finance unfolded and the goal editor focused; typing 15000 + Enter recomputes limit and projection on return; reload shows 15,000 |
| Diet ⋮ → Edit targets → Protein → 140 + Enter | row reads 140 g at once; the ring's denominator is 140 g on return |
| A target left NULL | ring shows the value with no denominator |
| `POST /memories` twice with slug `profession` | one row, updated text, `updated_at` moved |
| `POST /weigh-ins` twice for the same day | one row, second value kept |
| `grep -rn "PROTEIN_TARGET\|KCAL_TARGET\|savingsTarget\|userName" frontend/src/data/config.ts` | nothing |
| Drawer → Profile | five folded groups with a glance line each; a group unfolds to rows; a row unfolds to its editor; Enter saves, Esc closes; a refused value keeps the editor open and says so |
