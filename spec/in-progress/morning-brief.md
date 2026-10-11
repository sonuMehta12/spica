# The morning brief — Spica speaks first

> Status: **requirement recorded, 2026-10-08 — to brainstorm before anything is
> built.** Builds on `spec/in-progress/schedules.md` (built: the schedules
> table, the dispatcher, one job) and `spec/in-progress/borrowed-runners.md`
> (research: who runs a routine), which left the brief's runner undecided.
> Surface: backend · Android (the notification) · web (the thread)

## The problem

Spica only answers. Every suggestion — what to eat, what is due, what is left
to spend — waits for the person to ask, at the moment they are least likely to:
busy, hungry, already late. The agent knows enough to look at the day before
the person does, and it never does.

## What it would do

Once a morning — or every few days; the person chooses — Spica prepares the
day in the background and leaves it waiting:

- **Food** — what to eat today, from the pantry, the protein still to go and
  the dishes the person actually eats (`suggest_dishes` already does this when
  asked).
- **Work** — what is due today, what is late, the next one or two to start
  (`work_report`).
- **Money** — today's limit, and anything committed that falls due (the paisa
  summary).

It arrives as **one turn in the thread**, in the agent's own voice — the shape
every scheduled job already has (`jobs.narrate`, `post_turn`) — and on Android
as **a notification** that opens it.

**It knows the person.** Their targets and memories, their usual meals and
spend, the corrections they have made — the same rows the agent reads in
conversation. Nothing new is learned for the brief; it is the agent, early.

**It does the work in advance.** The suggestions are worked out when the job
runs, so opening the app shows them at once rather than starting a model call.

## What already exists

| Piece | Where |
|---|---|
| A schedules table the person owns — time, repeat, grace, params — and a dispatcher that runs what is due | `spec/in-progress/schedules.md` |
| A job's output as one agent turn, no user message | `app/agent/jobs.py` — `narrate`, `post_turn` |
| Meal suggestions from the pantry and targets | `suggest_dishes` |
| Tasks due, late and open | `work_report` |
| Today's limit | the paisa summary |
| Research on borrowed runners — Claude and ChatGPT scheduled tasks | `spec/in-progress/borrowed-runners.md` |

## Rules already true

- **The time lives in one place** — a `schedules` row, whoever runs it.
- **A suggestion is never a stored sentence about the person's data.** The
  turn is what was said that morning; any card in it names live rows — dish
  ids, task ids — so a row changed since still shows true.

## Open

- ~~**Who runs it.**~~ Spica's own dispatcher — decided 2026-10-10 in
  `spec/in-progress/schedules.md` § The set of schedules. It reads the ledger,
  must arrive with the laptop shut, and the phone needs it; a borrowed runner
  is kept for sources Spica cannot reach.
- **Whether an outside assistant may write into the ledger.** Reading the
  person's rows to prepare suggestions is low risk. A third party writing rows
  in the background is a trust question, and the work sync is the only one
  allowed to today (`spec/work-sync.md`) — tasks only, through four tools.
  Whether the brief may gather and *create* — tasks from what it read, say —
  is to be decided, not assumed.
- **How a notification reaches the phone.** Scheduled on the device, or pushed
  from the server — the second needs a push service the app does not have.
- **What is in it, and how long it is.** All three modes, or only what
  changed; one line each or a card each.
- **The cadence by default** — daily at a morning hour, or every few days.
- **Whether the agent can set a schedule from chat** — *"roz subah 8 baje
  bata dena"* — a `manage_schedule` tool, already proposed in
  `spec/in-progress/schedules.md` § Open.
- **The cost** — one model call per brief per person per run.
