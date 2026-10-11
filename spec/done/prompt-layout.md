# Prompt layout: static first, now last

> Status: shipped 2026-09-13. *On the Responses API since 2026-09-15 the same
> rule holds with different names: the system prompt is `instructions` and the
> tool schemas are `tools` — both stable, both in front — and the summary, the
> window and the `[now]`-plus-message ride in `input`, in that order.
> `prompt_cache_key` is set per user so the provider routes the prefix to the
> same cache.*
> Surface: backend, plus what the client sends with a turn

## The problem

The agent told the user it was 12 September when it was the 13th, and that it
had no way to know the time. Both were true, and both came from the same
decision: **the agent is handed a date, not an instant.**

**The date was wrong** because the client never sent the device's day. It sent
an *anchor*, and in dev the anchor was the last day that had any row:

```js
// Dev anchors to the last day that has rows, so a static dataset keeps
// behaving like "today" instead of receding.
```

Right while the ledger was a frozen 24-day August import. Once it started
taking live writes the anchor sat on whatever was last logged, so it was only
ever correct on days something had already been logged, and drifted a day
further behind on every day skipped.

**The time was absent entirely.** Nothing in the request carried a clock, so
the model could not tell breakfast from dinner, and both write tools stamped
every row they created at `12:00:00` whatever hour it actually was.

**And fixing it naively would have cost money.** A provider's prompt cache
matches a *prefix* and stops at the first difference. The date sat 46 tokens
into the system prompt, in front of everything else:

| block | tokens | changed |
|---|---|---|
| preamble | 46 | on deploy |
| **`## Today`** | **87** | **every turn** |
| who they are | 551 | when a memory changes |
| targets | 23 | rarely |
| categories | 45 | rarely |
| rules | 631 | on deploy |
| tool schemas | 3,287 | on deploy |

87 volatile tokens in front of 4,538 static ones. Every turn re-billed all of
them at full price. Adding a clock to that block would have made it worse, and
adding it *correctly* is what this spec is about.

**A second, larger leak sat behind it.** `_fold` ran after every turn and its
gate was `total <= WINDOW`. With a thread past twenty messages, every turn
pushed it to twenty-two, folded two away, rewrote the summary and advanced the
pointer. So on every single turn:

- the rolling summary changed, and
- the twenty-message window slid by two, and
- **a second model call ran** to re-summarise those two messages.

The message list's prefix therefore never matched the previous turn's, and the
token counts reported on `ChatOut` never included the fold's own call.

## What it does

**The request is ordered by how often each part changes**, most stable first,
because that is the only order a prefix cache can reward.

| position | part | changes |
|---|---|---|
| 1 | system prompt: who they are, targets, categories, rules | deploy, or a memory edit |
| 2 | tool schemas | deploy |
| 3 | rolling summary | once per fold |
| 4 | the window of turns | append-only between folds |
| 5 | `[now]` block, then what they said | every turn |

`build()` no longer takes a date and runs no date-scoped query. That is the
invariant, and a test asserts it: no date, weekday, clock or `[now]` marker may
appear in the system prompt.

**`now_block()` carries everything volatile**, attached to the user's message:

```
[now] 2026-09-13 Sunday 08:44. 18 days left in the month.
[paisa] Spent this month ₹651. Today's limit ₹0, of which ₹0 is already gone.
[diet] Protein today 0.0g, 135.0g left. Calories 0 of 2050.
Work out any other date from this one …
Something that happened just now takes the clock above, not midday.
```

**It is never stored.** The window replays stored text, so a `[now]` from three
turns ago would be a stale number in front of the model — the same reason tool
results are never replayed. The stored message is exactly what the user said.

**Folding happens in batches.** `FOLD_AT = WINDOW * 2`: nothing folds until the
un-summarised tail reaches forty, then it folds back to twenty in one call. The
window is append-only for twenty turns and the extra model call runs once per
twenty turns instead of once per turn.

**The client sends its clock.** `ChatIn.local_time` (`HH:MM:SS`, optional). The
anchor is the device's day, with `VITE_ANCHOR` kept for deliberate time travel.

**A write with no stated time takes the turn's clock.** `T.run` accepts
`default_time` and fills `time` on any tool whose schema has it, unless the
model passed one. A model that says *"subah ki chai thi"* and passes
`time=07:15` still wins.

## Result

| | before | after |
|---|---|---|
| first volatile token at | 46 | 4,584 |
| static tokens behind it | 4,538 | 0 |
| extra model call for folding | every turn | every 20 turns |
| clock available to the agent | none | the device's |
| default timestamp on a write | 12:00 | the turn's clock |

## Compaction, since batching changed it

**Who summarises.** The same model, in a second call of its own, with one
instruction: *keep what the person asked for, decided, or is in the middle of;
drop every number and every date, because those are re-read from the database
and would go stale here.* Nobody else compacts anything — there is one thread,
one summary column, one pointer.

**How it works.** `conversations.summary_through_seq` marks how far the summary
reaches. Everything past it is the tail. When the tail reaches `FOLD_AT`, the
oldest `tail − WINDOW` messages are handed to the summariser along with the
existing summary, the returned prose replaces the summary, and the pointer
advances past them.

**The window is the whole tail**, not the newest `WINDOW` of it. Batching made
the tail grow between folds, and taking only the newest twenty left the middle
of the conversation in neither the summary nor the window — invisible to the
model. Ten live messages were in that hole when it was found. `WINDOW` is now
only the floor a fold returns to; `FOLD_AT` is the ceiling and the window's cap.

**A failed summariser costs nothing.** The turn commits first, then compaction
runs in its own transaction inside a `try`. Before this, `_fold` sat between
the flush and the commit, so a summariser timeout rolled back the turn — while
any tool that had already written stayed written, because the routes commit for
themselves. The user then retried and paid twice.

**The fold's own call is counted** into the turn's `tokens_in` / `tokens_out`.

**It reissues, and it stays out of the conversation.** Two rules, both arrived
at by measuring rather than by reasoning, and the second was a surprise.

*Reissue it in full.* The summary is the only record left of everything behind
the pointer, so an instruction that lets the model drop what is already there
loses it for good. The old wording, *"continue the existing summary rather than
repeating it"*, reads as permission to drop. *"Merge"* and *"nothing may be
dropped"* were both tried and were not enough either. *"Your previous note is
the only record left of everything it covers. Reissue it in full, changed only
where the new turns add to it"* is what actually carried it.

*You are not part of this conversation.* Handed a transcript that ended on a
question, the summariser answered the question — in the agent's own
second-person Hinglish, with markdown bold and live numbers — and threw the
note away entirely:

> *"Aaj ab tak aapne **560 kcal** aur **43g protein** consume kiya hai."*

That is a reply, not a note. It now says it is not in the conversation, never
addresses the person, never continues the agent's last reply, and writes about
them in the third person. A transcript ending on a question is recorded as a
question asked, not answered.

Measured: four topics seeded into a note, then eight folds, one of them
carrying a numbers-heavy exchange.

| | topics alive after 8 folds | numbers leaked |
|---|---|---|
| old wording, 120 words | 2 of 4, three gone after the **first** fold | — |
| shipped wording, 200 words | 4 of 4, at every fold | none |

The note grows 61 to 140 words across those folds and settles under the cap,
which is the behaviour wanted: it accumulates until the budget binds, then
drops what is finished.

**The knobs are configuration.** `CHAT_WINDOW`, `CHAT_FOLD_AT` and
`CHAT_SUMMARY_WORDS` in `.env`. A bigger window is a better-informed model and
a bigger bill, and the right trade differs per model.

## Rules and edge cases

- **`local_time` is optional.** Without it the `[now]` block carries the date
  alone and writes fall back to midday, which is the old behaviour. Nothing
  breaks for a client that has not been updated.
- **The prefix still breaks when a memory changes**, because memories sit in
  the system prompt. That is once every few weeks against once per turn, and
  moving them out would mean re-sending 551 tokens on every turn to save a
  break that almost never happens.
- **A tool that has no `time` in its schema never gets one injected.**
- **Compaction is best-effort.** A fold that fails is logged and retried on
  the next turn. The tail grows past `FOLD_AT` until one succeeds, and the
  window's cap keeps that bounded.

## Decided against

- **Leaving the anchor in dev.** It existed so a frozen dataset looked alive.
  The dataset is not frozen any more, and a screen that quietly lies about the
  date is worse than one that shows an empty day. `VITE_ANCHOR` covers the
  legitimate case, which is deliberate time travel.
- **Putting `[now]` in a system message of its own, after the static one.**
  It would cache identically. It goes on the user turn because that is where a
  fact about this moment belongs, and it keeps the message count honest.
- **Storing the `[now]` block with the turn.** It would make the transcript
  self-describing, and it would feed the model stale numbers forever after.
- **Replacing `local_day` with a single timestamp.** The day is the client's
  decision and the wire says so; deriving it from an instant server-side is the
  bug `local_day` exists to prevent.
- **Moving memories out of the system prompt** to make the prefix perfectly
  stable. 551 tokens re-sent every turn to avoid a break that happens when the
  user edits a memory. The arithmetic does not work.
- **Caching `build()` in process.** Tempting, and premature: the queries are
  two indexed reads, and a stale cache after a memory edit is a worse bug than
  the one it fixes.

## Verified

`backend/tests/test_agent.py`, eleven new tests: nothing that changes per turn
appears in the system prompt while the date, weekday and clock all appear on
the last user message; the `[now]` block is neither stored nor replayed; a
write with no stated time takes the turn's clock; a time the model states beats
it; the thread folds in batches rather than every turn; no message falls
between the summary and the window (checked against the real `_window`, and
verified to fail when the bug is put back); a failed summariser leaves the turn
and its ledger row intact; the summariser's own call is counted; the summariser
is told to reissue in full and to stay out of the conversation, and is handed
the note so far, with the configured word budget; the window and the fold threshold come from config.

Whole suite: 195 passing.

By hand in the browser on 2026-09-13 at 08:44 IST, asked *"aaj kya date hai aur
abhi time kya hua hai?"* — *"Aaj **13 September 2026** hai aur abhi **08:44**
baj rahe hain."*

## Open

**Nothing.** The drift this spec was opened with is fixed: see *It reissues,
and it stays out of the conversation* above. The live thread had been rewritten about 65 times into
120 words, because it folded on every turn, and by the end all 54 surviving
words were about the last three turns:

> *"The user requested deletion of the 'Never ate this (test)' meal because
> they did not eat it. The agent confirmed it was deleted…"*

Three causes, all now addressed: it folded far too often (65 times rather than
7, fixed by batching); the instruction let it drop history on each pass (fixed
by *reissue in full*); and, handed a transcript ending in a question, it
answered the question in the agent's voice instead of writing a note (fixed by
telling it that it is not in the conversation). The third only surfaced in live
use, after the first two had shipped.

The existing summary on the live thread is still the eroded one. It will not
recover what it lost — that history is gone — but it will stop losing more.
