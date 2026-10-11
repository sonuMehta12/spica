# Paisa Tracker · Personal OS

Implementation of the `Paisa Tracker.dc.html` design canvas
([project](https://claude.ai/design/p/c2472c4e-e00d-4390-ae65-0c21b951acc7)),
with the navigation and hero reworked since.

**Agent hi app hai.** One conversation, and a swipeable deck of modes above it.
There is no tab bar and no forms: you say or type a thing, the agent states the
assumption it made, and logs it.

```bash
npm install
npm run dev
```

## The primary component

A horizontal deck — one card per mode, **Paisa / Diet / Work**. Swipe across it.
The only indicator is a single glyph in the card's bottom-right corner — `₹`,
a heart, a briefcase — showing the mode you are on and nothing else; the order
is the label. Tapping it steps to the next mode, so the deck stays reachable
without a pointer.

Each card is a set of **concentric arcs** with the figures in a legend beside
them, keyed by colour dot:

| Mode | Outer → inner | Beside it |
| --- | --- | --- |
| Paisa | month, today | `Total ₹67,146 / ₹95,000` · `Aaj ₹0 / ₹351` |
| Diet | calories, protein, carbs | `Calories 867 / 2,050` · `Protein 48g / 135g` · `Carbs 95g / 220g` |
| Kaam | *bars, not arcs* — one per project | the next three tasks (below) |

The month arc has two strengths: a paler stretch for money already committed
(₹53,000 of fixed costs) and full strength for what's actually been logged. Same
hue either way, so it still reads as one series against its legend dot.

While Kaam is showing the composer stands down (no typing, mic or media) — it
can display tasks but not yet create them. The `+` tool tray still works, since
tools are cross-mode.

## Kaam

A **bar per project** — `novacart-chan`, `kestrel`, `cortex` — task count up the
y, projects across the x ([ProjectChart.tsx](src/components/ProjectChart.tsx)).
Each bar is stacked: solid is finished, translucent is what is left, so one mark
carries both how much a project holds and how far along it is. A red pip sits
above any project with something already overdue.

This started as concentric arcs, matching Paisa and Diet, and that was wrong on
three counts:

| | |
| --- | --- |
| **The denominator was fake** | Paisa's ring is spend against a *budget*, Diet's is intake against a *target* — numbers you chose. "3 of 5 tasks" has no target in it; the 5 is just however many tasks landed in the window, and adding one pushes the arc backwards. A full arc meant nothing |
| **Nesting implied a hierarchy** | An outer ring reads as containing the inner one. These three projects are siblings. (Diet gets away with it because calories, protein and carbs *are* layers of one meal) |
| **Arcs cannot be compared** | Arc length scales with radius, so 50% on the outer ring is physically longer than 50% on the inner one — which defeats the only reason to draw three projects together |

Bars share a baseline, which is the strongest encoding for comparing
magnitudes, and a fourth project just adds a column instead of running out of
radii.

Where Paisa and Diet put a legend, Kaam puts **the next three tasks**
([TaskList.tsx](src/components/TaskList.tsx)) — a fraction cannot tell you
*which* task matters. Each checkbox is drawn in its project's colour, keying the
row back to its bar without a separate swatch list.

| | |
| --- | --- |
| **Order** | Overdue first, then by date, then by priority within a day, then the undated. Blind to `done`, so ticking a task doesn't make it jump out from under your finger |
| **Three rows** | If today holds one task, tomorrow's two fill the space. The rest lives behind the card's menu — `Sab kaam` opens the full list in the conversation, scoped to work |
| **Ticking** | A finished task **stays**, struck through, reading `nipta` instead of the date it was due — claiming `2 din late` about work you completed would simply be false |
| **Range** | `Is hafte` · `Mahina` · `Poora`. No `Aaj` — one day says nothing about a project |

Two decisions worth keeping:

**An undated task is on the plate now, not never.** *Revised 2026-09-27.* The
first rule kept undated backlog under `Poora` only, so no pile could make a
week look like a failure. It held while the tasks were seed data with dates;
once tasks came from chat and Linear — which rarely carry one — the default
card stood at 0/0 over seven open tasks, which flattered exactly the way this
app refuses to. Now `Is hafte` and `Mahina` count every open task that is
undated, due in the window, or already late (a late one used to drop out of
the week, which flattered too), and a finished one in the window it was
finished or due in. The three rows list undated tasks after the dated ones.
If the pile makes the week look bad, the pile is real: give tasks a date, or
archive them.

**`doneDay` is why a ticked task behaves.** Without it there are only two
options, and both are wrong: finished work vanishes the instant you tick it, or
last week's ticks clog the card forever. Stamping the day lets today's
completions stay and yesterday's drop off.

> The deck shares one range across all three cards, but they don't offer the
> same ones. Every card computes on `rangeFor(mode, range)` — the range its own
> dropdown is showing — so the label and the numbers can't drift apart.

## Workout

A **week strip** on the Diet card — seven marks, Monday to Sunday, filled on the
days you trained ([ChainStrip.tsx](src/components/ChainStrip.tsx)).

It sits in the band every card already reserves along its bottom for the deck's
mode glyph, aligned with it. That band was empty on the left, so the strip is
positioned out of flow and **costs no height** — Diet measures the same as Paisa,
and the deck is exactly what it was before workouts existed. Its own row, even
trimmed, cost 28px, and since deck height follows its tallest card that landed on
Paisa and Kaam too.

Not a fourth ring, and the reason generalises: an arc answers *how much, against
a target*. Turning up is neither a magnitude nor a thing with a target — it is a
pattern across days, so it gets a row. An arc for a binary fact would sit at 0%
or 100% and look broken at both.

The day letter sits **inside** the mark, and a filled dumbbell labels the row.
Both are size decisions: at 16px a mark above its own label row would not fit the
glyph band at all, and a *stroked* dumbbell collapses into three lines that read
as a capital `H` — an eighth day letter, right beside `M T W T F S S`.

| Mark | |
| --- | --- |
| Filled green | Trained |
| Hollow, `ringIdle` | Did not train |
| Hollow, `lineSoft` | Still to come — a Thursday that hasn't happened is not one you skipped |
| Soft ring | Today |

**A skipped day is hollow, never red**, and the count reads `3 din` rather than
counting a streak. The product is positioned as a manager, not a coach, and this
strip is the one place that line is easy to cross — the visual is identical
either way, so the difference lives entirely in the copy.

## Neend aur kadam

Sleep and steps use the **same strip-and-list** as money — a tab per series, then
`label · date · value`. Money, sleep and steps all reduce to that shape, so
[ItemList.tsx](src/components/report/ItemList.tsx) renders every tab in the
report and tone (green / red / amber) is the only thing that varies.

| Mode | Tabs |
| --- | --- |
| Kaam | `Sab`, then one per project |
| Paisa | `Pending`, each category, `Other` last |
| Diet | `Neend`, `Kadam` |

A sleep row carries the **window**, not just the length — `12:25am–6:35am` —
because the heuristic produces *when*, and that is the part worth correcting.
Inferred nights are marked `· andaaza`; confirmed ones are not. A steps row says
its distance from target rather than repeating the number.

## Compose mode

Tapping the composer — or the mic — folds the whole deck away so the conversation
gets the screen. Only the **menu button** stays put.

Getting this right on a phone took three fixes that a laptop never surfaces:

| Problem on device | Cause | Fix |
| --- | --- | --- |
| Menu scrolled off the top | Default `interactive-widget=resizes-visual` leaves the layout viewport full-height when the keyboard opens, so the browser scrolls the page to reveal the input | `interactive-widget=resizes-content` in the viewport meta, `--app-h` from `visualViewport` for iOS (which ignores that key), and `overflow: hidden` on html/body so the document cannot scroll at all |
| Every scroll dismissed compose mode | `pointerdown` cannot tell a tap from the start of a scroll — and a touchpad scroll fires no pointer events, so it looked fine on desktop | Dismiss on `pointerup` only when the finger moved < 8px in < 500ms ([Conversation.tsx](src/components/Conversation.tsx)) |
| No reliable way back | — | A tap on empty transcript space brings the deck back, and with the keyboard up there is plenty of it |

`composing` is also **not** tied to input blur: clicking a bubble to press a
button or select text blurs the input natively, and the card must not spring back
for that. It ends only on an explicit signal — a tap on empty transcript space,
`Escape`, opening the drawer, or the mic finishing.
Bubbles are marked `data-bubble` so the tap handler can tell them from
background. The collapsed card is `inert`, so its select and kebab leave the tab
order while the menu stays reachable.

## Card notes

**Text first, the card below — never a sentence inside a card**
(`spec/done/card-redesign.md`). What the agent says stands on its own above the
card; the card holds only data.

- A **server card** — a confirm, a table, a suggestion — carries no note. The
  agent's reply above it is the commentary, and two sentences would say the
  same thing.
- A **phone-built card** — the + menu's To-do, Pantry, Recipes and Cash flow —
  has no reply to stand on, so it gets one line above it
  ([notes.ts](src/agent/notes.ts)):

| Card | Example |
| --- | --- |
| `@todo` | *1 task is past its date — "Fix the cart bug", 3 days now. Clear that one first.* |
| `@pantry` | *Use the Paneer first — it came in 6 days ago. Out of Eggs.* |
| `@recipes` | *None eaten yet — saved and never cooked.* |
| `@cashflow` | *The ₹4,000 lent out is not counted until it comes back.* |

Two clauses: **what the data says**, then **what it means next** — and never a
figure the card already leads with. A card with nothing in it draws only its
line, never an empty box under a sentence.

Lines and cards are derived **at render time, not stored on the message** —
a + menu message carries only an id. Delete a row or tick a task and both
re-read correctly; a stored note would quietly start lying.

### One voice for the agent

The app had drifted into three treatments for agent prose — the greeting at 13px
ink, the confirmation body at 12px grey, the notes at 11px grey — so nothing
marked which words were the agent's. They now share one style, `agentVoice`
([bubble.ts](src/components/messages/bubble.ts)):

| | Face | Colour |
| --- | --- | --- |
| **The agent speaking** | Newsreader (serif) | ink |
| Data, labels, figures | Anek Latin, tabular figures | ink · muted |

Grey was the wrong instinct: it reads as a footnote, which is the opposite of
what these lines are for. `THEME.md` holds the type rules.

### One list, by when

Two ways in, same card ([TodoCard.tsx](src/components/messages/TodoCard.tsx)):
the Kaam card's `Sab kaam` opens it scoped to work, `@todo` opens everything.

Rows group by what is owed next — **Late**, **Today**, **This week**,
**Later** — rather than by project: late work is the one thing here you are
already behind on, so it leads. Each row is a live checkbox, the title, and the
project as a chip. Priority shows as `P1`/`P2` and only where it is set — `P3`
is the normal case and printing it would be noise. Undated backlog sits under
Later rather than being hidden.

## The mascot

Spica has a mark, the Constellation ([Mascot.tsx](src/components/Mascot.tsx)),
and it is the same mark in both places it appears: the avatar beside what the
agent says, and the mark signing the drawer. On a 96-unit grid it is a centre dot
(r 10), four mid dots on the axes (r 6) and four small dots on the diagonals
(r 3.5), all one colour — the brand. On the phone's launcher it is white on a
Jamun tile.

Motion moves dots and never resizes the outer ones: each outer dot travels
along its own spoke from the centre, so the mark keeps its shape in every state.

### One mark moves at a time

| State | What moves | When |
| --- | --- | --- |
| `still` | nothing | Every avatar in the transcript, and the drawer mark |
| `idle` | the centre breathes, 1 → 1.06 over 2.5s | Only the newest agent mark |
| `listening` | the outer dots drift 6% outward and back | Mic is running |
| `thinking` | the outer dots dim in turn, clockwise from the top | Agent is working |
| `saving` | the outer dots draw in, spring back past their place, settle (600ms) | The lock, just before the reply |
| `done` | the same beat, then held at rest | The newest reply, until the next turn |

`still` is a state, not the absence of one: a mark beside a message from ten
minutes ago is a portrait. When the live row appears, even the newest transcript
mark goes still — a column of pulsing avatars reads as a glitch, not as life.

The live row at the end of the transcript carries the whole sequence —
**listening → thinking → lock** — then disappears as the reply lands. Today the
delay is theatre over a synchronous stub, but the shape is the real one, so
wiring `/chat` in later is a swap rather than a rewrite.

**Small sizes get their own build, not a shrunk one.** Below 24px the diagonal
dots land under a pixel, so they are dropped and the rest grow: the centre to
r 12, the mid dots to r 8 and out to 18 and 78 — the way an app icon differs
from its own marketing art. Between 24 and 48px the outer dots gain half a unit
(6.5 and 4) to keep their weight. Animation lives in `global.css` under
`.cx-mascot`, keyed off `data-state`, so it runs on the compositor.

## The conversation

Standard chat sides: **the agent on the left behind its face, you on the right.**
Your messages carry no avatar — you already know which side is yours — and the
agent's face is drawn once per run, so a burst of cards from it doesn't repeat
the same portrait down the column. Bubble tails point up at the avatar
([MessageRow.tsx](src/components/messages/MessageRow.tsx)).

A reply is just the agent's formatted text — a headline with the logged figure,
then one line of explanation. There is no separate "assumption" strip above it
and no pill echoing the entry below it: the reply already says what was logged
and what it did to the day's remaining budget, and the arcs above show the rest.

## Report

Drawer → **Reports**, or **tap the card itself**. A glance, not an analysis —
anything deeper is the agent's job, which is why the composer floats over this
page too.

Tapping a hero card anywhere that isn't a control opens that card's report,
already switched to its mode. The press has to be measured rather than trusted:
the deck's swipe starts with the same `pointerdown`, so this only fires on
release, after under 8px of movement and under 500ms — and never when the press
landed on a `button`, `select` or checkbox. Ticking a task is the task's tap, not
the card's.

| Section | |
| --- | --- |
| **Numbers** | Four figures in one container. No rules between them — the shared card already does the grouping. `Limit ke andar` counts **transactions** logged while that day was still inside budget, by running total; `Net pending` carries no delta, so it shows none rather than a placeholder |
| **Numbers** (Diet) | Protein, calories, **neend and kadam**. Target-hit and days-logged move behind the card's `More` menu — same overflow pattern as the hero card, and the kebab only renders when there is something in it |
| **Kahan gaya** (Paisa) | One donut, legend on the left. **The full circle is the money that came in (₹95,000)** — the period's spend fills only its share of it, same reading as the hero card |
| **Kitni baar theek raha** (Diet) | Nested arcs, reusing the home screen's `ConcentricRings` + `RingLegend`. Two donuts cost twice the height for a question with one answer, so each metric contributes one ring: how many logged days landed in band — calories within ±200 of target, protein at Theek or better. The tiles already say *how much*; the rings say *how often* |
| **Tab strip** | `Pending` first and active by default, then the spend categories, with `Other` forced last — it's the leftovers bucket, so size shouldn't rank it. Scrolls left-to-right inside the content width rather than wrapping or bleeding to the edge |
| **Items** | The selected tab's contents, in place. Pending rows and ledger rows share one shape, so the sign alone decides the colour |

Selecting a category dims the other slices and puts its figure in the donut's
centre. Nothing opens the conversation — the report answers in place.

The page is reachable two ways: the drawer's **Reports** row, and a **Reports**
entry in the composer's `+` tray (or `@reports`). Tools that open a page declare
`opens` instead of `build`, so they route to the overlay rather than replying
inline ([tools.ts](src/agent/tools.ts)).

> **The ring under-reads on purpose.** It counts only logged transactions, so a
> full month shows ~15% of income rather than the ~71% on the home card — the
> ₹53,000 of fixed costs are not transactions and so are not in it.

Colour follows *intent* throughout: spend up is red, protein up is green.
The comparison period is clamped to the start of the month (there is no day 0)
and labelled when it comes out shorter; a period with no prior data reads
`no prior data` rather than a fabricated delta.

## Your data

Drawer → **Your data**. The library made visible — six sections: Recipes,
Pantry, Articles, Videos, Places, Workouts — kept as structure even where a
section is empty today. Not a bookmark folder; the substrate the agent reasons
over. The inbox of low-confidence guesses and the "agent built this" pointer at
the ledger were removed on 2026-09-04: the first needs an agent that does not
exist yet, the second belongs to the report.

Two ideas do the work:

1. **The pantry and the dishes are real.** *Dishes* reads `GET /dishes`: your
   library is what you saved (★) or have eaten (✓ 3×, counted from the ledger's
   meal lines, never stored), and *Cook now* is computed against live pantry
   stock. *Pantry* is the same idea one table down.

   **The pantry is real.** *Pantry* reads the `pantry_moves` ledger through
   `GET /pantry`: Stock groups foods into Buy, Stocked and Always here with the
   status derived every render, and Moves is the signed-grams ledger behind it.
   Every action writes a row — a quantity is never edited. The other five
   sections are still seed data from `data/vault.ts`, and the Recipes
   card's *"6 can be made now"* answers seed against seed until recipes go live.
2. **The uncomfortable number.** *"16 save karke chhod diye"* — saved and never
   opened. Same spirit as `"Other" 21.8%` in the report: the metric you'd rather
   not see is the one worth surfacing.

**No export**, deliberately. The control it stands in for is per-item removal:
every capture has an `×` that drops it immediately.

`@pantry` and `@recipes` in the chat read from the same
[src/data/vault.ts](src/data/vault.ts), so the tool cards and this page can never
disagree.

> The captures in `vault.ts` are **invented placeholder content** — unlike the
> ledger in `seed.ts`, which is real August data. Only the shapes matter; swap
> the rows for real extension output.

## Stack

Vite + React 19 + TypeScript, no UI or state library. Design tokens live in
[src/theme.ts](src/theme.ts) and every colour resolves through them; components
use inline styles with [src/styles/global.css](src/styles/global.css) carrying
the reset, hover affordances and keyframes that inline styles can't express.

## Layout

| Path | What lives there |
| --- | --- |
| [src/state/usePersonaOS.ts](src/state/usePersonaOS.ts) | All app state; `heroFor()` builds each mode's ring specs |
| [src/lib/useSwipe.ts](src/lib/useSwipe.ts) | Drag-to-page: axis lock, commit threshold, edge rubber-band |
| [src/components/ModeDeck.tsx](src/components/ModeDeck.tsx) | Home's deck: the modes' cards under their names |
| [src/components/Deck.tsx](src/components/Deck.tsx) | `DeckTabs` + `DeckPages`: the names (an ARIA tablist) and the swipeable ring under them — Home's deck and the Report's modes |
| [src/components/ConcentricRings.tsx](src/components/ConcentricRings.tsx) | The arcs — number-free by design |
| [src/components/RingLegend.tsx](src/components/RingLegend.tsx) | Colour dot + label + `value / total` |
| [src/agent/messages.ts](src/agent/messages.ts) | Card builders: confirmations, ledger tables, cash flow, pantry, recipes |
| [src/agent/tools.ts](src/agent/tools.ts) | The `+` tray's tool registry |
| [src/data/seed.ts](src/data/seed.ts) | August ledger, meal log, targets, tunable settings |

## How the money maths works

`dailySpendLimit()` in [usePersonaOS.ts](src/state/usePersonaOS.ts) is the one
number the whole Paisa mode hangs off:

```
fromBank  = max(0, savingsTarget − moneyAlreadyLentOut)
spendable = bankBalance − committed − fromBank
limit     = spendable ÷ daysLeftInMonth
```

Money already lent out counts toward the savings target, so only the shortfall
gets ring-fenced. With the seeded figures that's ₹351/day.

## Live data, not snapshots

Ledger cards store row **ids**, not copies. Delete a row from one `@paisa`
table and it vanishes from every other table on screen, from today's pill
strip, and from every arc that counted it — including the ones rendered
off-screen on other deck pages. See `resolve()` in
[TableCard.tsx](src/components/messages/TableCard.tsx).

## Stubs — what is not real yet

The design's own placeholders, carried over honestly rather than faked deeper:

- **Voice.** The home composer's mic replays [src/agent/script.ts](src/agent/script.ts)
  after a 1.7s waveform. The first run's *About you* screen is the one real
  mic: the browser's Web Speech API (English, India), filling the box and never
  sending on its own — and no mic at all where the browser has none.
- **Media capture** returns a "coming soon" card.
- **Kaam reads, it does not write.** Tasks come from `seedTodos`; nothing yet
  mirrors them out of a repo, and the composer cannot create one. The intended
  path is a Claude Code `PostToolUse` hook that parses `- [ ]` checkboxes and
  posts the delta with repo, path, line and branch — no new format to adopt.
  Mirrored tasks would stay read-only here; you tick them in the repo.
- **Drawer rows** (Billing, Permissions, Notifications, Help) return a stub card. Profile, Reports and Your data are real.
- **Diet figures** are the canvas's 9-day placeholder set — its notes say the
  real `Healthy_Eating_Tracker.xlsx` was never uploaded.
- **Carbs** is a fixed 95g against a 220g target. Meals only carry protein and
  kcal, so unlike the other two arcs the carbs ring does not move when you log
  something. It needs a per-meal carb figure to become real.
- **Sleep and steps detection.** Steps would come from Health Connect; sleep has
  no OS API without a wearable, so it is inferred from night window + screen-off
  + significant-motion. **None of that can run in a web version** — the data
  in [`SLEEP`/`STEPS`](src/data/seed.ts) is seeded. What *is* real here is every
  UI surface it needs, including the confirmed-vs-estimated distinction that the
  correction loop depends on.
- **Fat and fibre** behind the card's `More` menu are fixed strings.
- **Persistence.** State is in memory; a reload resets to the seed.

## Departures from the canvas

1. **Device chrome.** The canvas wraps the screen in an iOS bezel, status bar
   and home indicator (`ios-frame.jsx`) — mockup scaffolding, not product. The
   app fills the viewport instead, and the hard-coded `64px` / `42px` insets the
   bezel needed became `env(safe-area-inset-*)`. Above 520px wide it sits as a
   centred phone-width column.
2. **Navigation.** The canvas's story-circle row and slim two-segment budget bar
   are both gone: the circles became the swipe deck, and the bar became the outer
   arc. The page title went with them — the active dot names the mode.
3. **Range picker.** A native `<select>`, so mobile gets the platform picker,
   rather than the canvas's custom pill with a baked-in `▾`.

## Known design-side issue

The suggestion chips are not filtered by mode: Paisa mode offers "Sattu drink"
and "Office thali" alongside "Commute". This is faithful to the canvas
(`baseSuggs` there has no mode filter) but reads like an oversight, given the
canvas notes describe them as the Diet mode's meal plan. The fix is a one-line
filter in the `suggestions` memo in
[usePersonaOS.ts](src/state/usePersonaOS.ts) — left alone pending a call on
intended behaviour.
