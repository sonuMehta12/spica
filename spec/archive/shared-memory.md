# Shared memory — Cortex's memory, read by Claude and the others

> **Archived 2026-09-26 — not being built.** Parked to keep the first MCP
> server to one job, work sync; nothing in work sync depends on it. The design
> below had reached four decisions when it was parked, and they stand if it
> restarts. Why it was parked and what would bring it back:
> `spec/notes.md` § *Shared memory — archived*.
>
> **What this does not archive:** the `memories` table, `/memories`, and the
> Cortex agent's `remember` tool. Those shipped with `spec/done/users-profile.md`
> and Cortex's own agent keeps using them. Only *sharing* that memory with
> assistants outside Cortex is parked.

## The idea

Facts about the person are scattered across every assistant they talk to —
Claude Code's memory files, the Claude app, ChatGPT, Gemini — each holding a
slightly different, slightly stale copy. The aim was **one memory**: Cortex
holds the facts once, in its own format, and every assistant reads the same
ones. Telling one assistant *"I reply in English"* should not have to be
repeated to the next.

## What already exists

Built with `spec/done/users-profile.md`, and not affected by this archive:

| Piece | What it is |
|---|---|
| `memories` table | One fact per row: `slug · kind · text · source · confirmed_at`. `slug` is the identity, so the same fact rewritten by two agents is one row |
| `kind` | `identity`, `preference`, `style`, `interest`, `project`, `reference` |
| `source` | `user`, `claude-code`, `claude`, `chatgpt`, `gemini`, `cortex` — who wrote it |
| `GET/POST/PATCH/DELETE /memories` | The API; soft deletes, same slug updates |
| `remember` (agent tool) | Cortex's own agent writes a fact, `source = 'cortex'` |

On 2026-09-26 the table held 13 rows, 8 imported from ChatGPT and 5 stated by
the user. None had come from Claude.

## How the design got here

1. **`users-profile.md`** made Cortex the store and put three tools on the
   task-sync MCP server — `profile_get`, `memory_search`, `memory_add` — rather
   than a second plugin with its own auth.
2. **`notes.md` § *Memory sync*** found that no hosted assistant (Claude app,
   ChatGPT, Gemini) exposes an API for writing into its own memory, so the only
   honest path to them is pull-by-tool: the assistant asks Cortex when it needs
   a fact.
3. **`in-progress/borrowed-runners.md`** proposed a weekly local routine that
   reconciled `~/.claude` memory files against `memories` rows, in both
   directions.
4. **The work-sync brainstorm (2026-09-24 to 26)** replaced that routine with the
   design below, and then parked the whole feature.

## The design, as it stood

### 1. Read-only from Cortex

Claude reads Cortex's memory and never writes it. The MCP server carries no
`memory_add`. Cortex's own agent and the user, in the app, are the only
writers.

**Why:** one writer per fact is what keeps the store trustworthy. Claude Code's
memory is written freely and mostly about the work in front of it; letting it
write into Cortex would make Cortex a second copy of Claude's notes rather than
the one place the person's facts live.

**The cost, accepted:** something told to Claude about oneself stays in
Claude's memory and never reaches Cortex. A write tool is one addition later if
that turns out to matter.

### 2. Live read, not sync

A `SessionStart` hook in the Claude Code plugin loads the profile and the
memories into every session. Claude Code never keeps its own copy of these
facts, so there is nothing to keep in step.

**Why:** two copies kept equal by a periodic job drift apart between runs, and
they bring deleted facts back — delete a memory in Cortex, and next week's job
finds it in a Claude file and re-adds it. Reading live at session start has
neither problem, and it is current to the minute rather than to the last run.

This is also the one thing that made a **plugin** necessary rather than a bare
MCP server: an MCP server can offer tools, but only a hook can put context
into a session before the first message.

### 3. No reconcile routine

Nothing collects Claude Code's memory files into Cortex, weekly or otherwise.

**Why:** Claude Code's memory is **per project**, and most of it is rules for
one repository — *commit only when asked*, *spec first, then build* — not facts
about the person. Lifting those into Cortex mixes two different things. The
few that are about the person (*Applied AI Engineer, Delhi*; *replies in
English*) belong in Cortex because the person said them, not because a job
scraped them.

### 4. The Claude app and ChatGPT reach it by tool, through a connector

There are no hooks outside Claude Code. In the Claude app, ChatGPT or Gemini,
memory arrives only when the model calls `profile_get` or `memory_search` —
which needs Cortex reachable as a remote MCP server, and for the Claude app,
added as a **claude.ai custom connector**. That in turn needs **OAuth on
`/mcp`**; static request-header auth exists for custom connectors only as a
beta for a limited set of organisations.

## Decided against

| Option | Why not |
|---|---|
| Two-way sync between `~/.claude` memory files and `memories` | Drift between runs, and deleted facts come back from the other copy |
| A weekly reconcile routine | Claude Code memory is per project and mostly about repos, not the person |
| `memory_add` on the MCP server | Two writers per fact; Cortex stops being the one place the facts live |
| Writing Cortex's facts into `~/.claude` files | A second copy again; the hook reads live instead |
| Pushing into a hosted assistant's own memory | No such API exists, and pushing personal data into a third party is the export leak the product refuses (`notes.md`) |
| A separate memory plugin | Two plugins, two auths for one brain — already decided in `users-profile.md` |

## If it restarts

Start from the four decisions above. The smallest useful slice is the
`SessionStart` hook alone: a Claude Code plugin with one hook calling
`GET /users/me` and `GET /memories`. It needs the plugin and a token to exist,
both of which work sync builds anyway, so restarting later costs little.
