# Home as your day

> Status: in build
> Surface: android · backend (two fields: a habit log's time, a meal's dish)

## The problem

Home on the phone is a stack of widgets — Today, Money, Diet, Activity, Habits —
each its own island. To know how the day is going you read five cards and put
the day back together yourself: what you already did, what is next, and how far
the numbers have moved. The design canvas *Spica mood* settled a different Home
over rows I–P: the day itself, as one rail, with the numbers and the nudges a
tap away. This is row P, built. The sheets a row opens, another day in the
week, and the open card for each kind of item were settled after on the canvas
*Spica day sheets*.

## What it does

**Header, on the ground.** The top bar keeps the menu and the Home | Chat pill;
the bell's place holds a caret pointing left (see *The glance panel*). Under it,
the week, Monday to Sunday, today in a Jamun circle, days ahead lighter — no
date heading above it: the week already says where you are. The box on its
left names the month of the week showing, and the strip swipes a week at a
time.

**The day, on a white sheet** that rises over the ground with rounded top
corners and a handle. A thin line joins every moment:

- **What happened today**, oldest first: each spend, meal, habit log and task
  you finished, at the time it happened. A round node in the mode's colour with
  a white glyph; the title; one figure on the right (`−₹200`, `14 g`, `2nd
  today` for a counted habit). The line is solid here.
- **Now**: a dark pill at the current time.
- **Up next — the only open card.** The first thing still ahead, with its one
  action (see *The Up next card*).
- **The rest of today**, the line dashed: the plan's other meals, today's
  schedules (`Plan tomorrow's meals`, at their time), and the tasks due today or
  late. A task carries a round checkbox on the right and its project under the
  title, with `· 2 days late` in red when it is late. Anything without a clock
  time comes last, under *Any time*.

### The Up next card

One shape for every kind, so the eye learns it once: the mode's tint, a white
badge `Up next · <kind>`, the item's picture on the left at 60 when it has
one, the name beside it (15, at most two lines), one short line under the
name, then one Jamun button and at most one text link.

| Kind | Picture | The line | Button · link |
|---|---|---|---|
| Planned meal | the dish's photo | `P 46 · 720 kcal · C 84 · F 18`, the amber dot first while it is Spica's idea | **Log it** · *Something else* (opens Diet) |
| The workout | the plan's photo | `60 min · 6 exercises` | **Done** · *See the session* (opens Activity) |
| A task | none | project · `2 days late` in red · `from <source>` | **Done** |
| A schedule | none | how often it runs, then what it does, in a few words | none |

The time column holds the item's time (bold) or nothing; a planned meal's slot
is the badge's second word.

### A row's sheet

Tapping a row opens its sheet; tapping the Up next card or a tile in the
glance panel does the same. Every sheet has one frame: plain white, one
surface, a handle and a close; the mode's name in Figtree heavy and the day it
shows under it (`Today · Sat, 17 Oct`, or `Wed, 14 Oct`); the big numbers;
that day's rows for the mode, **the tapped row picked out** in the mode's tint
with its figure in the mode's ink; and a full-width Jamun button to the
mode's report.

- **Money.** A ring of spent against today's limit, the spend in its centre;
  beside it `₹1,240 left` over `of ₹1,600 today`. Then expected saving (red
  below the savings target), committed (a link to its page) and lent out.
  Then *Total*: `₹18,420 out · ₹62,000 in` with a thin bar of out against in.
  Then the day's spends. *Open Money*.
  - Over the limit: the ring full and red, the spend in its centre, `₹540
    over` in red beside it, `today's limit was ₹1,600` under.
  - No limit yet (salary not in): an empty ring with the spend in its centre,
    `— left`, `No limit yet: salary isn't in.` and *See what's committed*.
    Expected saving is a dash; *Total* reads `₹360 out · nothing in yet` and
    has no bar.
  - The limit at or below zero keeps today's copy: *Everything left this
    month is committed.*
- **Diet.** A ring of protein against the target, grams in its centre; beside
  it `62g to go` over `of 120g today`. Then kcal (`1,240 / 2,200`), carbs and
  fat. Then *Eaten*, then *Still planned*: each meal a row with a 68 photo
  tile on the left (the bowl icon on the same tile when there is no photo),
  the slot and time above the name, and one macro line with protein first. A
  planned meal's tile has a dashed frame — not yet, as on the rail — and a
  *Log it* on the right. *Open Diet*.
- **A habit.** The sheet is the tapped habit's alone, its glyph in a coin
  beside its name and what kind of habit it is under it. *Open Habits* goes
  to all of them.
  - One you are cutting (smoking) is counted: `2` today, `14` this week, `19`
    last week; then a bar per day with its count on top, today in ink; then
    today's logs (`1st today`, `2nd today`).
  - One you are building with minutes (workout) counts days: `4 of 7` days,
    `180 min` this week, `45 min` a session; then minutes per day as bars;
    then the recent sessions with their names and lengths.
  - One you are building without minutes (meditation) shows the week as day
    marks, the minutes inside a mark when the log has them; then the recent
    sittings.
- **To-do.** `4` open today, `1` late in red, `2` done today. Then the open
  tasks (due today or late) with their round boxes, then *Done today* with
  the time each was ticked, then *All tasks · 11 open*. *Open Work*.
- **Activity.** The Activity row is the plan's workout, so its sheet is the
  session: what kind (`Activity · today, strength`), the name, the amber
  `Suggested · 60 min · 6 exercises`, then the exercises in order, each with
  its sets and load, four shown and `+ 2 more · see the whole session`. A run
  leads with the plan's photo and shows the plan's minutes. Then *This week*:
  a bar per day of active minutes, strength and running told apart by
  lightness, and three totals (strength minutes, running minutes, steps
  today). **Done** at the foot. No report button: Activity has no report.

### Another day in the week

Tapping a day in the strip shows that day on the sheet; tapping today returns
to Now. The picked day carries a Jamun ring; today keeps its filled circle.
At the top of the sheet sit the day (`Wed, 14 Oct`), one line of totals
counted from its rows (`−₹600 spent · 84g protein · 2 tasks done`), and a
**Today** pill whose caret points the way today lies. Swiping the strip alone
changes nothing on the sheet.

- **A past day**: what happened, at its times, on a solid line. No Now, no Up
  next, nothing ahead.
- **A day ahead**: the schedules that run that weekday, at their times, and
  the tasks due that day with live boxes, on a dashed line. Under them:
  *Meals are planned on the day.*
- **A past day with nothing logged**: the totals are dashes and one line says
  `Nothing logged on Mon, 12 Oct.`
- **A day in an earlier month**, while it is read: the totals are dashes and
  three ghost rows stand in for the rail.

**A sheet opened from another day shows that day.** Its rows and its totals
are that day's. A limit or a target belongs to today, so on another day the
rings give way to the totals: Money shows what was spent that day, how many
spends, the month's average a day up to it, and the month's spend up to it,
with one line saying a past day has no limit to show. Diet shows that day's
grams and kcal without the ring.

**The glance panel.** The caret slides a panel in from the right over the day:
*Today so far* — six key numbers as tiles (left to spend today, protein to go,
kcal to go, last night's sleep, tasks open with how many are late, steps) — then
the nudges written in the last week and not put away, newest first, and *All
nudges*. A tile opens its widget sheet; a nudge opens its page. The caret's dot
is the bell's dot: a nudge written since the panel was last opened.

**One layer at a time.** The panel, a widget sheet and the menu never stack on
Home. Opening one closes whichever is open — a tile in the panel closes the
panel and opens the sheet. Back closes the open layer first.

## Data

Read only; nothing new is stored.

- Spends, meals, habit logs, tasks, schedules, the plan, nudges, the limit,
  targets, sleep — the deck and the endpoints the app already reads.
- **Times.** `transactions.occurred_at` and `meal_logs.occurred_at` are on the
  wire already; the app now keeps them. `habit_logs.occurred_at` is added to the
  deck's habit log (`HabitLogOut`). A task's place is its `done_at`.
- **Another day.** The deck is read up to today with no lower bound, so every
  meal, habit log and task is already on the phone. Spends are kept for the
  current month only; a day in an earlier month reads the deck once with
  `from` and `to` at that day — the server widens it to that day's month on its
  own — and the answer is kept for the session.
- **Pictures.** A planned meal and the plan's workout carry `image_url` and
  `image_credit` from the plan; those are the Up next card's picture and the
  Diet sheet's planned tiles. A logged meal is linked to its dishes through
  `meal_items`, but the deck does not say which, so **the deck's meal gains
  `dish_id`**: the first dish among its items, or null. The phone already
  holds the dish library with its pictures, so a logged meal's tile shows its
  dish's photo when the dish has one and the bowl icon otherwise. A meal is
  never matched to a dish by its name.
- **The session.** The plan's workout carries its exercises, each with a name,
  a detail line (`4 × 8 · 60 kg`) and its `exercise_id` when it is from the
  library. The phone already holds the exercise library, with each exercise's
  `image_url` and `source_url`, so a library exercise shows its picture as the
  thumbnail and opens its `source_url` to watch it. An exercise the model
  invented has neither: a numbered mark stands in, and nothing opens.
- **This week's activity** is Health Connect's exercise sessions and steps,
  read on the phone as the Activity widget reads them. A session carries its
  kind, minutes and day, which is all the week's bars need; steps are today's
  only.
- **A habit's minutes** are its logs' `amount` when the habit's `unit` is
  minutes; with any other unit, or none, the habit is drawn as day marks.

### What the code has, and what it gains

| Piece | Today | It gains |
|---|---|---|
| The rail | `DayRail.rail(s, now)` builds today only | a day to build: past, today or ahead |
| The week strip | `selected` and `onDay` exist, unwired | Home holds the picked day; tapping today clears it |
| The deck | `Api.fetchDeck(to)` | an optional `from`, for a day in an earlier month |
| Opening a sheet | `onRow(DaySheet)` | the row's key and the day, so the sheet picks the row and shows that day; a habit row also says which habit |
| The sheets | the old Home widgets drawn bare | one composable per sheet in the day look, reading the same state |
| The deck's meal | no dish | `dish_id` (backend, with its test) |

Everything else the sheets show — the limit and its parts, targets, the
plan with its pictures and exercises, the dish and exercise libraries,
schedules, a task's source and `done_at`, sleep, Health Connect — the phone
reads already.

## Rules and edge cases

- **A row without a time is not given one.** A log written before times were
  kept, or one still being saved, sits at the end of what happened, its time a
  dash.
- **Unknown is a dash.** No limit yet, no protein target, no sleep logged,
  Health Connect not connected, a macro no meal records: `—`, never 0. A
  ring with nothing to measure against is drawn empty.
- **Nothing to come** — no plan, no schedule left, no task due: the sheet says
  *Nothing planned for the rest of today*, and the Up next card is not drawn.
- **Every number is counted from rows at render time**: ticking a task moves the
  tasks tile, logging the planned lunch moves protein and kcal, deleting a spend
  moves a past day's total.
- **Late is red, the estimate is the amber dot**, as everywhere else. Expected
  saving is red only below a savings target that exists.
- **A habit day with no log is an empty mark**, never a zero bar.
- **The picked row is found by its key**, so a sheet opened from a row that
  is then deleted shows the sheet with nothing picked.

## Decided against

- **A coloured top on the sheets, and the widget as a card inside the sheet**:
  tried; the user wanted one white surface.
- **The old Home widgets on the sheets**: they were cards in another face; each
  sheet is drawn in the day look instead.
- **A bar for today's money, and two rings (today and the month)**: tried on
  the canvas. One ring for today, and the month as a thin bar under *Total*.
- **One Habits sheet for all habits**: a log opens its own habit's sheet; the
  whole list is one tap further, behind *Open Habits*.
- **A separate session sheet for the workout**: the suggestion and the workout
  are one thing, so the Activity sheet is the session.
- **A sheet for a run you already did**, with splits, and **a rest-day
  sheet**: not needed. A run is a run, whatever its time of day.
- **The exercise list on the Up next card**: the card names the session; the
  exercises are a tap away.
- **A full-width photo on the Up next card, and a grey box of macros under the
  name**: both took the room the day needs.
- **A date heading over the week**: the week says it.
- **Two open cards** (Up next and First task, as on the canvas's earlier rows):
  the user asked for one open item; the first task waits as a row.
- **A sentence from the agent at Now** (row L's brief): tried on the canvas and
  removed by the user.
- **A big So far card with two glasses**: the numbers live in the glance panel;
  the day gets the room.

## The look — on trial on Home

The day rail and the glance panel use the look the canvas settled in rows N–P:
Figtree (heavy for titles and numbers; it draws ₹, the true minus and tabular
figures) and the mode colours deepened together in OKLCH (L 0.52, C 0.117), so a
solid node carries a white glyph at 5 : 1 or better. They are tokens of their
own (`F.day`, `C.deep*`), used on Home only. Whether the rest of the app follows
is not decided; `THEME.md` § The day look says so.

## Open

- Whether the day look replaces Anek Latin and the current mode stops app-wide.
