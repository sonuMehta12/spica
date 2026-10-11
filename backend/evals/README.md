# evals

`n2n_eval` says a day of sentences to the **real model**, in order, and checks
what came back: the tool it ran, the cards in the reply, the rows that landed,
and what the reply says. It is the end-to-end half of `tests/`: those mock the
model and assert the server; this asserts the loop a person meets. Why it is
built this way, and what it found: `spec/done/chat-quality.md`.

```bash
cd backend
uv run python -m evals.n2n_eval                       # the day, three times side by side
uv run python -m evals.n2n_eval --repeat 1            # once — a quick look
uv run python -m evals.n2n_eval --upto pay-fix        # the day up to a case
uv run python -m evals.n2n_eval --only money,talk     # some groups, in order
uv run python -m evals.n2n_eval --only onboarding,plan-veg   # a block, and one case
uv run python -m evals.n2n_eval --effort none         # the same day at another effort
N2N_DB=cortex_eval_b uv run python -m evals.n2n_eval  # a second run beside the first
uv run python -m evals.judge_aid                      # the latest report, laid out to read
uv run python -m evals.to_artifact                    # the latest report, for the review page
```

- **It spends real tokens** — the model in `.env` (Luna), about 240 turns a full
  run: roughly 4 M input tokens, ~$0.20–0.40. Run it before every prompt or
  tool-description change. Not part of `pytest`.
- **One conversation, a day in order.** Each run is one account in its own
  database (`cortex_eval`), seeded with the lived-in week of `fixture.py`; the
  cases are said one after another at the clock each gives, so a correction acts
  on the payment just made. Today is left to the conversation.
- **Two blocks beside the day.** `plan` is Home's read — today's plan on the
  lived-in account at 08:00 and 18:30 (`plan-morning`, `plan-evening`), and on
  a veg account whose kitchen has eggs (`plan-veg`: no meat, fish or egg in any
  meal). `onboarding` is the first run (`spec/done/onboarding-goals.md`): each case on
  its own account **just signed in** — Google's name and nothing else, no
  lived-in week — said to `POST /onboarding/turn` with its question. A full run
  says the day and both blocks, and prints each block's score beside the total,
  so the day's own stays readable. `--only` takes day groups, `plan`,
  `onboarding`, or single case ids, mixed.
- **Three days side by side by default.** A case passes when it passes in all
  three; one that passes some is *flaky*, and counts as failing. The report
  gives both: cases passing every run, and turns passing.
- **Code checks, then Claude reads.** The checks grade what can be checked
  without reading for meaning. Claude reads every reply against the tool
  results the run captured — `judge_aid` lays a report out and points at the
  replies with numbers found in nothing the agent read.
- **Exit status 1** when any case fails outside a known gap. Each run writes
  `reports/n2n-<time>.json` with every reply, card, tool call **with its
  result**, and the turn's context block (git-ignored).

## Reading the output

```
 ✓ pay-log          3/3  chai 20
 ✗ thanks           1/3  thanks
       · wrote on a turn that asked for nothing: log_payment(…)  (×2)
 ~ ask              0/3  kal Rohit ko 500 diye
       (known gap: …)

cases passing every run: 95.1% · turns passing: 234/239 = 97.9%
first failure in each day: ['pay-recat', 'last-three', 'due-today']
```

`✓` every run passed · `✗` a run failed · `~` a known gap, already written
down, not counted. `(×2)` is how many of the days hit that failure.

## Adding a case

`cases.py` holds the day, in order. A case is a sentence, any `given`
sentences said just before it, the clock (`at=`, or spaced between the cases
that have one), and its expectations:

| Kind | Checks |
|---|---|
| tools | `called`, `not_called`, `no_writes`, `no_tools` |
| cards | `cards(...)` — the exact set; any other card is *unneeded* · `no_card` · `card` for one card's fields |
| rows | `row(sql, expect, says)` after the turn · `delta(sql, change, says)` — what this turn changed |
| the reply | `figure(sql, says, paise=)` — a number computed from the rows · `reply_has` · `reply_lacks` · `no_list` · `no_markup` · `says_today` |
| for Claude | `must=[…]`, `must_not=[…]` — what to look for when reading the reply |

A first-run case (`ONBOARDING`, at the end of `cases.py`) adds `question=` —
`about`, `place`, `health`, `money`, `habits` — and its `given` are earlier
answers to that question; `seed=` names state made through the API first
(`fixture.SEEDS`), for a fact the case must not leave to a model. Its checks
add `moves_on` / `stays` (the turn's `next`), `asks_once`, `weight_card` (the
estimate dot), `unchanged`, `untouched` (no payment, meal, task, tick or chat
line) and `kept_nothing` (a skip).

SQL takes `:u`, `:today`, `:yesterday`, `:tomorrow`, `:day_after`,
`:week_ago`. Keep a check to what must be true whatever words the model
chooses, and count with `delta`: earlier turns keep writing. Never write a
figure into a case — compute it from the rows with `figure`. `why` names the
real turn the case came from, with its date. A gap you know of and have
written down gets `known=` with where it is written.
