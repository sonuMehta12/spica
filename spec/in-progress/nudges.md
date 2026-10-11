# Nudges — what Spica says without being asked

> Status: designed and built 2026-10-08. The server half — the `nudges` table,
> `GET /nudges`, `PATCH /nudges/{id}`, and `morning_brief` writing Your day,
> Meals today and Workout (`backend/tests/test_nudges.py`) — and the phone's
> bell, Nudges, Your day, Meals today and Workout today, seen live on the
> emulator. Still owed: `dinner_check`, `categorise` as a `review` nudge, the
> snooze route, and the rest of *Definition of done*.
> Design: the "Cortex nudges" canvas in the artifact gallery — the bell, the
> Nudges page, each nudge's page and the phone's notification, clickable.
> Surface: android (the bell, the pages, the notifications) · backend (a
> `nudges` table that scheduled jobs write)
> Builds on `spec/in-progress/morning-brief.md` (the requirement),
> `spec/in-progress/schedules.md` (the runner) and `spec/in-progress/today-plan.md`
> (the meals and workout plan).

## The problem

Spica prepares nothing unless asked: what to eat, what is due, what is left to
spend all wait for the person to type. Where it was going to speak first, it
was going to speak into the thread — `schedules.md` has a job's output land as
an agent turn — and that is the unprompted message the time-of-day greeting was
taken out for (`THEME.md`): it reads as a message nobody sent. Meanwhile the
day's plan lives in the Meals and Workout widgets, a page of content squeezed
into a glance.

## What it does

Whatever Spica prepares on its own is a **nudge**, and nudges live behind a
**bell**. The thread stays a conversation the person starts.

### The bell

- In the right-hand slot of the top bar, on Home and on Chat. On Chat the clear
  button sits left of it; both side slots are one fixed width, so the pill
  stays centred.
- **A Jamun dot** when a nudge has not been opened. No count and no red: a
  number to clear is a chore — manager, not coach.
- A tap opens **Nudges**, a page in Home's clothes: the ground, a large title,
  the round close. *Today* first, then *Earlier* (the last seven days). Each
  nudge is a card: its coin (kind, in its mode's ink and tint), a title, the
  time, the agent's line in the serif, and a dot until it has been opened. At
  the foot, *Change when nudges come* opens Profile ▸ Daily runs.
- Opening the page clears the bell's dot; a card's own dot clears when that
  nudge is opened.
- **Order**: newest run first; within one run — its nudges share a
  timestamp — Your day, then Meals, Workout, Dinner, Review, Reminder, so the
  brief's lead card leads.
- **A card with no line of its own** — Meals today stores none, since a
  sentence about meals goes stale first — shows one worked out from the live
  plan when it is drawn (*Lunch and dinner planned*, *Today's meals are
  done*), in the sans face and muted: it is not the agent speaking, so it is
  not in the serif. With nothing to work it out from, the card is one line.
- **The ⋮ names the run** — *From Your day · daily at 08:00*, a muted row
  above *Dismiss* and *Turn these off* — which is how rule 1 is kept without
  a label on every card. An unknown schedule leaves the row out.
- **Unknown is not empty**: a list that failed to load says *Couldn't load
  nudges* with *Try again*, and the bell shows no dot. *Nothing yet* is said
  only when the server answered with none.

### What makes a nudge

1. **It comes from a Daily run you can see.** Every nudge names the run that
   made it, and its ⋮ holds *Turn these off*, which switches that schedule off.
   Nothing nudges from a hidden trigger.
2. **It is silent unless it has something to say** — `schedules.md`'s rule: no
   question left, no nudge.
3. **One morning, at most two more a day.** The morning brief is one, however
   many cards it brings; a reminder the person asked for does not count.
4. **It expires with its day.** Yesterday's nudges are *Earlier* and read-only;
   after seven days they are gone from the page.
5. **It leads somewhere.** Each opens a page where the thing gets done — a meal
   logged, a task ticked, a question answered — or is done on its card.
   *Ask about this* hands it to Chat.
6. **The line is what was said; the page is live.** The agent's sentence is
   what it said at that hour, history like any chat message. Every number on
   the nudge's page is worked out from the rows when it is drawn.
7. **Never into the thread.** A nudge enters the conversation only when the
   person taps *Ask about this*.

### The nudges

| Nudge | Made by | When | Silent when | Opens |
|---|---|---|---|---|
| **Your day** | `morning_brief` | the brief's hour, 8:00 by default | the run is off | Your day |
| **Meals today** | `morning_brief` | with Your day | no meal left to plan | Meals today |
| **Workout** | `morning_brief` | with Your day | a rest day fits the week | Workout today |
| **Dinner check** | `dinner_check` | 19:00 | dinner logged, or under 30 g protein to go | Meals today |
| **Reminder** | a `once` schedule | the time asked for | — | its own card: *Done*, *Tomorrow* |
| **Payments to check** | `categorise` | nightly | nothing left to ask | Payments to check |

The morning run writes three cards so each has its own page and its own done
state, and sends **one** notification for them.

### The pages

- **Your day** — the date as a journal heading, the agent's line with *Spica
  · 8:00 · the numbers below are live*, then: *Start with* (three tasks,
  tickable, Today's rule), *Left to spend* and *Protein to go*, the next meal
  (→ Meals today), the workout (→ Workout today), and *Ask about your day*.
- **Meals today** — protein and calories as logged-plus-planned bars, so the
  plan's claim to close the gap can be checked; one card per meal still ahead
  (photo with its Commons credit, slot, dish, macros, *Log it*; an idea carries
  the amber dot and *Save to dishes*). No line on why a meal was picked and no
  label saying where it came from: the card is the meal, and the dot and the
  Save button already say which are ideas. Logging a meal re-plans the rest.
  It is `today-plan.md`'s plan, given a page.
- **Workout today** — the suggestion (photo, name, minutes, distance or
  exercises, the line on why), *Done* and *Not today*; one alternative from the
  exercise library, *Do this instead*. What Health Connect says is read on the
  phone and never sent.
- **Payments to check** — the categoriser's questions as Ask cards. An answer
  writes at once; the nudge is done when none are left. What it was sure of is
  one line, *5 more it was sure of — filed*.
- **A reminder** has no page: *Done* and *Tomorrow* are on its card and on its
  notification.

### Read, done, dismissed

Opened is read. Acting — logging from the plan, ticking, answering the last
question, *Done* — marks it done, and the card says so (*Logged*, *Done*).
*Not today* and dismissing from ⋮ hide it for the day.

### On the phone

- **Two notification channels**, Nudges and Reminders, so Android can silence
  one. A notification opens its nudge's page.
- **Delivery without a push service**: WorkManager reads the schedules the
  phone already shows, wakes at the brief's hour and every few hours, fetches
  new nudges and posts them. A push service comes in only if that proves late.
- **Quiet hours**: nothing between 22:00 and 7:00 except a reminder set for
  that time.

## Data

| What | Where |
|---|---|
| `nudges` | new: `id` (ULID), `user_id`, `kind` (`day`, `meals`, `workout`, `dinner`, `reminder`, `review`), `schedule_id`, `local_day`, `title`, `line` (as said), `refs` (live ids: tasks, dishes, the plan, transactions), `created_at`, `seen_at`, `done_at`, `dismissed_at` |
| `GET /nudges?days=7` | new — the page's list: the last `days` local days, today included, newest first. Dismissed ones are listed too; the phone hides them for their day |
| `PATCH /nudges/{id}` | new — `seen`, `done` or `dismissed`, each a switch: `true` stamps now, `false` clears. Someone else's, or a deleted one, is a 404 |
| `POST /nudges/{id}/snooze` | new — a reminder again tomorrow, as a `once` schedule |
| `morning_brief`, `dinner_check` | new jobs in `JOBS`; each writes nudges, not a thread turn |
| `categorise` | writes a `review` nudge instead of a thread turn |
| The pages | read live: tasks and the limit as Home does, the plan from `GET /plan/today` |

The `line` is the one stored sentence, and it is history — what was said at
8:00 — never a claim the page shows as current. Your day's is the agent's own,
one model call per brief (`jobs.narrate`, the plain summary if that call
fails); Workout's is the plan's line on why; Meals today has none, because its
page is the plan, live.

A nudges job is told the hour it ran at, and reads the plan at that clock — a
brief caught up at 10:00 plans from 10:00, and Home opened then shares its
cache.

## Rules and edge cases

- **Unknown is not zero**, as everywhere: a page with no plan yet says so.
- **A nudge whose rows changed still opens true**: its page is live, so a meal
  logged since 8:00 is already off the plan.
- **No targets**: Meals today plans ordinary meals and offers *Set target*, as
  Diet does.
- **A first-day account** gets no brief until something is logged — Getting
  started is its first-day voice.
- **Every account has its Daily runs.** A run seeded for "the first user"
  reaches whoever was created first, not the person signed in — the account
  the phone used had no runs at all, so its bell stayed empty. Default runs
  are created with the account, not by a migration that picks one.
- **A rest day is said once** — *Rest day*, with its reason, not a *Rest day*
  label over a *Rest* title.

## Changes to decisions already made

- `schedules.md` — *a job's output is a turn in the thread* is replaced: a job
  writes nudges, and the thread hears about one only when the person asks.
- `morning-brief.md`'s open questions, answered here: Spica's own dispatcher
  runs it; it reaches the phone by a WorkManager fetch; it is one line and
  three pages; daily at 8:00 by default, the person's to change; one model call
  per brief, with the plan call cached and shared with Home.
- `today-plan.md` — the Meals and Workout widgets stay for now; see Open.

## Decided against

| Option | Why not |
|---|---|
| Nudges as turns in the thread | An unprompted message in the person's conversation — the greeting's problem again |
| A count, or a red badge | A number to clear is a chore, and red means over a limit |
| A popover under the bell | Cards with actions and a week of history need a page |
| Tips with no run behind them ("drink water") | Every nudge comes from a schedule and leads to an action, or it is noise |
| A notification per card at 8:00 | Three at once is a notification machine; the morning sends one |

## Definition of done

1. The bell on both pages; the dot shows for an unopened nudge and clears as
   written; the pill stays centred on Chat. *Built; the dot's clearing seen,
   its first appearance not yet.*
2. Nudges lists today and the last seven days; each kind opens its page or
   acts on its card. *Built for day, meals and workout.*
3. `morning_brief` writes Your day, Meals today and Workout — and nothing into
   the thread — `backend/tests/test_nudges.py`. *Built.*
4. Turning a run off from a nudge's ⋮ switches its schedule off.
5. One notification for the morning; a reminder's *Done* and *Tomorrow* work
   from the notification.
6. `n2n_eval` gains the brief's cases.
7. Every account gets its default runs when it is created.
8. The brief writes no Workout nudge when a workout is already logged.

## Open

- **The Meals and Workout widgets** once these pages ship: they would hold the
  same plan twice. Keep, shrink Meals to *Next meal*, or remove.
- **Setting a reminder from chat** — *"kal subah yaad dila dena"* needs the
  `manage_schedule` tool (`schedules.md` § Open). Until then a reminder is
  added in Profile ▸ Daily runs.
- **The dinner check's threshold**, 30 g protein to go, is a guess to try.
- **The web** keeps the deck and gets no bell for now.
