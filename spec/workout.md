# Workout

> Status: shipped
> Surface: frontend

## The problem

Diet records what went in and nothing about what was spent. A day where you ate
2,000 kcal and trained is not the same day as one where you ate 2,000 and did
not, and right now the app cannot tell them apart.

The thing worth knowing is not how hard a session was. It is **whether you keep
turning up** — and that is a pattern across days, not a number for today.

## What it does

A **week strip** on the Diet card: seven marks, Monday to Sunday, one per day of
the current week. A filled mark is a day you trained.

```
Diet card
│  rings + legend              calories · protein · carbs  (today)
│
└  🏋 M T W T F S S                                   [♡]   ← one band
      ● ● ○ ● ○ · ·
```

The strip sits in the band already reserved along the bottom of **every** card
for the deck's mode glyph, horizontally aligned with it. That band was empty on
its left, so the strip is positioned out of flow and **costs no height at all**.

Each mark is a circle with the **day letter inside it** — the label and the mark
are one object rather than two stacked rows, which is what keeps the whole strip
to a single line.

A **dumbbell icon** sits at the left, saying what the marks are counting. The row
carries **no visible number**: seven marks already show it, and the count lives on
the group's accessible label for anyone who cannot see them.

| Mark | Means |
| --- | --- |
| Filled, green, white letter | Trained |
| Hollow, grey letter | Did not train |
| Hollow, faint | Still to come this week |
| Ring around it | Today |

Tapping the strip opens the Diet report, same as tapping anywhere else on the
card.

## Why not a fourth ring

The obvious move was another arc next to calories, protein and carbs. It is
wrong for the same reason the Kaam arcs were wrong — the shape has to match the
question.

| | Rings answer | Workout asks |
| --- | --- | --- |
| Question | How much, against a target | Did I turn up, over time |
| Value | A magnitude | Effectively binary |
| Window | Today | The week |
| Unit | g / kcal | none |

An arc for a binary fact would be either 0% or 100% and look broken at both. And
a fourth radius would shrink the other three for a series that does not belong
beside them anyway.

## Record, not streak — the line that matters

This is the one decision in the file with a real risk attached.

"Never break the chain" is **coach** mechanics, and the product is positioned as
a **manager**. The visual is the same either way; the difference is entirely in
what the app says about it, so the copy rules are the spec:

- A skipped day is **hollow, never red.** Red is a scolding, and a scolding is a
  thing people avoid by not opening the app.
- The count is stated plainly — *"3 din is hafte"* — never *"3 day streak, don't
  break it!"*
- **No weekly target in v1.** A target turns every rest day into a miss. It also
  drags in rest-day configuration, which is a whole feature for a question
  nobody asked.

The strip records what happened. It does not have an opinion about it.

## Data

A workout done is a **ledger** entry — an instance. The library already holds the
templates: `vault.ts` has `ItemKind: 'workout'` for plans like *Push / Pull /
Legs*. Same template/instance split as Recipe → Meal log.

```ts
interface Workout {
  id: string;
  day: number;        // day of the month, like every other ledger row
  kind: string;       // 'Push', 'Legs', 'Cardio', 'Walk'
  minutes?: number;   // optional — absence is not a failure to record
  source: 'manual' | 'voice';
}
```

`kind` is a free string, not an enum. The agent should not refuse to log
*"kabaddi"* because it is not on a list.

**Weekday comes from the date**, not from stored data:
`new Date(DATA_YEAR, DATA_MONTH, day).getDay()`. Storing a weekday would be a
second source of truth for something the date already knows.

## Rules and edge cases

- **The week is the calendar week containing today, Monday first.** Not a rolling
  seven days: rolling would put the letters in a scrambled order (`T W T F S S
  M`) and the whole point of letters is that they read normally.
- **Future days in the week are drawn faint**, not hollow. A Thursday that has not
  happened is not a Thursday you skipped, and the strip must not imply it was.
- **Two workouts in one day** count as one filled mark. The strip answers "did
  you turn up", and turning up twice is still turning up.
- **An empty week** renders all seven marks hollow with no message. Seven empty
  circles say it clearly enough; a line of text saying so would be nagging.
- Marks stay a **fixed size** regardless of week length or screen width, so the
  row never reflows into something that looks like a different chart.
- **Report rows carry no tone colour.** A session happened or it did not;
  colouring one green would imply the others fell short of something, and there
  is nothing here to fall short of.

## How it is built

- `src/diet/workouts.ts` — the week maths, mirroring `src/work/tasks.ts`
- `src/components/ChainStrip.tsx` — the seven marks, nothing else
- `HeroCard` positions it absolutely into the glyph band — `left: 14`,
  `bottom: 14`, which centres it on the glyph (`bottom: 9`, height `26`)
- The Diet **report** gets a `Workout` tab listing the sessions — kind, date,
  duration

The circle-with-a-letter-inside is not a new invention — `ProjectChart` already
uses exactly that mark for its `A · S · C` project badges. Reusing it means the
app has one idea of what "a small labelled token" looks like.

## Height budget

The Diet card is the joint-tallest in the deck, and deck height is set by its
tallest card, so anything added here costs every card.

| Attempt | Cost | Deck at 375px |
| --- | --- | --- |
| Own row, hairline, full margin | +38px | 231 → 269 |
| Own row, margin de-duplicated | +28px | 231 → 260 |
| **In the glyph band, out of flow** | **0px** | **231** |

The first two both made Diet the tallest card, which sets the height of the whole
deck — so the cost landed on Paisa and Kaam too, for a series neither of them
has.

The fix was noticing that every card already reserves 40px along its bottom for
the mode glyph, and the glyph only occupies the right-hand end of it. Putting the
strip at the left of that same band, absolutely positioned, gives it a home that
was already paid for. Diet's content height is now identical to Paisa's, and the
deck is back to exactly what it measured before this feature existed.

The single-line mark-with-letter-inside is what makes that possible: at 16px the
strip fits the band's height. A mark above a separate label row would have been
~40px and needed its own row regardless.

## Testing

- A day with a logged workout renders filled; without, hollow
- Today carries its ring; days after today are faint, not hollow
- Two workouts on one day render one filled mark
- An empty week renders seven hollow marks and no text
- Logging a workout updates the strip and the report without a reload
- Strip does not reflow at 375px; marks keep their size
- Strip never reaches the mode glyph — at 375px there are 124px between them
- Deck height at 375px is unchanged from before the feature
- Tapping the strip opens the Diet report, and does not do anything else

## Definition of done

1. Strip renders on the Diet card, Monday to Sunday, correct weekday letters
   derived from the date rather than stored.
2. All four mark states are visually distinct — trained, skipped, future, today.
3. Deck height at 375px is **unchanged** — the strip is out of flow, in the band
   already reserved for the mode glyph.
4. Diet report has a Workout tab listing sessions with kind, date and duration.
5. No red anywhere in the feature, and no copy that counts a streak.
6. Every colour and size resolves through `theme.ts`.
7. Typecheck, build, and a cold-load console all clean.

## Decided against

| Option | Why not |
| --- | --- |
| A fourth ring | Wrong shape for a binary fact; would shrink the three rings that do belong together |
| Its own mode | Three modes is settled. Workout is not a fourth life area, it is part of health |
| Behind the `More` menu | A chain you cannot see is not a chain. Visibility is the entire mechanism |
| A hairline above the strip | It read as a divider between the card and its own footer, and no other card has one there. Alignment with the glyph does the separating |
| Its own row under the rings | Made Diet the tallest card, so every other card paid for it. The glyph band was free |
| Red for skipped days | Punishment. People stop opening apps that tell them off |
| A weekly target | Turns rest days into failures, and drags in rest-day config for a question nobody asked |
| Rolling 7 days ending today | Scrambles the weekday letters, which defeats using letters at all |
| A visible count next to the marks | Seven marks already say how many. The number was restating the row it sat in |
| A **stroked** dumbbell icon | At 16px it collapses to three thin lines that read as a capital **H** — beside `M T W T F S S` that is an eighth day letter. Filled plates cannot be mistaken for one |
| Intensity or volume on the card | That is a coach's metric. The card answers "did I turn up" |
| A long chain in the report | Thirty marks at a readable size is ~570px — it would either wrap into a grid that reads as a different chart, or shrink until the letters stop being letters. The card owns the chain; the report owns the list |

## Open

- Should a workout at a saved gym link to that **Place**, the way a transaction
  will? The edge is cheap and it would answer *"gym jaana kam ho gaya"* — but it
  needs places to be captured first.
- Does Health Connect expose enough to detect a session passively? Steps already
  come from there. If it does, the same `estimated` / `confirmed` pair that sleep
  uses would apply here, and the strip would fill itself.
