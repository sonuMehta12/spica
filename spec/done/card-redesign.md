# The cards, redesigned

> Status: shipped 2026-10-06 on the web and Android — settled 2026-10-01, revised 2026-10-02 after the card test run
> Surface: frontend · android, and since the test run backend: the cards, the tool descriptions, two restore routes
> Design: the "Cortex chat widgets" canvas in the artifact gallery — every widget
> with its real payload, today's render and the proposal, one artboard each.

## The problem

The cards in the thread were generated, not designed. Every write came back as
the same form — a lede, then Amount / Category / What / Day — so a ₹20 chai
said "Chai ₹20" three times: in the reply, in the lede, in the fields. The one
thing that needed the person (a guessed category) was hidden behind ⋮. Money in
looked exactly like money spent. Every expense was red. Agent sentences sat
inside cards, so the thread mixed prose and data in the same box. A habit
logged "2 smokes" showed "Ticked"; a meal with gaps was a form plus two grey
sentences to decode.

## What it does

### The rule everything follows

**Text first, the card below — never a sentence inside a card.** The agent's
words stand on their own above the card, in the serif; the card holds only
data. A card note worked out on the phone (the old "Sabse bada…", "92 g to
go", "Start with ACM-223") is no longer drawn inside the card:

- Under a **server card** (a table) it is dropped — the agent's reply above it
  is the commentary, and two sentences would say the same thing.
- On a **phone-built card** (+ menu: Cash flow, To-do, Pantry), where no reply
  exists, it is drawn above the card as the agent's line — still computed from
  the live rows every time it is drawn, never stored.

### The pieces

- **The receipt line** — a confirm card is one line: a mode coin, what
  happened, its meta (category or slot · day), the figure on the right.
- **Asks in place** — a guessed value carries the amber dot and asks on the
  card: "Food, I guessed · Right · Change". Right confirms the row; Change
  starts the edit. Nothing a person must answer sits behind ⋮.
- **Change attaches to the composer** — like a quoted message: a small chip
  above the input ("Auto · category ✕"), the input left empty for the user's
  own words, and the sentence sent is the chip's context plus what they typed
  ("Change the category of the ₹80 Auto payment on 1 Oct to transport"). It
  never pre-fills the composer — on a phone a pre-filled correction covered
  everything the user meant to write — and it never jumps to another page.
- **Quiet actions** — text buttons under the line (Undo, Fixed cost?, Forget).
  Undo deletes a row just written. Rare actions stay behind ⋮ where a ⋮ is
  drawn.
- **Figures in ink.** Red means over, late or negative — never "spent".
- **Read the live row.** A card reads the row it points at, so a change
  anywhere shows on it, and a deleted row shows "Removed", struck and faint.

### Card by card

| Card | Proposed |
|---|---|
| Payment (paisa · written) | Receipt: ₹ coin · what · "category · day" · amount. Guessed category asks in place. Undo · Fixed cost? (· Repeats? when fixed). |
| Money in | Same receipt, read from the live row: "Came in · day", **+₹** in Paisa ink, and "This month: ₹X in · ₹Y out" from the month's rows. |
| Udhaar (lent) | "Lent · comes back · day", the amount, and what is still out on that loan from the pending list. Never asks a category: a lending, a borrowing and a repayment are filed as Udhaar by their kind. |
| Payment proposed (nightly review) | A question: the payee and amount, "Category?" with the dot, the reasons as small facts (the guess's *why*, split), and two answers: *Yes, category* · *Change*. Proposals in one turn stack into one card, "1 of N", with *Skip*. No "80% sure" — the model's confidence is not a measured number. |
| Payment / meal deleted | The line, struck and faint, "Removed", and *Undo* — the restore route brings the row back exactly as it was, and every card showing it is live again. |
| Meal | Receipt: bowl coin · dish · "slot · today" · protein, with kcal, carbs and fat under it when known (dotted when estimated). Then a thin bar: protein today against the target, from the live meals; with no target, "no target · *Set target*". Macros unknown: "macros unknown" and *Add weight*. Unrecognised and unweighed items are their own lines — "Salad — how much? · not counted", "Achaar — not found · not counted" — and an assumption is its own dotted line. |
| Day facts (sleep, weight) | Two tiles: sleep against the sleep target; weight against the previous weigh-in, or "no earlier weigh-in" — never an invented change. |
| Habit ticked | The habit's coin, its name, **today's count** from the live habit log (not "Ticked"), and the week as seven marks. |
| Habit started / stopped | "Tracking · to build" or "to cut down", and the empty week. Stopped: struck, "Stopped". |
| Exercise done | Receipt: barbell coin · name · "Done today" · "N× in all". |
| Pantry move | Receipt: package coin · food · "+200 g bought · today" · the level now. Undo. |
| Dish saved | The dish as suggestions show it — protein, minutes, kcal — with a pin: "Saved". |
| Task (any state) | The task itself: a checkbox (live — tap ticks it), the title, chips for due and project (project dotted when guessed). Done: struck. A Linear task ticked here but not moved there gets its own line and *Move it ↗*. Just added: *Undo*. The same task said again, in any wording: "Already on your list", and no second task. |
| Task question | "mere saare tasks dikhao": the live To-do card under the reply, which says only what matters — never the list again in prose. |
| Project | The project's mark and name, "New project · N tasks". |
| Person | Initial, name, relation as a chip. |
| Place | Pin coin · name · "kind · N visits" · spent. |
| Memory | "I'll remember", the kind as a chip, the fact, and *Forget*. |
| Profile target | The target and its value; *Change* attaches the target to the composer ("Change my savings target to …"). |
| Payments table | The total spent leads as a figure ("₹345 · spent · 3 payments"); rows keep the old anatomy — date · name with category under it · amount · ⋮ — amounts in ink, money in as +, a loan's row saying Lent, Borrowed or Repaid. A deleted row is struck and faint and left out of the total. No day headings. No note. |
| Diet table | Protein against the target leads, with a bar; rows: date · dish with "slot · kcal" under it · protein · ⋮. A deleted meal is struck and left out. An empty log shows "nothing recorded" and its edit. No note. |
| Dish suggestions | Rows: coin or photo · name · "slot · minutes · kcal" · protein as the figure; the *why* as small facts; **Log it** as a real button; Save and Not this as quiet actions. Logged: "✓ Logged". |
| Exercise suggestions | Rows: barbell coin · name · "muscle · minutes · equipment" · "N× done" or "new" · **Done**. |
| Ask | The question above the card as the agent's text; the options as full-width rows inside it. The held-up row, struck, over them. (The server never sends this card yet; both apps can draw it.) |
| To-do (+ menu) | The note above. Card: "14 open · 2 late"; rows grouped Late · Today · This week (to Sunday) · Later; each row a checkbox, the title, the project as a chip, and its small print — how late, the day, P1, where it came from. A task ticked today stays in its group, struck, so the list never jumps under a tap. |
| Pantry (+ menu) | The note above. Card: "11 in the kitchen"; grouped Use soon (past its shelf life, oldest first, with how long it has sat) · Running low (low or out) · Stocked (folded). |
| Recipes (+ menu) | The note above. Card: "4 dishes · 1 eaten"; each dish as suggestions draw it — coin, name, "slot · minutes · kcal", protein, and N× · saved · new. |
| Cash flow (+ menu) | The note above. Card: what is left at month end leads — the server's `pool − locked`, the figure the Paisa card and the agent read; one bar, what goes out against what came in, red only when more goes out than came in; then Came in · Gone out · Still to go, and money lent out — listed, never counted. |
| Getting started | All five steps in order, ticked ones kept and ticked, the next one the only filled button, a progress bar, *Hide*. |
| A failed send | Your own message is marked "Not sent · Retry" — no agent bubble saying the server was unreachable. |

## Rules and edge cases

- A card whose row is outside the loaded window still asks for it by id, as
  today; until it arrives the receipt draws from the payload.
- The live row wins over the payload for every value it carries (amount,
  description, category, confidence, direction).
- Quiet actions are text, not pills; the one filled button on a card is its
  primary action (Log it, Do it, Yes).
- Copy is English; data stays as said — a row called "Dost 2 ko diya" is never
  translated.
- A phone-built card with nothing in it draws only its line ("Nothing in the
  pantry is counted yet.") — never an empty box under a sentence. An empty
  table says so in its caption ("no payments yet") and draws no divider.
- A fact a card already shows as its figure is not repeated as a chip (a
  workout's "done 3×" is the figure, not also a reason) — nor by the line
  above it: a phone-built card's line never restates the figure the card leads
  with. It says what the card cannot, such as why lent money is missing from
  the month. When a figure is below zero, the line names the cause that is
  true: nothing has come in yet, more went out than came in, or the
  commitments are larger than what is left.
- A + menu message carries only an id, and which list: the card and its line
  are both read from the live rows each time they are drawn, so a meal that
  lands or a row deleted afterwards shows on a card already in the thread.
- Two hardcoded notes were found and replaced: the Diet table's soya-keema
  advice (dropped with all server-card notes) and the cash-flow note about
  "the friend's ₹4,000" (now worked out from the pending rows).
- The old cash flow called income minus debts "left at month end", so the
  month's spending never lowered it. It now uses the server's month figures,
  the same ones the Paisa card reads.

### What the server does for the cards

- **Reads made only to check do not become cards.** Every read that returns
  rows used to become a table, and the model reads rows before most writes —
  so a meal correction came back with a paisa table nobody asked for. In a
  turn that writes, only a table of the kind written is kept (the day's
  payments after a payment, which reads as a receipt); in a suggestion turn,
  no table; a turn that only read keeps what it read. One task list per turn.
- **A loan's category is its kind.** Lent, borrowed and repayment rows are
  filed as Udhaar whatever the model passes, so no card asks to confirm one.
- **A category the user names is confirmed.** A correction or a "haan" to the
  guess sets the row's confidence to 1, and the dot clears.
- **A new ledger has categories to choose from.** The model is shown the
  ledger's own categories and then a default set, so a first "auto 80" can be
  Transport. A ride said without a category is a Transport guess, still dotted;
  money going out is never filed as income.
- **The same task in other words is one task**, on the same day: the words
  that carry it, compared without the glue of either language.
- **Buying a food starts tracking it.** A purchase or a stock-take of a food
  the pantry does not hold adds it; waste or a correction of one is refused.
- **The tool descriptions steer follow-ups**: anything said about a meal just
  logged is `correct_meal` on that meal, never a second `log_meal`, and the
  dish keeps the words the user named it with.
- **`evals/n2n_eval.py`** says each case's sentence to the real model on a
  fresh database and checks the tool it ran, the card that came back and the
  row that landed — run by hand before a build, never inside `pytest`.

## Decided against

- **"Estimate it" on an unknown meal.** No route estimates a logged meal, and
  sending a sentence to the agent risks logging the meal twice.
- **Grouping a table by day.** With one payment a day a heading only repeated
  the row's own date and amount.
- **Itemising the commitments on Cash flow** ("Rent due", "EMI due"), as the
  canvas drew them. What is committed arrives from the server as one figure;
  until it says what that figure is made of, it is one line.

## Left open — parked in `spec/notes.md` § Cards no turn produces yet

None of these is a rendering gap: both apps draw every card above. What is
missing is the server or the prompt producing them.

- The reply repeating the card ("Chai ₹20 log ho gayi" above the receipt) is
  the prompt's to fix; the user is reworking the prompt separately.
- Whether a meal follow-up corrects the meal is still the model's choice; the
  tool descriptions steer it and `n2n_eval` checks it, but nothing forbids a
  second `log_meal`.
- The ask card is never sent.
- The morning brief (`morning_brief` schedule) is not built.
- The Linear sync turn carries only prose; a receipt needs its trace on the wire.
- A number answer ("kitna kharcha?") is prose; leading with the figure needs
  the prompt.
- The exercise receipt cannot say "last time N days ago": once a workout is
  logged, the client holds only today's date for it. The server would send the
  previous one.
- A weigh-in compares against `/weigh-ins` only. A weight said in chat is
  stored elsewhere, so "since <day>" can miss the latest one.

## Definition of done

- Every card above renders as specified in the web app and the Android app.
- No agent sentence is drawn inside any card in either app.
- A guessed value asks in place; confirming it clears the dot.
- Money in shows +₹ in Paisa ink; no expense is red.
- Checked by hand in both apps against real rows: a payment, a meal, a habit,
  a task, a table of each kind, the + menu cards, a failed send.
- `uv run python -m evals.n2n_eval` passes, its known gaps aside; the server's
  half is `tests/test_card_redesign.py`.
