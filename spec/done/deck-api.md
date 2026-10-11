# The deck API and the swap

> Working doc. Covers the two remaining phase-1 features together, because they
> are one contract seen from two sides: `get-deck` (the endpoint) and
> `frontend-fetch` (the prototype stops importing `seed.ts`).
> Reads from: `spec/api.md` (rows-never-views is settled there), the three
> done data-model specs, `frontend/src/data/seed.ts`.

## Scope

**In:** the one read endpoint the deck needs, its exact response shape, the
frontend swap, loading/error behaviour, and the verification numbers.
**Out:** writes (`spec/api.md` § ledger writes), sync, auth beyond the existing
bearer token, and anything Android.

## The contract

```
GET /deck?from=2026-08-23&to=2026-08-29     # a window
GET /deck?to=2026-08-29                     # 'sab' — no start
```

One call, all three modes — a swipe between cards must never show a loading
state, so the data for all of them arrives together. Changing the range is a
deliberate tap and may refetch.

**Dates, not named ranges.** `?range=7din` was the first draft and it was wrong
twice. Hinglish does not belong on the wire — the spec's own rule puts it in UI
copy only. And worse, `aaj` would mean *the server's* today: a server in another
timezone turns an 11:30pm chai into tomorrow, which is the exact bug `local_day`
exists to prevent.

**The client sends the dates because only the client knows what day it is
where the user is.** The dropdown stays `aaj / 7din / 30din / sab` in the UI; it
resolves to ISO dates at the boundary. A later report page wanting an arbitrary
window then needs no new parameter.

**Rows, never aggregates.** `spec/api.md` settled this: the client computes, so
`metrics.ts`, `tasks.ts` and `workouts.ts` keep doing the maths they already do.
The server's only intelligence here is *which rows*.

### Which rows — per mode, the window plus what the card structurally needs

| Mode | In the response |
|---|---|
| paisa | `transactions` in the range window **∪ the current month** (the arc is monthly regardless of range) · the latest `balance_check` |
| diet | `meal_logs`, `habit_logs`, `days` in the window **∪ the current week** (the chain strip is weekly regardless of range) · all `habits` |
| work | all `projects` (not archived) · `tasks` that are open or doing, **plus** tasks done within the window (`doneDay` keeps today's ticks visible) |

The union matters: `range=aaj` must not blank the month arc or the week strip.
Those two windows are structural, not selected.

### Response shape

```jsonc
{
  "as_of": "2026-08-29T09:12:00Z",
  "from": "2026-08-23",
  "to": "2026-08-29",
  "paisa": { "transactions": [...], "balance_check": {...} },
  "diet":  { "meals": [...], "habits": [...], "habit_logs": [...], "days": [...] },
  "work":  { "projects": [...], "tasks": [...] }
}
```

Rows are wire-shaped like the DB, not like the prototype: `amount_paise`,
`local_day: "2026-08-27"`, ULID ids. The prototype adapts at its boundary —
the server does not serve one client's convenience types.

## The swap — every seed export, accounted for

`seed.ts` is imported in 12 files, and it exports more than rows. Nothing may
survive by accident:

| seed export | After the swap |
|---|---|
| `seedTx`, `seedMeals`, `seedWorkouts`, `seedTodos`, `PROJECTS`, `PENDING` | rows from `/deck`, mapped in one adapter file |
| `TODAY`, `DATA_MONTH`, `DATA_YEAR`, `MONTH_DAYS` | the real clock. The seed froze time at 22 Aug; that lie ends here |
| `DIET_TODAY`, `CARBS_TODAY` | derived from rows, as the maths already does |
| `UDHAAR_PENDING` | derived: `lent − repayments settling it` |
| `PROTEIN_TARGET`, `KCAL_TARGET`, `CARB_TARGET`, `SLEEP_TARGET_MIN`, `STEP_TARGET` | a client `config.ts` at the time; since `spec/done/users-profile.md` they come from the `users` row via `/deck.profile` |
| `SALARY`, `FIXED`, `LOCKED` | deleted — derived from the imported Setup rows (gap 3, closed) |
| `SLEEP`, `STEPS` | see gaps 1–2 below |
| `INCOME_SOURCES`, `MENU_ROWS`, `DEFAULTS` | static UI copy — moves to `config.ts`, was never data |

**One adapter file** (`frontend/src/data/api.ts`): fetches, maps wire rows to
the existing prototype types (`Tx`, `Meal`, `Todo`, …), and is the only file
that knows both shapes. `metrics.ts`, `tasks.ts`, `workouts.ts` keep their
maths byte-identical — their imports re-point, their logic does not move.

## Three honest gaps the swap exposes

The seed papered over these; real rows cannot. The third is now closed.

**1. Steps have no table.** `STEPS` was invented data for a strip on the report
page. Health Connect is phase 6. Until then the strip shows `no data` — the
honesty rule already covers this; the seed was the violation.

**2. Sleep is nearly empty.** `days.sleep_hours` has 3 real values in 24 days.
The report renders what exists and shows coverage — not a fabricated week.

**3. Income and fixed costs — closed, and imported.** Six rows added, tagged
`fixed`; see `spec/done/paisa-import.md`. The arc's numbers now derive:
₹22,139 spendable, ₹60,948 fixed, ₹42,052 total, ₹10,921 unaccounted — all
queries, nothing stored.

The user's correction is what settled it: `MERE HAATH MEIN THA` named a
subtraction as if it were money held, and *ghar ka paisa is spent, not held*.
So `SALARY`, `FIXED` and `LOCKED` leave the client with the rest of `seed.ts`
rather than surviving as constants.

## Loading and error states

| State | Behaviour |
|---|---|
| First load | the deck skeleton, once. After that rows live in memory |
| Swipe between modes | **zero** network, zero flicker — the data is already there |
| Range change | one refetch; the old rows stay visible until the new ones land |
| Request fails | say so, plainly. Never render zeros as if they were data — a `0` the server did not send is a fabricated number |

## Auth: the seam now, the lock later

Three things that get confused, separated:

| | Means | Status |
|---|---|---|
| Authentication | *who are you* — login | Deferred (`spec/notes.md`) |
| Authorization | *are you allowed* | Deferred with it |
| `user_id` plumbing | where the code **gets** the id | **Needed today** — every query filters on it |

The first two are deferred; the third cannot be, because every query already
carries `WHERE user_id = …`. The multi-user audit did the expensive half — the
column exists everywhere — so this costs one function:

```python
def current_user() -> str:
    # Today: one user. Later: read the token, verify it, return its id.
    # Auth lands inside THIS function; no endpoint changes.
    return "me"
```

Every endpoint takes the user from this dependency, never from a constant of
its own. **The frame now, the lock later:** adding auth later becomes one file
instead of every endpoint.

**No bearer token yet.** On localhost the server is reachable only from this
machine, so a token is friction without security. It becomes real the day this
is deployed, and it lands in the same function. `spec/api.md`'s token section
stands — it just is not wired yet.

CORS allows the Vite origin in dev. Nothing else.

## Definition of done

**The restated test.** The original test — "the app looks exactly the same" —
was written when the plan was to import `seed.ts` itself. The plan changed: the
DB holds real August, the seed holds fiction, so the pixels will rightly
differ. What must not change is the *machinery*:

1. Same components, same maths — `metrics.ts`, `tasks.ts`, `workouts.ts`
   logically untouched (imports re-pointed only)
2. `grep -r "data/seed" frontend/src` returns nothing; `seed.ts` is deleted
3. `npm run typecheck` clean

**And the numbers must be the DB's, verifiable by query:**

| Card, full window | Expected (from the imported data) |
|---|---|
| Paisa: spendable expense (excl. `fixed`) | ₹22,139 |
| Paisa: pale arc (`fixed` paid) | ₹60,948 |
| Paisa: arc total | ₹42,052 |
| Paisa: udhaar pending | ₹4,000 (Dost 2) |
| Paisa: latest balance check | ₹8,992 · 22 Aug |
| Diet: meals in ledger | 119 rows, 23 days |
| Diet: chain strip | workout marks on 10, 12, 14 Aug — 3, not 8 |
| Work: bars | novacart 1/23 · cortex 0/2 · kestrel 0/2 |
| Work: "aaj" list | the 5 tasks due 2026-08-29, hero cap 3 + arrow |

**Behavioural:**

| Check | Expected |
|---|---|
| Swipe paisa → diet → work | 0 network requests |
| Range `sab` → `7din` | exactly 1 request |
| Backend stopped, app reloaded | error state, no fabricated zeros |
| A single-day window on a quiet day | empty states, month arc and week strip still drawn |

## Open

- Does `/deck` also serve the report page's longer comparisons, or does the
  report get its own `GET /rows?since=` later? Leaning: deck only, report spec
  decides its own needs when it is next touched.
