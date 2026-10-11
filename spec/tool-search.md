# Tool search: a resident set, and a bucket behind it

> Status: settled, not built — the trigger has not been reached
> Surface: backend

Written 2026-09-13 at 21 tools, so the decision is on the shelf when the count
grows. Nothing here is owed yet.

## The problem it will solve

Every tool the agent has is sent on every request. Twenty-one of them today:

| | tokens |
|---|---|
| full schemas, as sent | 3,538 |
| of which parameter schemas | 2,117 |
| of which names and descriptions | 966 |

That is the largest single block in the request, bigger than the system prompt.
Past some count the model also starts picking the wrong one — two tools that
sound alike are two chances to reach for the nearer name.

**The token cost is not the reason to act.** The schemas sit in the static
prefix and are cached (`spec/done/prompt-layout.md`), so a resident tool is
paid for once and hit thereafter. Hiding tools saves the *cache-miss* price,
not the per-turn price, and a search costs a round trip and a miss of its own.

**The reason to act is selection accuracy**, and that means the trigger is a
measurement, not a number. Thirty is the moment to start *checking*, not the
moment to build.

## The trigger

Build this when a live eval shows the model picking the wrong tool on turns
where the right one exists — not when the count crosses a line. Two things to
measure before touching anything:

- **wrong-tool rate** by turn, from `messages.tool_trace`, which already
  records every call with its arguments
- **whether it improves** with the bucket in place

If accuracy is fine at forty tools, forty tools is fine.

## What it does

**Names stay. Schemas go.**

This is the whole design, and it comes from a failure that repeated five times
in one afternoon: asked something the tools could answer, the model reached for
the nearest-looking *field* and got it backwards — `spent` read as all
spending, `fixed` read as what is committed, `udhaar` read as who owes what. A
model that mis-selects among tools it can *see* will not go looking for one it
cannot. Hiding a tool completely is how it stops being used at all.

So the request carries three things instead of one:

1. **The resident set** — full schemas, as today.
2. **The catalogue** — one line per bucketed tool, name and a few words. 291
   tokens for all twenty-one; call it 15 per tool. The model always knows the
   tool exists and roughly what it is for.
3. **`find_tools(need)`** — returns the full schemas for the matches, which the
   runner then adds to the next round's `tools` array.

The saving is real because the parameter schemas are the bulk: 2,117 of 3,538
tokens. A bucketed tool costs 15 tokens instead of 170.

## What stays resident

Not "the most used". The rule is **how obvious the tool is from the words the
user says**:

- **Resident** — anything the model must consider *unprompted*. The two reads
  (`paisa_report`, `diet_report`), the two logs, the four correct/delete tools.
  A turn that should have read the ledger and did not is a wrong answer with no
  symptom.
- **Bucketed** — anything whose trigger phrase names it. *"Yaad rakho"* is
  `remember`. *"Pantry mein paneer khatam"* is `pantry_move`. The search query
  writes itself from the user's own sentence.

The dangerous middle is a tool the model needs to *know to reach for* when the
user has not named it. `people` is the example: the udhaar bug happened because
the model did not use it while it was fully visible. Such a tool belongs in the
resident set however rarely it fires.

## Rules and edge cases

- **A searched turn is a cache miss.** The tools array changes, and the array
  sits in the cached prefix, so the whole prefix is re-billed for that turn.
  Budget for it: a bucket that gets searched on most turns is worse than no
  bucket at all.
- **The extra round trip** costs its own latency. `MAX_ROUNDS` must rise, or a
  search plus a write plus a read runs out of rounds.
- **Searched tools last the turn, not the thread.** Carrying them forward would
  make the prefix depend on conversation history, which is the mistake
  `prompt-layout.md` exists to avoid.
- **`find_tools` returns nothing** when nothing matches, and that is an answer:
  the model says what it cannot do rather than improvising, per the prompt rule
  already in place.
- **The catalogue is generated**, never hand-maintained. A tool registered in
  `TOOLS` and missing from the catalogue is invisible; a test should assert
  every bucketed tool appears in it.

## Decided against

- **Hiding tools completely, with no catalogue.** The saving is 291 tokens
  better and the cost is that the model stops knowing the tool exists. Five
  bugs in one session came from the model not finding the right thing while it
  was in plain sight.
- **Splitting by mode** — money tools when the talk is money. Conversations mix
  in one sentence: *"chai ₹40 aur do roti"* is both.
- **Merging more tools** to keep the count down. Forty-five became twenty by
  moving constants into the prompt and filters into fields
  (`spec/agent-tools.md`). What is left would only merge behind a `kind`
  switch, which that spec rejected: one verb on one kind of thing.
- **A count-based trigger.** Thirty tools with clean selection is not a
  problem. Measure, then act.
- **Loading tools by embedding similarity.** A closed set of twenty-odd names
  is a lookup. Vectors are for open sets.

## Open

Nothing to decide. The next step, when the trigger fires, is the measurement —
wrong-tool rate from `tool_trace` — not the implementation.
