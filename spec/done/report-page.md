# Report page — tabs by data, actions on rows

> Built and verified in the browser on real rows — tabs, ⋮ Edit from the
> report, ⋮ Delete on a habit log (15 → 14) and a task; sleep shows the 3
> real nights; Diet All interleaves 142 rows.
> The report was prototyped against `seed.ts`; its tabs still describe that
> seed (Kadam, Neend, Workout) rather than the data the app now holds. This
> spec re-cuts it against `/deck`, and gives every row the ⋮ the chat table
> already has.

## The problem

Two things, both visible on the paisa report today:

1. **The tabs are the seed's, not the data's.** Diet has *Neend · Kadam ·
   Workout* — no Meals tab at all, a Kadam tab with no source behind it, and
   Workout as if it were the only habit. Paisa has no *All*.
2. **Rows are read-only.** Edit and Delete exist only in the chat's `@paisa`
   table. The report is where you actually go looking for a wrong row, and
   it is the one place you cannot fix it.

## Tabs — derived from what the ledger holds

| Mode | Tabs | Rule |
|---|---|---|
| **Paisa** | `All` · `Pending` · one per category **present in the span** | *All* = every transaction in the span, newest first, signed by direction. Categories appear only if they have rows — a tab with nothing behind it is noise |
| **Diet** | `All` · `Meals` · `Habits` · `Sleep` | *All* = meals and habit logs interleaved, newest first. *Habits* = **every** habit log, not workouts alone — the strip stopped privileging workouts, the report follows. *Sleep* = `days.sleep_hours`, one row per night that has a value |
| **Kaam** | `All` · one per project | unchanged |

**`Kadam` (steps) goes.** There is no steps table and no source until Health
Connect (`spec/notes.md`). A tab that can only ever be empty is a promise the
app cannot keep; it returns the day steps do.

**Sleep stays its own tab, not part of *All*.** A night's sleep is a
measurement of a day, not an event that happened during it; interleaving
"7.5 h" between a dal and a cigarette reads wrong.

## Row actions — the same ⋮ everywhere

Every row on every tab gets the tray the chat table already has. One shared
component, so the two cannot drift.

| Row | Edit | Delete | Calls |
|---|---|---|---|
| Money (incl. *Pending* — a lending is a transaction) | composer edit mode, ✎ chip | soft delete | `PATCH` / `DELETE /transactions/{id}` |
| Meal | composer edit mode | soft delete, pantry moves reversed server-side | `PATCH` / `DELETE /meals/{id}` |
| Habit log | — (nothing to edit but the amount; later) | soft delete | `DELETE /habit-logs/{id}` |
| Sleep | — | — | `days` rows are edited when `days` gets a write path; not this spec |
| Task | tick / un-tick (existing) | soft delete | `PATCH` / `DELETE /tasks/{id}` |

**Optimistic, never silently** — the rule from `ledger-writes` applies
unchanged: the row leaves at once; if the server refuses it comes back marked
`· unsaved`. No confirm dialog: per-item delete *is* the user-facing control
(`CLAUDE.md`), and a dialog in front of it says we do not trust the tap.

**Editing from the report uses the same composer.** The composer already sits
over the report (*"one composer, placed wherever it is needed"*), so ⋮ → Edit
here does exactly what it does in chat: fills the bar, shows the ✎ chip,
`PATCH`es on send.

## What this needs from the adapter

Two things `/deck` already returns that the client currently drops:

- **Habit logs with ids** — today the adapter keeps only `{day, habit}` for the
  strip. Delete needs the id, the Habits tab needs amount and note.
- **Sleep from `days`** — today `SLEEP` is a hardcoded empty array. It becomes
  `days.filter(d => d.sleep_hours != null)`.

No API change. The report keeps computing on the client from rows, as
`spec/api.md` settled — which is also why the old `reports-api` feature is
retired: there is nothing for a reports API to return that `/deck` does not.

## Decided against

| Option | Why not |
|---|---|
| Keeping `Kadam` with a "no data" state | A tab that is empty by construction, not by circumstance. It comes back with its source |
| A separate Workout tab beside Habits | Workout is one habit; the strip already stopped singling it out |
| Sleep inside *All* | A measurement of a day, not an event in it |
| A confirm dialog on Delete | Per-item delete is the control; a dialog says we do not trust the tap. Optimistic-with-revert is the safety net |
| A reports API | The report computes from rows the client already holds; a second computation server-side is the duplicated maths `api.md` refused |

## Settled in review

| Question | Answer |
|---|---|
| Diet *All* | **Interleaved, each row in its own shape.** A meal row: name · type · main macros. A habit row: name with its count — *Cigarettes ×2*. The list reads like the day did |
| Editing a habit log | **Show the count; edit later.** Delete is available now; changing an amount inline is its own small control and can wait for the agent |
| Deleting a task from the report | **Yes.** The Claude Code plugin will create and delete tasks through the same `POST /tasks` and `DELETE /tasks/{id}` — one API, two callers — so giving the report the button now costs nothing later |

## Definition of done

| Check | Expected |
|---|---|
| Paisa tabs | `All`, `Pending`, then only categories with rows in the span |
| Diet tabs | `All`, `Meals`, `Habits`, `Sleep` — no Kadam |
| Habits tab at `VITE_ANCHOR=2026-08-14`, Mahina | rows for workout, cigarettes, alcohol — 15 logs, newest first |
| Sleep tab | the 3 real nights, hours shown, nothing invented |
| ⋮ → Delete on a money row | gone at once, `deleted_at` set, Aaj recomputes |
| ⋮ → Delete on a meal with a recipe | pantry moves reversed |
| ⋮ → Edit on a report row | composer fills, ✎ chip shows, send `PATCH`es the same id |
| Backend stopped, ⋮ → Delete | row returns, reads `· unsaved` |
