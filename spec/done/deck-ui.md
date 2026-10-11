# Deck UI — consuming /deck

> On Android the deck is gone: Home's widgets replace it
> (Home's widgets, `android/…/ui/home/Widgets.kt`), with the arithmetic below carried over.
> The web still draws it.

> Built and verified — every expected number reproduced in the browser at the
> dev anchor, and the icon stack confirmed against the 10–12 Aug week.
> The frontend's half of `spec/done/deck-api.md`: what each card
> shows, per range, computed from the rows the API returns. Written after the
> swap surfaced that "the dropdown works" and "the card answers the question"
> are different claims.

## Scope

**In:** range semantics per card, the coverage rule, the habit strip redesign,
empty states, and the exact numbers each configuration must show against the
imported August data. **Out:** writes, the report page (its own spec when
touched), English copy (follows this).

## How data arrives

One fetch at boot, no `from` — everything up to today. **All range switching is
client-side**: the rows are already in memory, and a dropdown tap must be
instant. Refetching per range becomes real only when history outgrows one
payload; that day is visible from afar (years away at ~500 rows/month) and
changes this spec, not the API.

The anchor is **the device's today** (30 Aug while writing). Every window ends
there.

## Ranges are calendar windows

| Range | Window |
|---|---|
| `aaj` | today |
| `7din` | today − 6 … today |
| `mahina` | the 1st … today (month-to-date, as the label says) |
| `sab` / `poora` | everything |

**The bug this kills:** diet's 7din currently averages the *last 7 days that
have logs* — a window that silently slides back to wherever data exists. A
quiet week then reports last month's average as this week's, which is a
flattering number, and flattering numbers are the ones the honesty rule exists
for. Paisa already uses calendar days; now everything does.

## The coverage rule — money and food divide differently

Same asymmetry the diet model already established (*you always eat; you do not
always log*):

| | Divide by | Because |
|---|---|---|
| **Paisa** | calendar days | a day with no spending is real data — ₹0 spent |
| **Diet** | logged days, **with coverage shown** | a day with no log is missing data, not fasting |

So diet's average line always carries its denominator: **`4/7 din logged`**.
An average over four days shown as a week's average is a lie of the 7-Aug kind.

## Paisa card

| Ring | `aaj` | `7din` | `mahina` |
|---|---|---|---|
| **Total** (month arc) | — structural: always month-to-date. `(fixed + spent) / income`, pale base = fixed | same | same |
| **Second ring** | aaj ka kharcha vs daily limit | avg/day (calendar 7) vs limit | avg/day (month-to-date) vs limit |

Expected against the data, anchored 30 Aug:

```
Total (always)   ₹83,087 / ₹1,03,000 · pale base ₹60,948
aaj              ₹3,400 / limit           (28 Aug — Rakhi day)
7din             ₹7,993 / 7  = ₹1,142/day (22–28)
mahina           ₹22,139 / 28 = ₹791/day
```

Anchored to the dev anchor, 28 Aug.

The Total ring deliberately ignores the range — it answers "mahine ka kya
haal", which has no 7-day version. Its caption must say `Mahina` so the
stillness reads as designed, not stuck.

## Diet card

All three rings move together — carbs currently stays frozen at today, which
is the second bug this spec kills.

| Range | Rings show | Sub-line |
|---|---|---|
| `aaj` | today's kcal / protein / carbs vs targets | — |
| `7din` | per-logged-day averages in the calendar week | `6/7 din logged` |
| `mahina` | per-logged-day averages, month-to-date | `23/28 din logged` |

Expected, anchored 30 Aug:

```
aaj      0 kcal · 0g · 0g            ← 28 Aug has no meal rows; true
7din     1,554 kcal · 78g · 185g     (9,324 / 465 / 1,111 over 6 logged days) · 6/7 din
mahina   1,950 kcal · 83g · 235g     (over 23 logged days) · 23/28 din
```

## Work card

| Range | Bars count |
|---|---|
| `Is hafte` | tasks **due within this calendar week** (Mon–Sun), plus those done this week |
| `Mahina` | same, month-to-date |
| `Poora` | everything, including undated |

This replaces the rolling `due ≤ TODAY+6` / `due ≤ 31` windows, which made
Hafta and Mahina show identical bars — the third thing that read as "the
dropdown does nothing".

**The hero list (top 3) ignores the range on purpose.** It answers "abhi kya
karna hai", which is not a windowed question. Stated here so it stops being
re-diagnosed as a bug.

Expected: Hafta `A 0/5` · Poora `A 1/23 · C 0/2 · S 0/2`.

## The habit strip — from workout strip to habit strip

Today the strip draws workouts only. The requirement: **every habit**, on the
same seven marks.

Constraints that bound the design:

1. **Deck height is sacred.** The strip lives inside the mode-glyph band
   precisely because that costs zero pixels. Any design adding a row per habit
   dies here — on the card.
2. **Manager, not coach.** A cigarette mark must inform, not scold. No red.
3. **Build and break are different sentences.** "Workout hua" fills a mark;
   "2 cigarettes" is a count. One visual can't say both.

### Decided: stacked icons, one per habit

The user's design, and it beats what was proposed before it:

```
habits    M      T      W      T      F      S      S
7 days   (🏋︎(🚬(🍺   ○    (🏋︎(🚬(🍺   ○    (🏋︎    (🚬    ○
```

**The two-word label matches the paisa card's projection row** (`per day` /
`saves`). Both cards' bottom bands now open with one short label per row, so
the deck reads the same way whichever card you are on — and neither needs a
legend or a heading.

Each habit has an **icon**; a day shows the icons of every habit logged that
day, **stacked with a slight overlap** — the avatar-stack pattern every review
UI already trained people to read. One habit, one icon. Three habits, three
icons peeking out. Nothing, an empty mark.

Why this wins:

- **The build/break machinery dissolves.** A fill needed a badge needed a
  legend, because a filled dot cannot say *which* habit. An icon just is the
  habit — the dumbbell and the cigarette need no explaining, no colour code,
  no red. Neutral pictures, stated plainly: manager, not coach.
- **It scales the right way.** A day with three habits gets visually *denser*,
  which is the true signal — that day had more going on.

Mechanics:

- **Icon by habit name, chosen in the frontend.** A small lookup — workout/gym
  → dumbbell, smoke/cigarette → cigarette, beer/alcohol → glass, run → shoe,
  meditate → lotus. **Unknown habit → its first letter in a small circle**, the
  same fallback the project chips use. Habits are user-defined free text, so
  the fallback is not an edge case; it is the contract.
- **The stack shows presence, not amounts.** ×2 cigarettes is still one
  cigarette icon — counts live in `@habits` and the report. A stack of tallies
  would turn the band into arithmetic.
- **Cap at three visible**, then `+n` — the avatar-stack convention, and the
  band's width is the hard limit.
- Icons are tiny filled shapes, not strokes — the H-that-was-a-dumbbell lesson.

Rejected on the way (kept for the record): one row per habit (kills the card's
height budget — right for `@habits` and the report, where it lives instead);
half/half colours in one mark (illegible past two, and colour = identity);
fill-for-builds + grey count badge (needed a legend to say *which* habit — the
icon answers that for free).

## The dev anchor — data that stays "today"

The imported month ends on 28 Aug and recedes further every day of
development, so `aaj` would be forever empty and every window would slowly
drain. The fix is to move the **clock**, never the data:

- **Dev builds anchor to the last day that has rows** — the deck behaves as if
  today were 28 Aug. Auto: `max(local_day)` across the fetched rows.
- **`VITE_ANCHOR=2026-08-14`** overrides it for time-travel — that week holds
  two three-habit days, which is how the stack gets seen.
- **Prod builds anchor to the device clock**, unconditionally.

Rows are never shifted: rewriting `local_day` to fake freshness would put lies
in the ledger to make a screen nicer, which is the exact trade this project
exists to refuse. When real logging starts, the data's last day *is* today and
the anchor becomes a no-op.

## Windows look back for money and food, forward for work

Paisa and diet windows end at the anchor — they are ledgers, and the ledger's
future is empty by definition. **Work windows cover the whole calendar week and
month including days ahead**, because tasks live in the future: `Mahina` means
"due this month", and a task due the 29th belongs in it on the 28th.

## Empty states## Empty states

| Case | Card says |
|---|---|
| `aaj`, nothing logged | zeros, plainly — plus diet's coverage line `aaj abhi kuch log nahi hua` |
| Strip with no logs this week | seven empty marks — blank is true, not broken |
| Window fully before the data | rings at zero with the coverage line carrying the reason |

## Definition of done

Every number in the three "Expected" blocks above, verified in the browser at
each dropdown position, at the dev anchor (28 Aug). Plus:

| Check | Expected |
|---|---|
| Carbs ring on `7din` | 185g — moves with the range like the others |
| Work bars | Hafta `A 0/5` (due 29 in the week ahead) · Poora `A 1/23 · C 0/2 · S 0/2` |
| Dropdown tap | zero network requests |
| Strip, anchored 28 Aug | week 24–30: seven empty marks — blank is true |
| Strip, `VITE_ANCHOR=2026-08-14` | 10th and 12th stack three icons (workout+cigarette+alcohol); 14th dumbbell alone; 15th cigarette alone |
