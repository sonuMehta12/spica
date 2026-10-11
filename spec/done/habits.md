# Habits you can add, rename and retire

> Status: shipped 2026-09-15
> Surface: both

## The problem

Three habits exist — Workout, Cigarettes, Alcohol — and they exist because a
migration inserted them. There is no other way one can come into being.

- **No route creates a habit.** `/habit-logs` writes, edits and deletes the
  *ticks*; the `habits` table itself has no endpoint at all.
- **No screen shows them.** Profile's Health group lists six targets and
  nothing else. The chain strip on the deck renders the marks, and a mark has
  no edit.
- **The agent can tick one and nothing more.** `log_day` matches a habit by
  name and, on a miss, returns `"no such habit"` — a dead end with no next
  step. *"Ab se meditation bhi track karna hai"* cannot be said.

Everything downstream already works: the chain strip, the week's counts, the
`habits_week` field. Only the thing being counted cannot be managed.

## What it does

**Four routes**, the shape every other library in this app already has:

```
GET    /habits            name, direction, unit, and this week's count
POST   /habits            client ULID, like every write
PATCH  /habits/{id}       name, direction, unit
DELETE /habits/{id}       soft
```

**`direction` gets a name on screen.** The column is `build | break` and it has
never been shown. *Workout* is one to build, *Cigarettes* one to break, and the
difference is the whole point of tracking them — a chain of ticks reads as
progress on one and as a warning on the other. On screen: **build** and
**break**, no cleverer word.

**`unit` stays optional.** Workout counts minutes, Alcohol counts units,
Cigarettes counts nothing — a tick is the whole fact. NULL means the log
carries no amount, and that is a real state, not a missing one.

**In Profile, under Health**, below the six targets: one row per habit, the
Memory group's pattern exactly — tap to edit in place, `×` to retire, an add
row at the bottom. That pattern is already built and already understood.

**One agent tool, `manage_habit`**, alongside `log_day`:

```
manage_habit(name, direction?, unit?, habit_id?, delete?)
```

Same shape as `keep_dish` and `log_exercise`: a name creates, an id edits. It
is not a second way to tick — `log_day` stays the only tick.

**`log_day` stops dead-ending.** On `"no such habit"` it now names the habits
that do exist, so the reply can be *"meditation track nahi ho raha — shuru
karun?"* rather than a refusal with nothing after it.

## Ask before starting one

*"Meditation kiya"* on an untracked habit does not create it. `log_day` comes
back with the tick unmade and the tracked list beside it, and the agent asks —
*"Meditation track nahi kar rahe. Shuru karun?"* — and starts it on a yes, in
the same turn as the tick.

A habit is a thing you decide to track, not a thing that appears because a word
was said once. The ladder already refuses to invent a dish for the same reason,
and a mistyped habit is worse than a mistyped dish: it shows on the deck every
day until noticed. One extra turn buys that.

## A habit is addressed by its name or its id

Both tools take either. This is not a convenience — it is the difference
between the feature working and not:

- The agent is never handed a habit id by anything it reads. Asked to rename
  one it had not just created, it refused rather than invent an id — correct,
  and a dead end. The name the user says now addresses the habit.
- Having just started a habit, the model passes the **id** it was handed into
  `log_day` — every other tool in this app is addressed by id, so it
  generalises. Name-only matching dropped that tick and the reply said the
  tracker had not taken it.

No habit is ever named like a ULID, so one lookup serves both and neither call
has to guess. A name that matches nothing returns the tracked list, the same
rule an unknown tick follows.

## Rules and edge cases

- **Retiring keeps the history.** Soft delete. The week strip still draws the
  days it was ticked; it just stops being offered. A habit deleted and its logs
  kept is the same rule meals and payments follow.
- **Two habits cannot share a name**, case-insensitively — `log_day` matches by
  name, and two *Workout*s make the tick ambiguous. A partial unique index on
  `deleted_at IS NULL`, as everywhere else.
- **Renaming does not orphan the logs**; they point at the id.
- **Changing `unit` does not rewrite old logs.** An amount logged in minutes
  stays minutes. Unknown is not zero, and a converted number would be invented.
- **No habit yet** is an empty Health list with one line saying what a habit is
  — the Memory group's empty state, which already reads well.

## Decided against

- **A `kind` on habits** — health, money, work. Three is not a taxonomy, and
  `direction` already carries the only distinction that changes the display.
- **Targets per habit** ("gym 5× a week"). The chain strip counts and does not
  judge, and a target would need a period, a reset, and a streak rule. It can
  come later from real use; guessing it now is the `meal_slot` mistake.
- **Editing a habit from the deck's chain strip.** The strip is 15px marks in
  the glyph's band. Profile is where settings live.
- **Letting `manage_habit` tick as well as manage.** `log_day` is the tick,
  and one verb per tool is the rule the tool count was cut by.

## Verified

- 231 backend tests pass. `tests/test_habits.py` holds 13: the routes, the
  case-insensitive uniqueness, a retired name being reusable, retiring keeping
  the logs, and one case per bug above — each checked to fail when the bug is
  put back.
- In Profile › Health: added a habit, flipped its direction, renamed it and
  retired it, against the running server.
- Through the agent, in order: *"roz journaling shuru kar raha hu, 10 minutes,
  aaj ka bhi log kar do"* → asked first; *"haan kar do"* → started **and**
  ticked, two cards; *"naam badal ke Morning pages kar do"* → renamed;
  *"ab track mat karo"* → retired, with a `deleted` card.

## Open

Nothing.
