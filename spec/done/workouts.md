# Workouts — an exercise library to suggest from

> Shipped 2026-09-07. Fills the empty `exercises` table. A workout stays a
> **habit**; `spec/workout.md` (the deck strip) is unchanged and still true.

## The problem

The `exercises` table was created with the diet model and never had a row. So
*"aaj gym mein kya karu"* had nothing to answer from, and neither did *"leg
lagana hai, kuch bata"*.

That is the whole gap. Logging is not part of it: a workout is recorded the way
a cigarette is — **yes or no**, as a habit tick — and what was done inside the
gym is not something this user writes down.

## What it does

One table. A **library to suggest out of**, the way dishes is one — not a
record of what happened.

- The agent reads it first: *"leg lagana hai"* is a `muscle_group` query,
  *"cardio karna hai"* is a `kind` query, *"20 minute hain"* is
  `typical_minutes`, *"gym nahi ja paya"* is `equipment`.
- What the library does not hold, the agent finds — YouTube, Instagram, its own
  knowledge — and **offers**. Keeping it is a row: name, `steps`, `source_url`,
  `source = 'chat'`.
- **`tried` is how well you know it.** `0` means it is only bookmarked; above
  zero means you have actually done it, and the agent can lean on it.

*Your data → Workouts* browses the library. **Three tabs and nothing else on
arrival** — All, Done, Not tried — with type, muscle group and equipment behind
a **Filter** button on the right. Two rows of chips before anyone has asked a
question is noise; the button counts itself (`Filter · 2`) and stays green while
anything is on, because a filtered list that looks unfiltered is a lie by
omission.

## Data

One table, and every row belongs to one person.

```sql
exercises
  id                TEXT PK
  user_id           TEXT NOT NULL REFERENCES users(id)   -- whose library

  name              TEXT NOT NULL          -- 'Barbell shoulder press'
  aliases           TEXT[] NOT NULL '{}'   -- 'OHP', 'military press'
  kind              TEXT                   -- strength | cardio | mobility | stretch
  muscle_group      TEXT                   -- chest | back | legs | shoulders | arms | core
  equipment         TEXT                   -- barbell | dumbbell | machine | cable | bodyweight | none
  typical_minutes   INTEGER

  steps             TEXT                   -- how to do it
  source_url        TEXT                   -- the YouTube / Instagram link
  image_url         TEXT                   -- a form GIF; seeing beats reading
  source            TEXT NOT NULL          -- seed | chat | link | manual
  note              TEXT

  tried             INTEGER NOT NULL 0     -- 0 = never done
  last_tried        DATE
  ...envelope
```

**Removed with this shape:** the `exercise_saves` table, and `visibility` /
`created_by_id` / `forked_from_id`.

### Why `tried` is stored

Everywhere else in Cortex a count is a query — a dish's tried-count over
`meal_items`, pantry stock over `pantry_moves`, a person's still-out over the
ledger. **Exercises have no ledger underneath them**, because the event is not
recorded: a workout is a habit tick.

So *"I have done this three times"* is a **declaration**, not a measurement, and
that is the side of the line where storing is correct — the same rule that puts
`staple` on a pantry row and a weight target on the profile. The danger is only
a stored number *pretending* to be derived; this one is not.

It also replaces the bookmark. An exercise is in the library because someone put
it there, which is what a star meant; `tried = 0` versus `tried > 0` is the only
distinction left, and one integer carries it.

`POST /exercises/{id}/did` increments it and stamps `last_tried` in one write,
so the client never reads-then-writes a counter. The agent calls it when you say
*"aaj squats kiye"* — a counter moving, not a session row.

### Why `kind` is separate from `muscle_group`

The first seeded CSV filed **cardio as a muscle group**, which is wrong: cardio
is not a muscle. Split apart, *Incline walk* is `kind: cardio` with **no**
muscle group, and *Barbell squat* is `kind: strength, muscle_group: legs`. Then
*"leg lagana hai"* returns leg work and not a treadmill, and *"cardio karna
hai"* returns the treadmill.

### The seed

`data/workouts/exercises.csv`, imported by `scripts/import_exercises_csv.py`,
idempotent on name so the CSV stays the source of truth while it is corrected.

**`steps` ships empty.** Writing thirty-six form guides from memory would be
thirty-six chances to describe a lift wrongly, and *Honesty over completeness*
applies to instructions harder than to numbers. They arrive per exercise, from a
real source, with the link beside them.

## API

```
GET    /exercises?q=&kind=&muscle_group=&minutes=&tried=   → the library
POST   /exercises                                          → add one
PATCH  /exercises/{id}                                     → any field, tried included
POST   /exercises/{id}/did                                 → tried += 1, last_tried = today
DELETE /exercises/{id}                                     → soft
```

The query parameters *are* the suggestion, spelled out.

## Rules

- **A workout is a habit.** Yes or no on the Diet card, next to cigarettes and
  alcohol. The section says so in one line, so it does not look like it forgot
  to offer logging.
- **`?minutes=20` keeps the unknowns.** An exercise with no `typical_minutes` is
  unknown, not too long; filtering it out would treat a missing number as a
  large one.
- **Nothing the agent finds is inserted silently.** It is offered; a row appears
  because the user kept it.
- **`tried` never decrements on its own.** A miscount is fixed with `PATCH`,
  deliberately.

## Decided against

| Option | Why not |
|---|---|
| `workout_logs` + `workout_items` — a session ledger | **Built 2026-09-06, removed 2026-09-07.** The user logs *that* he trained, not *what*. A ledger of lines modelled somebody else and retired a habit that was working. Full reason in `spec/notes.md` |
| An `exercise_saves` table | The library *is* the bookmark. `tried = 0` versus `tried > 0` is the only distinction a star was making, and an integer already there carries it |
| `visibility` / `created_by_id` / `forked_from_id` | Dishes has them for a pool the app ships. One person's exercise library is owned outright — `WHERE user_id = :u` is the whole rule, and it removes the `COALESCE(created_by_id = :u, false)` NULL trap that 500'd this endpoint once already |
| Deriving `tried` | There is nothing to derive it from, and inventing a ledger to make the arithmetic possible is what 2026-09-06 did |
| Seeded `steps` | Thirty-six form guides written from memory is thirty-six chances to teach a lift wrong |
| `sets` / `reps` / `weight` | Still nothing in the data asks for it. A typical prescription, if ever wanted, is a sentence in `steps` |

## Definition of done

| Check | Expected |
|---|---|
| Migration | the nine new columns; `exercise_saves`, `visibility`, `created_by_id`, `forked_from_id` gone; 36 rows carry `user_id` and `source = 'seed'` |
| Cardio split | the five cardio rows read `kind: cardio` with no muscle group |
| `GET ?muscle_group=legs&minutes=20` | leg strength work, no treadmill |
| `GET ?kind=cardio` | the treadmill, not the squat |
| Search `ohp` | finds the barbell shoulder press by alias |
| `POST /exercises/{id}/did` twice | `tried = 2`, `last_tried` today |
| `PATCH tried = 0` | corrects a miscount |
| Your data → Workouts | three tabs on arrival; Filter opens type · muscle group · equipment |
| `cardio` + `machine` together | four rows — Skipping is cardio but needs no equipment, so it drops out |
| Filter with anything on | reads `Filter · 2` and stays green when closed |
| Diet card | still shows the workout habit's marks — nothing about logging changed |
| Tests | `backend/tests/test_workouts.py`, one row per line above |
