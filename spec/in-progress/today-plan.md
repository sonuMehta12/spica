# Today's plan — meals and a workout on Home

> Status: in build (2026-10-08) — server and phone built; the server half waits on apply
> Surface: backend + android. The web keeps the deck.
> Builds on `spec/in-progress/meal-suggestion.md` (how the reasoning works) and
> closes the two suggestion jobs parked in `TODO.md`.

## The problem

Home says where the day stands — protein to go, calories, steps — but not what
to do about it. Asking means opening Chat and typing *"what can I eat"*, and the
answer today is thin: `suggest_dishes` only filters the dish library and the
pantry, so a short library gets one dish or nothing; `exercises` only filters
the exercise library, so a new account hears *"library mein nahi mila"*. And no
dish or exercise has a picture: 21 dishes and 41 exercises, no image on any.

## What it does

Two more widgets in the Add widget sheet, off by default like Activity:

| Widget | It shows |
|---|---|
| **Meals** | the rest of today, planned: one card per meal still to eat, each with a picture, the dish, the slot, kcal and protein · carbs · fat, and a line on why it fits. Together they close today's protein and calorie gap. *Log it* logs that dish as eaten, as the suggestion card's button does |
| **Workout** | today's suggestion: one workout — a run, a ride, a gym session — with a picture, the minutes, and its exercises or distance, and a line on why (rest days this week, what was done last). *Done* logs it |

### The plan is the rest of today

Whatever has been eaten stays; the plan covers the meals still ahead, sized to
what is left of the targets. It is worked out again when a meal is logged, so a
bigger lunch shrinks dinner. Before anything is logged it is the whole day; at
night, with no meal left to plan, the widget says the day is done and shows
what it came to.

### Ideas, beyond the library

The library comes first: a dish you have eaten and liked beats a stranger. When
the library cannot close the gap — too few dishes, the wrong slot, nothing
cookable from the pantry — the model adds **ideas** of its own: North Indian
home cooking, in the rules of the engine spec. An idea is marked as one, and its
macros carry the amber dot: they are estimates. *Save* puts an idea in the
library; after that it is a dish like any other.

The same holds for a workout: the exercise library and what was done this week
first; with too little history, a sensible start — a muscle group and the
minutes are enough — marked as an idea.

### Pictures from the web, licensed

A dish or exercise without a picture gets one, found once and stored on its
row: a photo from **Wikimedia Commons** under a free licence, the best match for
the name. The card shows the photographer's credit in small type. No match, no
picture — the card draws its coin, as now. An idea gets its picture the same
way, kept with it if it is saved.

Commons over a general image search: its photos may be shown with credit; a
search result is someone's photo with no permission to use it.

**A picture must share a word with the name.** Commons ranks loosely — the
first result for *chicken curry with rice and roti* was a photo of peas, and
*whey shake* came back as a generic food chart. So the photo whose file name
shares the most words with the dish wins, and one sharing none is no match: the
card keeps its coin rather than showing the wrong food.

## Data

| What | Where |
|---|---|
| `GET /plan/today?local_day=` | new. Meals and the workout for the rest of the day. Computed by one model call with the engine spec's state — today's log, the targets, the last seven days, the pantry, the dish library's candidates (`suggest_dishes`' query) and the exercise library's — and cached per user and day until a meal or a workout is logged |
| `dishes.image_url`, `exercises.image_url` | exist, empty today; filled by the lookup |
| `dishes.image_credit`, `exercises.image_credit` | new, text, nullable: *"Photo: Jane Doe, CC BY-SA 4.0"* |
| An idea | not a row until saved: it travels in the plan with `idea: true`, a name, a slot, estimated macros and its picture |
| Logging from the plan | the existing tap-to-log path (`POST /chat/act`), so the row and the receipt are what the suggestion card makes |

The plan is not a stored sentence about the user: it is regenerated from the
rows, and the cache dies with any write it was built on.

## Rules and edge cases

- **Closing the gap is the point.** The meals' protein and kcal, added to what
  is logged, land on the targets within a band; the widget shows the sum so the
  claim can be checked.
- **No targets, no gap.** Without a protein or calorie target the plan suggests
  ordinary meals and says the targets are what would size them — with *Set
  target*, as Diet does.
- **Estimates are marked.** Library dishes carry their stored macros; ideas
  carry the dot.
- **Every meal is one a person eats**: at most 800 kcal or 50 g protein, a snack
  350 kcal. When the slots left cannot close the gap, the day falls short rather
  than one dinner carrying it — the first real run planned a 1,790 kcal dinner
  at 6:30 pm with nothing logged. Nothing logged by evening usually means meals
  went unlogged, not uneaten. `n2n_eval` holds the plan to the targets only when
  the slots left can reach them.
- **One model call per change, not per open.** Opening Home reads the cache.
- **A picture is optional.** A failed lookup is not retried on every open.
- **Health Connect stays on the phone.** The server does not see runs and rides,
  so the workout plan reads what Spica holds — habit logs and exercises — and
  the phone may add *"you ran 5 km yesterday"* from Health Connect to the line
  it shows, never sending it.

## Decided against

| Option | Why not |
|---|---|
| A general image search | Photos we have no right to show |
| AI-made pictures | Chosen against by the user: a real photo of the dish reads better |
| Planning the whole day each morning, fixed | It goes stale at the first meal that differs. The rest of today stays true |
| Library only | Sparse until the library is large — the reason both TODO items exist |
| A plan computed on the phone | The engine needs the last seven days, the pantry and the libraries, which live on the server, and the model call belongs to the agent |

## Definition of done

1. `GET /plan/today` returns meals whose macros plus today's log land within
   the band of the targets, on an account with targets, a pantry and a week of
   history — `backend/tests/test_today_plan.py`.
2. A meal log or a workout invalidates the cache; an open without a write makes
   no model call.
3. An empty library and empty pantry still get a plan, every item marked an idea.
4. Pictures: a dish with a Commons match gets `image_url` and `image_credit`; no
   match leaves both null and is not retried on every open.
5. `n2n_eval` gains the plan cases.
6. On the phone: Meals and Workout in the Add widget sheet; *Log it*, *Save* and
   *Done* write through the existing paths, and the receipt lands in Chat.

## Open

- **Meal suggestion needs a proper design, not a patch** — library-only
  suggestions are wrong. Recorded, with what was seen and what to decide, in
  `spec/in-progress/meal-suggestion.md`.
- **Servings for a library dish.** Found by the chat eval's plan checks,
  2026-10-10 (`spec/done/chat-quality.md` § Where it landed): the
  morning plan for an empty day fell short of 2000 kcal in six rounds of
  seven — 1,340 to 1,800 — at either effort. Every time it chose library
  dishes at one serving (egg bhurji 280, whey 120, soya keema 360), and a
  library dish keeps the library's numbers, so with a small library the plan
  *cannot* reach the target whatever the model decides. A `servings` on a
  planned library dish, scaling its numbers, would let it; until then the
  check fails on any account with a small library.
- Whether a planned workout should also suggest a walk on a low-steps day, once
  the phone shares steps with the plan.
