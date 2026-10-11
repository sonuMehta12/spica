# Chat quality — fewer made-up answers, the right card

> Status: **shipped 2026-10-10** (commit `2f23372`). The eval, the rounds of
> fixes and the effort decision; 96.3% of cases and 98.7% of turns on Luna at
> medium, without glue. Results under *Where it landed*; what was left for
> later is in `spec/notes.md` § *Chat quality — what the 95% left*.
> Surface: backend — the prompt (`app/agent/prompt.py`), the tool
> descriptions (`app/agent/tools.py`), card choice (`app/agent/cards.py`),
> and the eval (`backend/evals/`)

## The problem

The agent's replies have been unreliable: it **states things the rows do not
say**, it **does things nobody asked for**, and it **returns the wrong card, or
a card nobody needed**. For an app whose premise is *agent hi app hai*, this is
the core failure — a ledger with a voice is only worth anything if the voice is
true.

## What "wrong" means here, measurably

A reply fails when it does any of these:

- **A number nobody read.** A figure in the reply that is in no tool result,
  not in the turn's context and not in the person's own words.
- **A claim the trace contradicts.** *"Log kar diya"* with no write, *"dobara
  log nahi kiya"* with a write.
- **A name or item that is not there.** A dish, payee, task or project the rows
  do not contain.
- **A write nobody asked for.** Anything written on a question, a greeting or
  a thanks.
- **The wrong tool for the question** — a task question answered from money.
- **Markup instead of a card** — a code block, JSON, a made-up widget.

And a card fails when it is **missing** (a write with no card), **wrong** (a
card of another kind or about another row), or **unneeded** (any card the
case did not expect).

## Found in the real thread, 2026-10-01 to 10-09

Read from the last nine days of the dev thread, turn by turn. Each is a case.

| Pattern | Seen |
|---|---|
| **Writes nobody asked for** | *"Thanks"* logged a second ₹260, and the reply said it had not; *"thanks"* ticked Workout; *"or kon si tracked ho rahi hai"* ticked Cigarette; *"meditation band karo"* logged two cigarettes again; *"aj log kar do"* after adding one habit ticked two |
| **Unneeded cards** | Every correction's lookup showed the day's payments as a table; *"Show all remember"* brought fourteen money cards; *"Acha"*, *"ji"* and *"hi"* read the task list |
| **Numbers from nowhere** | Protein left 122 g at 07:22, 63 g at 07:37, nothing logged between; a greeting's 14 open tasks against work_report's 11 |
| **A correction that duplicates** | *"90k sorry"* logged a second salary instead of fixing ₹90; a meal's clarification logged lunch again |
| **Unknown written as zero** | A dish saved with 0 kcal and 0 g protein |
| **A category no one would pick** | A cigarette filed as food, then Health/Diet |
| **Markup instead of a card** | *"Show with ui"* got a hand-written ` ```ui ` JSON block |
| **Out of scope, answered from data** | *"Trip plan for this weekend"* answered with the gym task, said to be due |

## What a right reply is — decided 2026-10-09

| Situation | What comes back |
|---|---|
| **A correction** — *"chai 25 ki thi"* | The corrected receipt, and nothing else. No table of the day's payments under it |
| **A turn that asks for nothing** — *"thanks"*, *"acha"*, *"theek hai"* | A short reply. No tool, no card, no write |
| **A new task** — *"kal gym renew karna hai, task bana do"* | That task's card. Not the To-do list |
| **A card nobody asked for** | Counts as a failure in the eval. Each case lists exactly the cards it wants |

The rule under all four: **one card for each thing that changed, or for the
list that was asked for — never for what the agent read to find its way.** A
lookup the agent makes before a write is its own business.

This changes one earlier decision: `cards.curate` keeps a table of the day's
payments under a payment's correction, because it "reads as a receipt"
(its docstring in `app/agent/cards.py`). That goes.

## Decided in review, case by case

From going through the baseline's failures one at a time (2026-10-09):

- **A missing value is asked for, never filled.** *"grocery pe kharcha kiya"*
  with no amount is a question back — not a `log_payment` with ₹0 that the
  server happens to refuse. The same habit wrote a dish with 0 kcal.
- **A correction changes the row it corrects.** *"90k sorry"*, *"chai 25 ki
  thi"*, *"dal ek katori thi"* change the entry just made; when it is unclear
  whether a sentence corrects or adds, the agent asks first.
- **Your tracked habits are shown to the agent every turn**, like the day's
  numbers. Asked *"kaun si habits track ho rahi hain?"* it reached for
  `log_day` — a write — to find out.
- **Nothing a turn did not ask for is written** — no payment on a thanks, no
  memory on a question about memory, no exercise on a question about
  exercise. The one exception is the next rule.
- **One sentence, two facts: judgement, not a rule.** A sentence can carry a
  second fact it never states: *"spent 25 on cigarette"* is a payment and,
  at ₹20–25 a stick, one cigarette smoked. The agent writes what was said,
  and for the second fact decides like a person would:
  - **plainly implied** — the price of one cigarette, a habit they track — it
    writes it too, marked with the dot as inferred, and says so;
  - **unclear** — *"cigarette ka packet liya, 350"* — it writes the payment
    only and asks the one question that settles the rest: *"aaj kitni pi?"*
  The line between the two is the agent's judgement, informed by the
  person's own history (what a cigarette usually costs them), and the eval
  holds it to cases on both sides of the line, three runs each — a judgement
  that changes run to run is not judgement.
- **Food is asked about, not inferred.** *"Swiggy se biryani 350"* logs the
  ₹350, then asks *"biryani khayi? log kar dun?"* before any meal is written —
  ordering food very likely means eating it, but a meal brings estimated
  macros with it, and the person confirms that.
- **Intent, not a word.** *"200g paneer laya"* is a purchase — the pantry, never
  a meal. *"aaj workout kiya"* ticks the Workout habit. *"yaad rakhna: …"* is a
  memory — never a habit or an exercise, whatever the sentence mentions. A
  second *"chai 20"* in a day is a second chai unless it says it corrects (*ki
  thi*, *sorry*, *nahi*). A search that finds nothing because of its own filter
  is not "not in the library".
- **A list the card shows is not typed again.** *"mere saare tasks dikhao"* is a
  short summary — the counts, what is late or due today — and the To-do card
  under it. The card must be there; the sentence never repeats its rows.
- **Outside the three modes: short, plain, no data.** Spica is goal-oriented —
  *"less managing life, more achieving it"*: it turns goals in saving, fitness
  and time into everyday actions — and is not a general-purpose assistant. *"Is weekend ka trip plan suggest karo"* gets a
  short suggestion from general knowledge, in plain text: no tool, no card,
  nothing from the ledger dressed up as a plan. Whether travel ever becomes
  something Spica manages is not decided.
- **Which projects** is answered in the sentence. No card: the To-do list is
  tasks, not projects.

## Decided after the loop — 2026-10-10

- **A follow-up that could correct or add is asked about, not guessed.** "90k
  sorry" after "90 salary" — when the agent cannot tell whether a sentence
  changes the row just logged or adds a new one, it asks in one line: *"₹90
  wali entry ko ₹90,000 karun, ya nayi salary?"* A wrong guess writes a wrong
  row; a question costs one tap.
- **No glue.** A fix that guesses intent from the person's words — a keyword
  list, a regex over the sentence — is not how a failing case is closed. The
  correction guard (`_CORRECTS`) and the table word list (`_ASKS_TO_SEE`) added
  at the end of the loop were such fixes; both are gone, replaced by the two
  decisions on either side of this one. A guard that holds a true invariant of
  the data — an amount above zero, a schema field its handler accepts — is not
  glue.
- **Whether a read shows as a card is the agent's call, made explicitly.**
  Reading rows to find one number ("Blue Tokai pe kitna kharcha hua?") must not
  put a table under the reply; asking to see them ("is hafte ki payments
  dikhao") must. The agent says which, with `show` on `paisa_report`,
  `diet_report` and `work_report` and the guidance in each description — not a
  server word list over the sentence. A card is built only when `show` is
  true; the result's `card` note tells the model whether one will appear, so
  the reply never points at a card that is not there.
- **Judgement that varies run to run is accepted at today's rate** — a packet
  ticked as a cigarette, or a write on a question, about one run in three on a
  few cases. Not chased with rules.

## Already fixed, and the pattern they share

Found while building work sync and projects (`spec/done/projects.md`):

| Failure | Fix |
|---|---|
| *"Aaj kya due hai?"* answered from `paisa_report` | A `work_report` tool, and a `[work]` line in every turn's context |
| A reply arriving as one sentence written twice | The final answer only, said once (`runner.final_text`) |
| A *yes* that asked the same question again | The refusal names the next step for each answer |
| A guessed project left unmarked | Whether it was named is read from the person's words |

**Each was fixed by giving the model a fact or a field, not a sterner
sentence.** That is the order to reach for again: a field whose name is the
question, a fact in the turn's context, a tool that returns what the sentence
needs, a server-side guard — and prompt prose last.

## The harness

`uv run python -m evals.n2n_eval`.

### Decided, 2026-10-09

- **One conversation, in order** — like the eval before it. The cases are
  said one after another on one account, so later turns act on what earlier
  ones wrote (*chai 20*, then *chai 25 ki thi*), the way the app is really
  used, and a long thread is part of what is tested. A failure early can make
  a later case fail too; the report shows the first failure, not only the
  last.
- **Checks only — no judge model.** What is graded is what can be checked
  without reading the sentence for meaning:
  - **tools** — what must run, what must not, or *no writes at all*;
  - **cards** — the exact set. Any other card is an unneeded card;
  - **rows** — what the database holds afterwards;
  - **the reply, mechanically** — a figure that must appear, computed from the
    rows; words it must or must not contain; no code block or JSON.
- **Claude is the judge, not a model in the code.** After every run, Claude —
  in the working session — reads each reply beside the tool results the run
  captured, and fails any reply that claims what the data does not say or what
  the tools did not do. The code checks run first; Claude's reading comes on
  top. Nothing is graded by a model the eval itself calls.
- **Each run three times.** A case passes only when it passes in all three; one
  that passes once or twice is flaky, and counts as failing.
- **Run before every prompt or tool change lands.** A case that passed before
  the change and fails after it blocks the change.

### Built with it, for review

- **A lived-in week of data** the conversation starts from — payments, meals,
  habits, tasks in three projects, a pantry, a lending, memories — so the
  questions have something true to be answered from.
- **The review page** — the Card test run artifact's Eval view: every case
  with its expectation, the reply, the tools with their results, the cards and
  why it failed, and a mark per case: the verdict is right, the verdict is
  wrong, or the case expects the wrong thing.
- **Effort and model as flags** — `--effort medium` runs the same day at
  another effort; `--model` exists but the agent stays Luna (*The fix
  order*, 6). `N2N_DB` names a second database, so two runs go side by side.
- Tool results are captured inside the eval only; `messages.tool_trace` keeps
  arguments, not results, and stays that way.

## Where it landed — 2026-10-10

The same day of 79 cases, said three times per round, plus Home's two plan
checks. A case passes only when it passes in all three; *turns* counts each of
the three separately. Code checks, then Claude reading every reply against the
tool results (`evals/judge_aid.py`).

| Round | What changed | Cases, all 3 runs | Turns |
|---|---|---|---|
| Baseline | — (the first harness, one account per case) | 63.2% | 71.5% |
| 1 | Cards only for what changed; ids of written rows; habits every turn; money in rupees, debts by who owes; empty writes refused; every tool description; the prompt's rules | 82.7% | 89.1% |
| 2 | Ids moved off the replies (the model copied them); usual price beside each habit; one table per kind; a failed commit no longer ends the turn; a miscopied id finds its row; a category learned from the ledger | 91.4% | 95.8% |
| 3 | A repayment finds its one open loan; `by_category` in rupees; a habit is not an exercise; never claim an undone write | 92.6% | 96.7% |
| 4 | Effort **medium** (and the paneer rule, a 90 s call timeout) | 92.6% | 96.2% |
| 5, none | A statement is the ask; `keep_dish` acts; a result says whether a card will show it | 93.8% | 97.5% |
| 5, medium | the same code, side by side | 95.1% | 97.9% |
| Confirmation, medium | A result's card note says *name the one to three that answer*; a prompt the provider refuses becomes a reply | 97.5% | 99.2% |
| Final, medium | A table only when the sentence asks to see a list | 98.8% | 99.6% |
| No glue, medium | The correction guard and the table word list removed; `show` on the three reports; ask when a follow-up could correct or add | 96.3% | 97.1% |
| **No glue, fixed** | `work_report`'s handler takes `show` — the schema offered it, the signature did not, so every task list came back as a TypeError | **96.3%** | **98.7%** |

The last row is where it stands. The glue bought about two points of cases;
what remains of them is three cases failing once in three runs each, none
twice — the variance accepted above, not a pattern.

Without Home's plan checks — a separate feature, not chat — the confirmation
round is **98.7% of cases and 99.6% of turns**: the 95% held on a second
measured round rather than one lucky one. **Medium is now the agent's effort**
(`app/config.py`): 4.7 s a turn at the median and 11.9 s at p90, against 4.4 s
and 9.2 s at none, for about ₹0.0015 more a turn.

What still fails, and why it is left (the last round):

- **"90k sorry"** logged a second salary once in three, neither correcting
  the ₹90 row nor asking. It is the one remaining failure that writes a wrong
  row, so it is the first to watch in real use. A server check that guesses a
  correction from the amount or the timing would be glue; if it recurs, the
  lever is what the model reads — the `[rows written …]` line and the ask
  rule — or effort high on Luna.
- **"16k ki shopping — RO, pressure cooker…"** filed under *Ghar* once in
  three. RO and a pressure cooker are household goods, so the case may expect
  too narrowly; it is the person's to mark on the review page.
- **"Is mahine kitna kharcha hua?"** answered once from a figure read earlier
  in the conversation, without reading again. The figure was right; a figure
  carried forward goes stale the moment a payment lands.
- **A miscopied row** — once in six runs, two rounds before the last, a
  correction took the chai's id for the Amazon payment's. Not seen since; a
  shorter handle for recent rows is the step if it recurs.
- **Home's morning plan** passed in the last round and missed in the one
  before. It is not chat: it belongs to `spec/in-progress/meal-suggestion.md`,
  which owns what to suggest and from where.
- Fixed in the confirmation round and measured there: a prompt OpenAI refuses
  as a policy risk (a false positive on "last 3 payments dikhao") is now a
  reply asking to say it another way, not a failed request; and "aaj kya due
  hai?" names the task instead of only counting it.

The experiment's model spend: about 27 M Luna input and 0.2 M output tokens
over every run, and 0.5 M Sol tokens for the judge model before it was dropped
— $2–4 counted, about $3–6 with the meal, summary and plan calls inside the
runs that the reports do not count.

## The fix order

Decided 2026-10-09: **a loop, with the person at each turn of it.**

1. **Round 0 — the eval matches these decisions.** No change to the agent.
2. **Each round:** run the eval three times → Claude reads every reply against
   the tool results → a fix plan: what failed, grouped by cause, and the change
   proposed for each → **the person approves or changes the plan** → the fix →
   the next round.
3. **Every round reads the whole surface the model reads** — the prompt's rules
   *and every tool's description and parameters* — not only the rule nearest
   the failure. Several failures trace to a tool, not the prompt: a search
   filter that hides what it was asked to find, a write tool reached for
   because no read answered the question.
4. **Fixes, in the order of the *Already fixed* rule:** a server-side guard
   first (a write on a turn that asked nothing is refused; a lookup read makes
   no card), then a fact or field in a tool's result, then prompt prose.
5. **It stops** when every case passes three runs in three, when what is left
   needs a product decision, or when a round makes no progress.
6. **Then reasoning effort — on Luna only.** Medium first, high as the
   ceiling; each run on the same cases, three times, so the change is
   measured, not felt. **The agent does not move to a bigger model** (decided
   2026-10-10): at the official prices that day a turn costs about ₹0.07 on
   Luna and ₹1.4 on Terra — ₹60 against ₹1,250 a month for a person who sends
   thirty messages a day. What effort adds in latency is measured with it.

## Levers — which were pulled

- **Reasoning effort — measured, and changed.** The agent ran at `none`,
  chosen 2026-09-15 for speed on single-step turns. Measured side by side in
  round 5, **medium** won on multi-step turns for about ₹0.0015 more a turn;
  it is the default now (*Where it landed*).
- **The size of the rules, the tool count, a check at runtime — not
  pulled.** The bar was reached without them. Each is parked in
  `spec/notes.md` with what would bring it back, alongside the one decision
  this work left open: where a task with no project named is filed.

## Definition of done

| Check | How |
|---|---|
| Every pattern above is at least one case | `evals/cases.py`, review — **done** |
| A baseline is recorded on Luna, then the score after the fixes | `n2n_eval` reports — **done**, *Where it landed* |
| Around 95% on Luna, by fixes and effort, never a bigger model | **met, without glue**: 96.3% of cases and 98.7% of turns at medium in the last round; 95.1–98.8% across the four rounds before it |
| Every case passes three runs in three | **set aside by decision** — run-to-run judgement is accepted at today's rate (*Decided after the loop*). The last round: three cases short, each once in three, listed above |
| No case regresses on a prompt or tool change | `n2n_eval`, before every such change |
