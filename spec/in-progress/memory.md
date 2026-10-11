# What Spica knows about you — memory, context and learning

> Status: **requirement recorded, 2026-10-09 — to plan after chat quality.**
> Nothing here is decided beyond what *Rules already true* says.
> Surface: backend — the prompt (`app/agent/prompt.py`), the thread's window and
> summary (`app/agent/runner.py`), the memories and profile (`app/models/users.py`)
> Builds on `spec/done/chat-history.md` (one thread, the summary),
> `spec/done/prompt-layout.md` (what goes where in a request) and
> `spec/done/chat-quality.md` (whose failures pointed here).

## The problem

What the agent knows about the person is assembled fresh on every turn from
pieces that were each designed alone, and nobody has designed them as one
thing:

| Piece | What it holds today |
|---|---|
| Memories (`memories`) | Every row, in the prompt under *Who they are* — kind, slug, text |
| The profile (`users`) | Targets — protein, kcal, sleep, steps, savings — and name, city, timezone |
| The categories and projects | The ledger's own, listed in the prompt |
| The turn's context block | Today: date, clock, spent, today's limit, protein, tasks |
| The conversation window | The last `CHAT_WINDOW` turns, folded at `CHAT_FOLD_AT` |
| The summary | What a fold or a clear leaves behind, about `CHAT_SUMMARY_WORDS` words |
| Tool results | Seen in the turn that called them, never replayed later |

The chat-quality eval keeps landing here:

- *"dal ek katori thi"* sent `meal_id: PLACEHOLDER` — the history carries what
  was said, not the id of the row the agent wrote a turn ago.
- *"kaun si habits track ho rahi hain?"* reached for a write tool to find out —
  the habits were nowhere in its context. (Fixed by the chat-quality decision
  to show them every turn.)
- *"mere baare mein kya yaad hai?"* answered right and then *wrote* a memory:
  "User asks what is remembered about them". Nothing decides what is worth
  remembering.
- *"spent 25 on cigarette"* needs the person's own price of a cigarette to judge
  whether one was smoked; nothing gives the agent that.

## What it should become

A system that learns the person better over time, so the agent judges like
someone who knows them — and whose every piece of context is there on purpose.

Ideas recorded, not decided:

1. **A pass over each statement: is there something lasting here?** In the
   style the person calls *JEV* — route by intent, and extract a memory only
   when confident. It runs in the background, after the reply, never in its
   path; what it keeps carries its source and how sure it is, and a guess is
   confirmed before it is trusted.
2. **A summary that keeps what matters.** When old conversation is folded, the
   summary keeps facts, decisions and open questions — not a gist of the chat.
3. **What is learned from the ledger, not stored.** The usual price of a
   cigarette, the usual breakfast, the days money runs out — worked out from
   the rows when needed, never written down as a sentence (the rule below).
4. **An audit of the context.** For each piece above: what it costs in tokens,
   what the agent actually uses, what is missing, what is noise.
5. **Ids in the history.** A turn that wrote a row leaves its id where the next
   turn can see it, so a correction can point at what it corrects.

## Rules already true

- **Never store a sentence about the person's own data** (CLAUDE.md). A learned
  pattern is computed from live rows; a memory is a fact the person gave or
  confirmed, not a claim about their ledger.
- **Per-item delete, no export.** Every memory can be seen and deleted; there is
  no "download everything".
- **Shared memory with other assistants is archived** (`spec/archive/shared-memory.md`).

## Open

- What exactly the *JEV* pass is here, and which model runs it.
- When the background pass runs — every turn, or in a batch at night.
- How a learned fact is confirmed — the amber dot, a question, or the
  memories page.
- How memory is evaluated: *"yaad rakhna…"* recalled later; a fact learned
  without being told; a fact that should **not** have been kept.
- The token budget for the whole context, and what gives way first.
