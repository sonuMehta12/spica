# Home as your day

> Status: in build
> Surface: android · backend (one field)

## The problem

Home on the phone is a stack of widgets — Today, Money, Diet, Activity, Habits —
each its own island. To know how the day is going you read five cards and put
the day back together yourself: what you already did, what is next, and how far
the numbers have moved. The design canvas *Spica mood* settled a different Home
over rows I–P: the day itself, as one rail, with the numbers and the nudges a
tap away. This is row P, built.

## What it does

**Header, on the ground.** The top bar keeps the menu and the Home | Chat pill;
the bell's place holds a caret pointing left (see *The glance panel*). Under it,
the week, Monday to Sunday, today in a Jamun circle, days ahead lighter — no
date heading above it: the week already says where you are. Tapping a day does
nothing yet.

**The day, on a white sheet** that rises over the ground with rounded top
corners and a handle. A thin line joins every moment:

- **What happened today**, oldest first: each spend, meal, habit log and task
  you finished, at the time it happened. A round node in the mode's colour with
  a white glyph; the title; one figure on the right (`−₹200`, `14 g`, `2nd
  today` for a counted habit). The line is solid here.
- **Now**: a dark pill at the current time.
- **Up next — the only open card.** The first thing still ahead, with its one
  action: a planned meal (`Log it`), the workout (`Done`), a task (`Done`).
- **The rest of today**, the line dashed: the plan's other meals, today's
  schedules (`Plan tomorrow's meals`, at their time), and the tasks due today or
  late. A task carries a round checkbox on the right and its project under the
  title, with `· 2 days late` in red when it is late. Anything without a clock
  time comes last, under *Any time*.

**Tap a row and its widget opens as a sheet**: a spend opens Money, a meal Diet,
a habit Habits, a task Today's tasks. The sheet is plain white, one surface: a
handle, a close, then the same widget Home used to show, drawn on the sheet
itself rather than as a card inside it (two widgets are split by a hairline),
and a button to its report.

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
- Steps from Health Connect on the phone, as the Activity widget reads them.

## Rules and edge cases

- **A row without a time is not given one.** A log written before times were
  kept, or one still being saved, sits at the end of what happened, its time a
  dash.
- **Unknown is a dash.** No limit yet (no income this month), no protein target,
  no sleep logged, Health Connect not connected: the tile shows `—`, never 0.
- **Nothing to come** — no plan, no schedule left, no task due: the sheet says
  *Nothing planned for the rest of today*, and the Up next card is not drawn.
- **Every number is counted from rows at render time**: ticking a task moves the
  tasks tile, logging the planned lunch moves protein and kcal.
- **Late is red, the estimate is the amber dot**, as everywhere else.

## Decided against

- **A coloured top on the sheets, and the widget as a card inside the sheet**:
  tried; the user wanted one white surface.
- **A date heading over the week**: the week says it.
- **Two open cards** (Up next and First task, as on the canvas's earlier rows):
  the user asked for one open item; the first task waits as a row.
- **A sentence from the agent at Now** (row L's brief): tried on the canvas and
  removed by the user.
- **A big So far card with two glasses**: the numbers live in the glance panel;
  the day gets the room.
- **Widgets inside the day as cards**: they open from the rows they belong to.

## The look — on trial on Home

The day rail and the glance panel use the look the canvas settled in rows N–P:
Figtree (heavy for titles and numbers; it draws ₹, the true minus and tabular
figures) and the mode colours deepened together in OKLCH (L 0.52, C 0.117), so a
solid node carries a white glyph at 5 : 1 or better. They are tokens of their
own (`F.day`, `C.deep*`), used on Home only. Whether the rest of the app follows
is not decided; `THEME.md` § The day look says so.

## Open

- Whether the day look replaces Anek Latin and the current mode stops app-wide.
- Tapping another day in the week.
- Times for planned meals: the plan has slots, not clock times, so a planned
  meal's time column shows its slot.
