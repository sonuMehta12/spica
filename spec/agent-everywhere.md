# Agent everywhere — Spica on Claude surfaces

> Status: requirement recorded, deliberately without technical design.
> **Moved up 2026-09-16.** `spec/in-progress/borrowed-runners.md` found that
> every borrowed routine — work capture, memory reconcile, anything run from a
> Claude or ChatGPT schedule — can do nothing for Spica until its tools are
> reachable over MCP. The scheduler turned out to be a detail; this is the
> unlock. It also carries ~99% of the model spend: 235 agent turns cost 2.2M
> input tokens against one batched call a night for the categoriser.
> The *how* — sync, auth, context sharing — is open and gets its own pass.
> Surface: a plugin for Claude Code and the Claude app · backend
> Extends: `spec/work-sync.md`, the first slice — an MCP server with four
> task tools. This spec is what exposing the rest would be

## The behavioural fact this starts from

The user's chat already happens somewhere: Claude Code on the laptop, the
Claude app elsewhere. These are super apps now — that is where power users
talk, and the user is one. **Opening Spica will never become a habit, and
this requirement respects that instead of fighting it.**

So the premise sharpens:

> **Agent hi app hai — aur agent wahan rehta hai jahan baat pehle se ho rahi
> hai.** Spica is one surface of the agent, not its home.

| Surface | Role |
|---|---|
| **Spica (phone)** | The glance: the deck, the cards, a quick tick. Opened to *see*, sometimes to log |
| **Claude Code (laptop)** | Work happens here; the agent is in the room already |
| **Claude app** | Chat from anywhere, same agent, same knowledge |

## The requirement

One plugin (skills + tools) that makes every Claude surface able to answer and
act on Spica's data — the same things the Spica agent itself can do:

```
"aaj ka limit kya hai?"          ← paisa, computed from the ledger
"aaj ka to-do kya hai?"          ← kaam
"aaj ka meal plan bata do"       ← diet, from pantry + targets
"yeh log kar do"                 ← writes, not just reads
```

**Same context, both directions.** What the agent learns in a Claude chat, the
Spica app knows; what is logged from the phone, a Claude chat can see. Not two
agents with a sync problem — one agent with several mouths.

**Two-way means writes.** Logging a meal from the Claude app must land in the
same ledger as logging it in Spica. Read-only would make the plugin a
dashboard, and dashboards are what this product exists to not be.

## What this changes about what was already written

`spec/work-sync.md` builds the first piece of this: Spica's own MCP server,
behind OAuth, carrying only the four tools a work routine needs. This
requirement generalises it to **all three modes** — the same server, the rest
of the tool registry, the Claude app as a client. The door is built there;
this is what else goes through it.

## Deliberately not designed yet

Recorded so the next session starts here rather than re-deriving:

- **Sync** — how the backend, the phone and the Claude surfaces stay one brain.
  The `/events` question in `spec/notes.md` becomes live again here.
- **Auth** — a Claude app tool call must prove it is this user. Ties into the
  deferred auth work (`spec/notes.md`).
- **Context sharing** — "same context" needs a definition: recent
  conversation, or just the data? Where does a conversation started on the
  laptop continue from on the phone? The *memory* half was designed and
  archived 2026-09-26 (`spec/archive/shared-memory.md`).
- **The Claude app path** — a local plugin serves Claude Code; the app needs a
  remote reachable one. Different constraint, same requirement.
- **ChatGPT/other apps** — the user's behaviour argument applies to them too.
  Out of scope until the Claude surfaces work; noted so it is a decision, not
  an omission.
