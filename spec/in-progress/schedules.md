# Schedules — the things Spica does on its own

> **Narrowed 2026-09-16 by `spec/in-progress/borrowed-runners.md`:** this is
> the runner for what must happen *without a laptop open* and for what has to
> exist on Android. Work capture and memory reconcile are not its jobs and
> should not be added to `JOBS` — a Claude Code scheduled task already reaches
> both this machine and Spica's data, on the subscription.
>
> **Changed 2026-10-08 by `spec/in-progress/nudges.md`:** a job may post
> **nudges** instead of a turn in the thread — `Job.posts` is `thread` or
> `nudges`. The morning brief is the first nudges job; nothing it says enters
> the thread. Categorise is still a thread job until it writes a `review` nudge.
>
> **Extended 2026-10-10 — § The set of schedules:** which schedules exist, who
> runs each, what each reads and writes, and the evening brief. The sections
> below it are the mechanism (table, dispatcher, due rule) and still hold.
>
> Status: built 2026-09-15, one step short of done — the crontab line is not
> installed, so the tick does not fire on its own yet. Everything it fires is
> built and tested, and `scripts/run_due.py` runs the same path by hand.
> Surface: backend (a table, four routes, one dispatcher) · frontend (one
> Profile group) · later, Android (WorkManager reads the same table).
> First job: the nightly categoriser, which exists and currently runs only
> when asked. `spec/in-progress/categorise.md`.

## The set of schedules

> Decided 2026-10-10. Nothing in this section is built except the morning
> brief, categorise and the dispatcher; § Build order says what is next.

The mechanism — table, dispatcher, due rule — is settled further down. The
question here is **what to schedule**. Four things decide each schedule, and a schedule is not specified until all four are
written down: **when** it fires, **who runs it**, **what it reads**, and **what
it writes**.

### One output: nudges

Every schedule's output is **nudges** — rows behind the bell, each opening a
page where the thing gets done (`nudges.md`). Not a turn in the thread, and not
a message that exists only in someone else's chat. Whoever runs the schedule,
the person finds the result in the same place, in the same shape:
`{kind, title, summary, refs, line?, facts?}`.

Two rules from `nudges.md` carry over unchanged because they are what keep a
daily run from becoming noise: **silent unless there is something to say**, and
**the page is live, the line is history** — numbers are worked out from the
rows when the page is drawn; the only stored sentence is what the agent said at
that hour.

### Two runners, and the line between them

| | **Spica's dispatcher** | **A Claude routine** |
|---|---|---|
| Where the clock lives | a `schedules` row, the person's to change in Profile ▸ Daily runs | claude.ai ▸ Routines — and only there (`work-sync.md` § *Why the schedule lives in Claude*) |
| Reads | Spica's rows, directly | Linear and Wispr Flow through the account's connectors; Spica through four MCP tools |
| The model | one call on Spica's own key | the subscription's |
| Works on the phone | yes — WorkManager reads the same row | n/a, it writes rows the phone then fetches |
| Good for | anything about the ledger; anything that must be punctual | anything whose *source* Spica cannot reach |

**The rule that sorts a job: a schedule *pulls* from a place Spica cannot see.**
Linear and Wispr Flow are such places, so the work sync is a Claude routine.
Spica's own rows are not, so everything about money, food and the day is
Spica's. The brief is not borrowed for the same reason the categoriser is not:
it reads the ledger, it should arrive when a laptop is shut, and the phone needs
it — the argument `borrowed-runners.md` made, and the one open question it left
(*the morning brief's runner*) is closed this way.

**A schedule pulls; a connector pushes.** To-dos made *inside* ChatGPT or
Claude need no schedule at all: the Spica connector is added to that surface
and the chat calls `tasks_upsert` the moment the task is made. A routine that
polled a chat history for tasks would be slower, would need a surface that
exposes it, and would write the same row. This is `agent-everywhere.md`'s
ground and costs nothing new here — the four tools already exist. (ChatGPT's
MCP connector is documented, not yet tried.)

### The schedules

| Schedule | Runner | Default | Reads | Writes | Silent when |
|---|---|---|---|---|---|
| **Work sync** | Claude routine (locked — not reopened here) | 07:00 and 18:00, set in claude.ai | Linear, Wispr Flow, Spica's open tasks | `tasks`, `source_documents`; **no nudge of its own** | — |
| **Your day** (`morning_brief`) | Spica | 08:00, grace 3 h | tasks, today's limit, protein to go, the plan | `day`, `meals`, `workout` nudges | nothing logged yet |
| **Dinner check** (`dinner_check`) | Spica | 19:00 | protein to go, what is logged | `dinner` nudge | dinner logged, or under 30 g to go |
| **Payments to check** (`categorise`) | Spica | 20:30, grace 12 h | unconfirmed payments | `review` nudge | nothing left to ask |
| **Your evening** (`evening_brief`) | Spica | **21:00, grace 3 h — new** | the day's tasks, spend, meals, and what the morning said | `evening` nudge | nothing logged today |
| **Reminder** | Spica, `repeat = once` | the time asked for | — | `reminder` nudge | — |

Work sync runs **before** the brief that reports it, on purpose: 07:00 feeds
08:00, 18:00 feeds 21:00. The order is a default the person can break, and the
brief survives a sync that did not run (below).

### The work sync does not nudge — the brief reports it

A sync that fired its own nudge would put a third thing at 07:00 for a person
who is about to get the brief at 08:00. Instead the brief reads what the sync
left: new tasks are in Start with like any task, and the line may name where
they came from (`tasks.source` — already stored).

**A sync that did not run is said, not hidden.** If the last `work_sync_finish`
is older than the sync's period plus slack, Your day carries one plain line —
*Work sync last ran Tuesday* — and its work numbers are marked as of then.
Unknown is not zero: a quiet Linear and a routine that never fired must not
look the same.

`work-sync.md` § `work_sync_finish` says the run writes **an agent turn in the
thread**. That predates `nudges.md` (2026-10-08) and is withdrawn: it writes
the `source_documents` rows, and the **summary is kept on the run** for the
brief to read. A routine's own chat in claude.ai still shows what it did — that
is Claude's output and needs nothing from Spica.

### Your evening — the new one

*Opens* a page in Home's clothes, as Your day does. The date as a heading, the
agent's line in the serif, then four sections. The page is live; every figure is
worked out when it is drawn, so a payment recategorised at 21:10 is already
right.

| Section | Shows | Honest edges |
|---|---|---|
| **Done** | tasks closed today, against what was due; the late ones still open | `no tasks due` is said as that, not as a zero |
| **Money** | spent against today's limit; the biggest category; money lent out is not spend | nothing logged → `nothing logged today`, never ₹0 |
| **Food** | protein and calories against target; meals logged of meals planned | the **coverage** is shown — `2 of 3 meals logged` — so a low number is read as low *or* unlogged |
| **Tomorrow** | up to three moves, each leading somewhere | below |

**Tomorrow is computed, not advised.** Each item exists because a number says
so, and each leads to a place where it gets done:

| If | Then Tomorrow says | Opens |
|---|---|---|
| protein ended short | the gap, and that it can be closed at breakfast | Meals today |
| tasks are late, or due tomorrow | the first one or two to start | the task |
| a category ran over, or the limit did | which, and by how much | the Paisa report |
| payments still unconfirmed | how many | Payments to check |

No item without a number behind it — a *"drink more water"* is the tip with no
run behind it that `nudges.md` already decided against. And no flattering
rounding: a day that missed its protein says so plainly, the metric most worth
showing being the one the person would rather not see.

**The model writes the line and only the line.** One call, handed the figures
as `facts` (the shape `morning_brief` already uses) and told to say what the day
was in the agent's own register; if the call fails the plain summary — the
`_day_summary` pattern — lands instead. The figures themselves come from
Spica's existing summaries (`paisa_summary`, `diet_summary`, `work_report`), so
the brief, the agent in chat, and the report pages can never disagree.

**Silent when nothing was logged today** — no task closed, no money, no meal. An
evening that says *nothing happened* is the daily *nothing to report* the
dispatcher already refuses to append.

### On demand

The same day, on request, is **a question in chat** — *"aaj ka din kaisa raha"*
— answered in the thread, because the person started that conversation. The
agent has `paisa_summary`, `diet_summary` and `work_report`; it needs no new
tool, and because the brief reads the same functions its answer matches the
evening nudge. In a Claude or ChatGPT chat with the Spica connector it is the
same question, answered there.

A Run now button on a Daily runs row is not built: `POST /schedules/{id}/run`
stays refused, for the reason given in § Decided against.

### Meal suggestions: no schedule of their own

The plan is a computation (`plan.today`), cached by a fingerprint of the rows it
read and shared with Home; it is recomputed when a meal is logged. The morning
brief already warms it at 08:00. A separate nightly job would compute a plan
the first meal logged would then invalidate, and would store a sentence about
stock that goes wrong overnight — the thing the cache is built not to do. The
evening brief says the *gap* to close tomorrow; the plan to close it arrives at
08:00 with real stock.

### Other schedules considered

| Idea | Verdict |
|---|---|
| **Weekly review** — the same four figures against last week, Sunday evening | Yes, later. `repeat = weekly` exists; the job is the evening brief's functions over seven days, with `no prior data` where there is none |
| **Udhaar follow-up** — someone owes you, for N days | When udhaar detection ships (`agent.md`) |
| **Bills and fixed payments due** | With commitments, which is parked |
| **Pantry restock** | A line in Tomorrow, not a schedule |
| **A midday protein check** | `dinner_check` is that, moved to when it can still change the day |
| **Memory reconcile** | Archived 2026-09-26 |

### Build order

1. **One day-summary function** — tasks, spend, food for a given local day,
   built from the three existing summaries; `morning_brief` and the evening
   brief both call it, and so can the agent. Tested against the live shape.
2. **`evening_brief`** in `JOBS`, the `evening` kind (the `ck_nudges_kind`
   check and `KINDS` both list the kinds, so a migration), its page on Android,
   tests and `n2n_eval` cases.
3. **Default runs created with the account**, including the new job
   (`nudges.md` Definition of done 7) — otherwise the phone's account has no
   evening run at all.
4. `dinner_check` and `categorise` as a `review` nudge — `nudges.md` owns
   them; this section only fixes their place in the day.
5. **Work sync on its clock** — `work-sync.md` build order 4 and 5: Render,
   then the routine. Until then it is verified locally and **not yet scheduled
   by anything**, which means the brief has no sync to report. The recency line
   above is what says so.
6. Weekly review.

### Decided against, in this section

- **The briefs on a Claude or ChatGPT schedule.** They read the ledger, which
  lives behind Spica; they must arrive with the laptop shut; the phone needs
  them. A routine would have to be handed every figure through MCP and write
  the nudge back — more surface, a worse model of what is already one function
  call in Spica — to save one model call a day. The conversation is 99% of the
  spend (`borrowed-runners.md`); the brief is not where the money is. *What
  would change this:* a brief that wants something only a subscription model
  has — long context across surfaces — at which point a routine calls a
  `brief_begin` tool and posts through the same nudge shape, with no change to
  the page.
- **A nudge from the work sync.** See above.
- **A schedule per surface.** One brief, in one place; the chat answer to *"how
  was my day"* is the on-demand version, not a second job.
- **Storing a plan overnight.** See *Meal suggestions*.
- **Generic advice in Tomorrow.** Every move has a number and a destination, or
  it is not there.

### Open

- **How many notifications a day.** `nudges.md` says one in the morning and at
  most two more. This section's day has Payments to check (20:30), Your evening
  (21:00) and the dinner check (19:00) — three. The recommended answer is to
  count **notifications, not nudges** and let the two evening runs, half an
  hour apart, arrive as one; the dinner check, silent most days, keeps the
  other slot. `nudges.md` rule 3 needs rewording whichever way it goes.
- **Evening time.** 21:00 sits after the review so the money figure is the
  filed one. If the person reviews payments later than 20:30 the order inverts;
  worth watching before it is tuned.
- **Whether the sync's second run (18:00) is worth it.** Two runs a day cost two
  routine runs against the subscription's daily allowance. Start with one at
  07:00 and add the evening one if the evening brief shows stale work.


## The problem

`scripts/categorise.py` is written, tested and correct, and **it has never run
on its own.** Its docstring suggests a crontab line; no crontab line exists. A
feature described as nightly that runs only when someone types a command is not
nightly, and the gap is invisible — the script works perfectly every time it is
tried by hand.

That is one job. Three more were known when this was written:

| Job | What it does | When | Runner |
|---|---|---|---|
| **categorise** | the second look at unconfirmed payments, and the questions it leaves | end of day | **here** — must not need a laptop, and must reach Android |
| **morning brief** | what to eat today, what is due, what is left | morning | **here** — decided 2026-10-10, § The set of schedules |
| **work capture** | pull the day's tasks in | twice a day | **borrowed** — a Claude cloud routine, `spec/work-sync.md`; its clock is in claude.ai, not here |

Each of them wants a *different* time, and the time is the user's business, not
a constant in a file. Three crontab lines edited over SSH is not a product; and
on the phone — which is where this ends up — there is no crontab at all.

So the decision is not "install a cron". It is **where a schedule lives**, and
the answer is: in the database, as a row, like everything else the user owns.

## What it does

### One dispatcher, many jobs

One line in the OS crontab, once, forever:

```
*/5 * * * *  cd …/backend && PYTHONPATH=. uv run python scripts/run_due.py
```

It asks one question — *which schedules are due?* — and runs those. Adding the
morning brief later adds a row, not a crontab line. On Android the same row is
read by WorkManager; the table is the contract, the runner is per-platform.
This is the whole reason the schedule is data and not configuration.

### `schedules`

```sql
CREATE TABLE schedules (
  id                  TEXT PRIMARY KEY,
  user_id             TEXT NOT NULL REFERENCES users(id),
  job                 TEXT NOT NULL,          -- categorise | morning_brief | evening_brief | dinner_check
  at_local_time       TIME NOT NULL,          -- the user's clock, their day
  repeat              TEXT NOT NULL DEFAULT 'daily',   -- daily | weekly | once
  days                INTEGER[] NOT NULL DEFAULT '{}', -- 0=Mon … 6=Sun, for weekly
  params              JSONB NOT NULL DEFAULT '{}',     -- what the job is run WITH
  enabled             BOOLEAN NOT NULL DEFAULT true,
  grace_hours         INTEGER NOT NULL DEFAULT 4,
  last_run_local_day  DATE,
  last_run_at         TIMESTAMPTZ,
  last_error          TEXT,
  created_at, updated_at, deleted_at
);
-- one schedule per job per user, and a retired one frees the name
CREATE UNIQUE INDEX uq_schedules_user_job ON schedules (user_id, job)
  WHERE deleted_at IS NULL;
```

**Nothing a run needs is hardcoded.** The `job` name selects *code*; every
input that code takes comes from the row — the time, the repeat, the grace, and
`params` for whatever is particular to that job. A job that reads a constant out
of a Python file is a setting the user cannot see and cannot change, which is
the thing this table exists to stop.

The registry in code holds only what is true of the *job itself*: its function,
the label the UI shows, and the defaults a brand-new row starts from. What the
user chose afterwards lives in the row and nowhere else.

`job` is a closed vocabulary, not free text: each value names code that exists.
An unknown `job` is a 422, because a schedule pointing at nothing would sit in
the UI looking like it works.

### Repeat

`daily` is what every job needs today, and it is not the only shape there will
ever be — so the column exists now rather than as a migration later, with the
two others that are already imaginable:

| `repeat` | Runs | `days` |
|---|---|---|
| `daily` | every day | ignored |
| `weekly` | on the listed weekdays | `{0,2,4}` = Mon, Wed, Fri |
| `once` | the next time it comes due, then turns itself off | ignored |

`once` is the one that earns its place immediately: *"kal subah yaad dila dena"*
is a schedule, not a reminder feature, and a row that disables itself after
running is the whole of it. A weekly Sunday review is the other.

### Due, and run at most once a day

```
due  ⟺  enabled
     ∧  today is a day this repeat runs        (daily · weekday ∈ days · once)
     ∧  now_local ≥ at_local_time
     ∧  last_run_local_day < today_local
     ∧  now_local < at_local_time + grace_hours
```

**The day stamp, not a timestamp, is what makes this safe.** A five-minute tick
that fired twice, a laptop that woke up, a dispatcher run by hand — none of
them can run a job twice in one day.

**And it is what gives catch-up for free.** The laptop is shut at 20:30; the
first tick at 09:00 next morning finds a job that is due and has not run today,
and runs it. A nightly review arriving late is worth having. That is exactly
what `grace_hours` bounds: a *morning* brief at 6pm is not late, it is wrong, so
it gets a short grace and is skipped. The nightly categoriser gets a long one.

### The agent writes it, and it is a real message

*For a nudges job this section holds with one change: what the agent writes
lands as nudges behind the bell, not as a turn — `nudges.md` § What makes a
nudge. The rest — one model call, no fake user message, silent unless it has
something to say — is the same.*

The output of a job is **a turn in the thread, written by the agent** — not a
template with numbers in it. Opening the app in the morning should read as the
agent having looked at the day and said something about it, because that is
what happened; the whole product is that the agent is the app.

So a job runs its tools and then makes **one model call** whose only task is to
say what it found, in the agent's own register and rules. The cards the tools
produced ride along with it, live and tappable, exactly as they do in a turn the
user asked for.

**No fake user message.** A scheduled run appends the agent turn alone. Writing
*"aaj ke payments dekh lo"* into the thread as though the user had typed it
would be the app putting words in their mouth, and it would come back as history
the model reads next turn.

**If the narration call fails, the turn still lands**, with a plain composed
line. The work happened; losing the report because a sentence could not be
written would be the worst of both.

**And a job is silent unless it has something to say.** A night where the
categoriser writes nothing, agrees with nothing and asks nothing appends
nothing. A thread that collects a daily *"nothing to report"* teaches the user
to scroll past the thing that matters on the night it does.

### Where the user sets it

Profile → **Daily runs**, the pattern Memory and Habits already use: one row per
job, showing its name, its time, and whether it is on.

```
DAILY RUNS
Review payments                          20:30   ●
  last run today · 14 waiting
Morning brief                            07:30   ○
  off
```

Tap the row to change the time, the dot to turn it off. `last_error` shows on
the row when the last run failed, because a scheduled job that silently stopped
working is worse than one that was never built.

### Defaults

| Job | Default | Why |
|---|---|---|
| categorise | **20:30**, on | The user reviews the day's spending before bed, not at the counter (`paisa-categorise.md` §4.2). Late enough that the day is done, early enough to still be awake |
| morning_brief | **08:00**, on, grace 3h | Built 2026-10-08 as nudges (`nudges.md`), and seeded on so Daily runs shows it working. A brief at 6pm is not late, it is wrong |
| evening_brief | **21:00**, on, grace 3h | After the 20:30 review, so the money it states is the filed figure. An evening brief at 7 the next morning is not late, it is wrong |

## Rules and edge cases

- **A failed job stamps the day anyway**, records `last_error`, and does not
  retry until tomorrow. The alternative — retry on the next tick — turns one
  broken job into 288 failures a day, and the tick is not the place to learn
  that an API key expired.
- **A job never blocks another.** Each runs in its own try; one throwing leaves
  the rest of the tick's jobs alone.
- **Local time is the user's time.** One user, one timezone, so `at_local_time`
  is read against the same local day the ledger already uses. When there are two
  users there is a `timezone` on `users` and this reads it; nothing else changes.
- **Turning a job off does not delete its row**, so its time survives being
  turned back on. A `once` job that has run is off, not deleted, for the same
  reason — and turning it on again arms it for the next occurrence.
- **Changing the time does not re-run today.** `last_run_local_day` already
  says it ran; moving 20:30 to 21:00 takes effect tomorrow. Running it now is
  what the agent and the script are for.

## Decided against

- **A crontab line per job.** The thing the user is choosing would live on a
  machine they do not use, in a syntax they did not ask for, and would not
  travel to the phone at all.
- **An in-process scheduler** (APScheduler, an asyncio loop in the FastAPI
  lifespan). It dies with the dev server, runs twice under `--reload`, and
  makes "did it run last night" depend on whether a terminal stayed open. The
  OS tick is one line and is already someone else's problem.
- **A `POST /schedules/{id}/run` route.** Running a job now is `categorise_now`
  for the agent and the script for the terminal — two doors already, and the
  same reason `categorise.md` refused a route.
- **Per-run history** (`schedule_runs` with a row per execution). `predictions`
  already records what the categoriser did, with more detail than a run log
  would carry. A table of "ran at 20:30, ok" answers nothing anyone asks.
- **Minute-level precision.** The tick is every five minutes, so a job set to
  20:30 runs between 20:30 and 20:35. Nobody is watching the clock for a
  nightly review, and a one-minute tick is twelve times the wake-ups for it.

## Definition of done

| # | Claim | How |
|---|---|---|
| 1 | Four routes: list, create, patch (time, enabled), delete | test |
| 2 | An unknown `job` is refused | test |
| 3 | Due is time + not-run-today + inside grace; each clause tested alone | test |
| 4 | A job runs at most once a local day, however many times the tick fires | test |
| 5 | A job missed overnight runs on the next tick inside its grace, and is skipped outside it | test |
| 6 | A throwing job stamps the day, records `last_error`, and does not stop the others | test |
| 7 | A run with nothing to report appends no turn; one with questions appends one agent turn, with the cards and no user message | test |
| 8 | A narration that fails still appends the turn | test |
| 9 | `once` disables itself after running; `weekly` runs only on its days | test |
| 10 | `params` reaches the job; no job reads a constant from code | test |
| 11 | The Profile group lists, edits, and toggles | **not yet** — written, typechecks and builds, but the app now gates on sign-in and that is the user's to do |

All but the last are green: `backend/tests/test_schedules.py`, 15 tests.

## Verified — the first scheduled run, 2026-09-15

`scripts/run_due.py` at 23:35, against the seeded 20:30 schedule inside its
12-hour grace — the catch-up case, on the first try, by accident:

```
Review payments: 14 payments check ke liye pending hain.
    · ₹180 · Egg roll · 72% sure
    · ₹512 · T-shirt · 62% sure
    …
```

and immediately after, `nothing due` — the day stamp refusing a second run.

In the thread it is one agent message (`seq 467`), model `schedule:categorise`,
fifteen cards, **and no user message before it**. The line was written by the
model, not composed from a template: *"14 payments check ke liye pending hain."*

## Open

- **Can the agent set a schedule?** *"roz 9 baje review kar do"* → one
  `manage_schedule` tool, the shape `manage_habit` already has. Recommended
  yes, and deliberately not in this spec: habits proved the UI and the tool are
  the same feature, but this one has a working UI answer first and the tool
  count is at 23 of 25.
- **Does a job notify?** On the web, no — the turn in the thread is the whole
  delivery. On Android a nightly review that nobody opens is a notification,
  and that is `capture.md`'s territory, not this one.
- ~~**The morning brief's content.**~~ Designed and built in
  `spec/in-progress/nudges.md`: Your day, Meals today and Workout.
- ~~**The morning brief's runner.**~~ Spica's own dispatcher — decided
  2026-10-10, § The set of schedules.
