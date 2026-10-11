# Onboarding — one screen before, a checklist after

> **Superseded 2026-10-11** by `spec/done/onboarding-goals.md`. The door
> replay, the first-minute greeting and the Getting started card are gone;
> `users.onboarding_done_at` carries over, now set when the first run ends.
> What follows is why the old version was built as it was.

> Status: **shipped — built 2026-09 on the web, the server and the phone; finished
> 2026-10-10** — the sixth step (what you pay every month), a thank-you that
> counts nothing, and `backend/tests/test_onboarding.py`.
> Surface: frontend · android · backend (one column on `users`, one block on
> `/deck`). The door is the sign-in screen: `spec/in-progress/sign-in.md`.

## The problem

A new user opens the app to an empty ledger. The greeting reads *"Good
morning, "* with a trailing comma, the numbers draw against nothing, and the
composer waits for a sentence the user has no reason to know how to say. The
premise — say a thing and it is logged — is invisible until the first thing is
said, and nothing in the app gets a stranger to that first sentence.

The instinct is a four-slide carousel. That is the wrong shape here: the app
has one screen and one composer, so there is nothing to tour, and every slide
is a claim about the product that has to be maintained by hand.

## What it does

Three moments. As little as possible before the first sentence, and the rest
after it, one step at a time, until there is nothing left to suggest.

### 1 · The door (before sign-in — one screen, no carousel)

The sign-in screen is the pitch. Top to bottom:

- The mark and the wordmark, `spica`.
- One line: **"Money, food, work. One conversation."**
- The app demonstrating itself: a **replay** of three beats, each a sentence
  said, the agent's line, and the card it produced. It loops, and can be
  swiped:
  1. *"Rapido home, one sixty"* → a money card, ₹160, *Transport* with the
     amber dot.
  2. *"Lunch — 2 roti, dal, salad"* → a diet card, protein and calories, the
     calories estimated.
  3. *"What should I do tomorrow"* → a To-do card, the overdue task first.
- **Continue with Google.** Nothing else on the screen. No skip, no "learn
  more".

The replay is drawn with **the app's own parts** — the user's bubble, the
card's shell and heading, the agent's serif, the estimate dot — over three
fixed script beats. It cannot drift from the product's look, because the look
is the product's; its rows are script, written nowhere and nobody's ledger.
Not a video: a video is a stored picture of the UI, and starts lying the week
a card changes. (A screen recording is still the right thing for the Play
listing, which is marketing and a different job.)

### 2 · The first minute (after the first sign-in — no form)

Nothing is asked. The thread opens with a greeting written for an empty
ledger, in the agent's voice, two sentences:

> Hi Sonu. I'm Spica — I keep your money, food and work in one place.
> Nothing here yet. Tell me one thing you spent today, or what you ate.

Three chips under it: **Chai 20** · **Lunch — 2 roti dal** · **Add a task**.
A tap **sends** the sentence — it does not merely fill the composer. One tap,
one real card, in the user's own ledger. The sent text stays in the thread as
the user's own bubble, so the example is still there to read, with its answer
under it.

Empty numbers say so in words — *No spends yet this month*, *Nothing eaten yet
today*, *No tasks* — never `0 / 0`.

### 3 · Getting started (a card until it is done)

A card under the greeting at the head of the thread: **Getting started**, how
many of how many, and a bar. Six steps, in the order they matter:

| step id | the line | done when | a tap does |
|---|---|---|---|
| `payment` | Log a payment | any `transactions` row | fills the composer: *"I spent "* |
| `meal` | Log a meal | any `meal_logs` row | fills the composer: *"I ate "* |
| `savings_target` | Set a savings target | `savings_target_paise` set | opens the goal editor |
| `diet_target` | Set protein and calorie targets | `protein_g_target` or `kcal_target` set | opens the targets editor |
| `commitment` | Add what you pay every month | any `commitments` row | opens the commitment sheet, empty |
| `task` | Add a task | any `tasks` row | fills the composer: *"Remind me to "* |

**Every step stays on the card, in order.** A done one is ticked and struck
through, so progress is something you can see rather than a number; the next
undone step is the only filled button (*Do it*). The commitment step is there
because the day's limit is only honest once rent and EMIs are known
(`spec/done/commitments.md`).

When the last step turns done, the card is replaced by one line in the agent's
voice — *"That is everything. I will stay out of the way now."* — once, and the
card never returns. It names no count: the number of steps changes with the
product. **Hide** on the card does the same without the thank-you; hidden is
done, there is no "later".

**The agent does not nudge** about these steps in the conversation. The card
lists them; a sentence after a write saying the same thing would be a second
voice for one job (parked, `spec/notes.md` § *Onboarding nudges in the chat*).

## Data

**Per-step state is not stored. It is derived.** Each step is an `EXISTS` on
rows the app already reads, or a null check on `users`. A stored "done" would
lie the day the row that made it true is deleted; a derived one cannot. Rows
count only while not deleted.

**One column is stored**: `users.onboarding_done_at` (timestamptz, null) — the
one fact no row can derive, *the person is finished with this*. **The client
sets it**, with `PATCH /users/me { onboarding_done_at }`, at the two moments
the client owns: the last step turning done (the thank-you) and *Hide*. Once
set it stays set, and `/deck` then sends `done_at` and no steps.

`/deck` carries one block, computed on the server so the web and the phone
agree:

```json
"onboarding": {
  "done_at": null,
  "steps": [
    { "id": "payment", "done": true },
    { "id": "meal", "done": false },
    ...
  ]
}
```

The words for each step live in the client, keyed by `id`. The server says
what is true; the client says it in words. A step id the client has no words
for is skipped, not printed raw — a newer server may know steps an older
build does not.

## Rules and edge cases

- **The door is the only thing before sign-in.** No screen precedes it, and it
  has no second page.
- **Nothing blocks.** The checklist is a card in the thread, never a modal;
  the composer is live from the first frame.
- **Greeting with no name.** The name comes from Google's `given_name`. If it
  is empty the greeting is *"Hi."* — no trailing comma, no placeholder.
- **Not a tour.** No coach marks, no arrows pointing at the composer.
- **A returning user never sees any of it.** `onboarding_done_at` set → no
  card, no thank-you, the greeting as on any other day.
- **Reduced motion.** The replay shows each beat still and advances on a timer.
- **The replay is not the user's data.** Its rows are script, never written,
  and carry the amber dot only where the real product would.
- **A deleted row undoes its step.** Delete the only payment and *Log a
  payment* is undone again on the next load — until the person is finished.
- **Steps grow with the product.** A new step is one `EXISTS` on the server and
  one line of words on each client. It appears for users whose
  `onboarding_done_at` is still null and for nobody else.

## Decided against

| Option | Why not |
|---|---|
| A three-to-four slide carousel with illustrations | Explains what the replay shows; every slide is a claim about the product that has to be maintained by hand. |
| A screen-recorded video on the door | A stored picture of the UI — it drifts the week a card changes. Kept for the store listing, where a re-record is routine. |
| Asking for targets up front | A savings target with no spends is a guess, and the first-run form is the screen most people abandon. Ask after the data exists, which the checklist does. |
| Storing a boolean per step | Lies when the row is deleted. Derive. |
| A modal tour with coach marks | Nothing to point at. |
| The agent introducing itself at length | Two sentences. It earns attention by logging the first row. |
| A separate name for the agent | The wordmark is *spica* and the mark is Spica's. A second name means two things to explain on the one screen there is. |
| Filling the composer instead of sending, for the first-minute chips | Teaches the grammar at the cost of the payoff. The sent bubble teaches it anyway. |
| "Remind me later" on the card | A third state to store and test for a card that already leaves the moment it is not needed. |
| A done step dropping off the card | The card shrinking is progress you have to remember; a struck-through step is progress you can see. |
| The agent nudging in the chat after a related write ("Want a protein target?") | The card already lists every step; "never twice for the same step" would need a stored record of what was said. Parked in `spec/notes.md`. |
| The server marking onboarding finished from `/deck` | The thank-you is a moment on the screen, so the client owns it; the server deciding it would have to send the finished steps once more just so the thank-you could show. |
| *"That is all five"* | A count in a sentence is stale the day a step is added. |

## The name

**Spica** — the product and the assistant share it, and the Constellation is
its mark. One name to say on the one screen there is. The one-name rule was
decided 2026-09-15, under the name *Cortex*; the name became Spica 2026-10-09
(`CLAUDE.md`).

It is held as a constant, not typed into components: `frontend/src/brand.ts`
exports the name, the wordmark, the tagline and the `localStorage` namespace,
and the door, the greeting and the Drawer read from there; `index.html`'s title
carries the literal. The namespace stays `cortex.` — renaming the keys would
sign every browser out.

## Definition of done

| Check | How |
|---|---|
| Each step is derived: false on a new account, true once its row or field exists, false again when that row is deleted | `test_onboarding.py` |
| The commitment step turns done with a commitment and back with its delete | `test_onboarding.py` |
| `onboarding_done_at` set by `PATCH /users/me` → `/deck` sends `done_at` and no steps, and it stays set | `test_onboarding.py` |
| The card shows six lines on both surfaces, the commitment one opening the empty sheet | the web in the preview pane; the phone on the emulator |
| The thank-you names no count | read on both surfaces |
