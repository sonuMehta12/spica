# Borrowed runners — let Claude and ChatGPT run the routines

> Status: research, 2026-09-16. Nothing built, nothing undone.
> Surface: the question is where a routine *runs*; the answer changes what
> `spec/in-progress/schedules.md` is for and makes `spec/agent-everywhere.md`
> the critical path.
> Verified first-hand where it says so; read from documentation where it says
> that instead.

## The idea, as it was put

> Instead of running my cron inside Spica, run it on Claude or ChatGPT. They
> have good models I already pay a subscription for, and I do not have money
> to pay per-call. And why build the complexity when the easy, better method
> is already there? Tomorrow I want a work plugin — why build a plugin? Just
> make two or three routines. Point them at the MCP servers I already use, let
> them read and write our DB so they have context, and it is done. Same for
> memory: every night or once a week, reconcile what Claude and ChatGPT know
> with what our DB holds. Keep some routines local, borrow the rest.

It is a good idea and most of it is available today. One constraint decides
which half of it works now, and one correction is worth making about the money.

## The four runners that exist

| Runner | Where it runs | Reaches `localhost` | Billed as | Verified |
|---|---|---|---|---|
| **Claude Code scheduled tasks** | **this Mac**, while the app is open; a missed run fires on next launch | **yes** | the Claude subscription | first-hand — the tools are in this session, and the user already runs one (*Amazfit stock watch*, 10:03 daily) |
| **claude.ai routines** (remote triggers) | Anthropic's cloud | no | subscription | first-hand — the API answers; the user has none yet |
| **ChatGPT Tasks** | OpenAI's cloud | no | subscription | documentation: time-based only, ~hourly ceiling, 3 tasks on Go / 5 Plus / 15 Pro, auto-pause if ignored; since Jun 2026 they may use web search and connected apps (MCP) |
| **Codex automations** | OpenAI's cloud container | no | subscription | documentation: schedules plus event triggers, e.g. on a GitHub push |

`CronCreate` inside a Claude Code session is a fifth and is not a candidate:
in-memory, dies with the session, expires after seven days.

## The one constraint

**Spica's data is a Postgres container on this laptop, on port 5434.** A
routine that runs in someone else's cloud cannot see it. That single fact
sorts every routine into one of three piles, and it is not a preference — it
is arithmetic.

```
                        needs Spica's data?
                   ┌──────────────┴──────────────┐
                  yes                            no
                   │                              │
        ┌──────────┴──────────┐                   │
   runs on this Mac      runs in a cloud      runs anywhere
        │                     │                    │
   ✅ works today        ❌ needs Spica        ✅ works today
   Claude Code             reachable and      a cloud routine that
   scheduled task          authenticated      only touches GitHub,
                           (deployment,       Linear, email, the web
                            not scheduling)
```

**Almost everything Spica wants scheduled is in the left pile**, because
almost everything Spica does is about the ledger. That is why the local
runner — which the user is already using for something else — is the one that
pays off immediately, and the cloud ones wait on a decision that has nothing to
do with cron.

## The correction worth making before anything is built

The premise was *"I cannot afford to pay per call."* True, and the cron is not
where the money is. Measured on the live database this morning:

| | calls | tokens in |
|---|---|---|
| **Interactive agent turns** | 235 | **2,208,996** (avg 9,400 a turn) |
| **The nightly categoriser** | 1 per run | ~6,000 |

The conversation is roughly **99% of the spend**; the nightly batch is one
call a day. Moving the cron to a subscription saves almost nothing.

This does not weaken the idea — it aims it. **The expensive thing is the
agent, and the idea that moves the agent onto a subscription surface is
already written: `spec/agent-everywhere.md`.** Borrowed runners and borrowed
*chat* are the same move; the chat one is where the money is.

## What this reframes

The user's instinct — *"why build a plugin, just make two or three routines"*
— is right about the scheduler and inverted about the plugin. A routine on any
of these runners is a prompt plus tools. For it to do anything for Spica it
must be able to **call Spica's tools**. That interface is the plugin:

> **The scheduler is a detail. The tool surface is the product.**

Once Spica speaks MCP, every runner in the table above can drive it — a local
Claude Code task, a cloud routine, ChatGPT, Codex, and Spica's own dispatcher
— without any of them knowing about the others. Without it, none of them can
do anything except through a shell script we wrote anyway.

So the order inverts from what it looks like: **`agent-everywhere.md`'s MCP
server is the unlock, and it was already item six in the queue.** This research
moves it up.

## Remote control — answered, both directions

The question was whether a routine can be fired or re-timed on demand — *"the
work data changed a lot today, I need it in an hour, not tomorrow morning"*.

**Yes, for Claude, verified in this session:**

| Want | How |
|---|---|
| Run a **local** routine now | `run_scheduled_task(taskId)` — identical to the *Run now* button |
| Run a **cloud** routine now | `RemoteTrigger action:"run"` |
| Re-time either | `update_scheduled_task` / `RemoteTrigger action:"update"` |
| See what a cloud run actually did | `RemoteTrigger action:"list_runs"`, then `get_run_log` |
| Fire a routine on a **GitHub event** rather than a clock | `RemoteTrigger action:"create_webhook_trigger"` |

So from a Claude Code session the user can say *"work sync abhi chala do"* and
it runs, local or cloud. **For ChatGPT Tasks no such external trigger API is
documented** — those are managed inside ChatGPT. If the emergency path matters
more than the model, that is an argument for keeping the work routine on a
Claude surface.

## The split, job by job

| Routine | Runner | Why |
|---|---|---|
| **Paisa categorise** | **Spica's own dispatcher** (built) | Needs the ledger; must not depend on a laptop being open at 20:30; and it is the one job that must survive onto the phone, where WorkManager is the runner and no Claude app exists |
| **Work sync** | **Claude cloud routine** — revised 2026-09-27 | Its sources, Linear and Wispr Flow, are claude.ai connectors, and a cloud routine runs with the laptop off once Spica is deployed. Designed in `spec/work-sync.md` |
| ~~Memory reconcile~~ | — | **Archived 2026-09-26** with shared memory — `spec/archive/shared-memory.md`. No routine runs for memory |
| **Morning brief** | **undecided** — see Open | Wants to arrive at 07:30 whether or not a laptop is open, which argues for Spica; wants a good model and rich context, which argues for borrowed |

**This is the hybrid the user described, and the line falls where they guessed:
punctuality and the phone stay home; context and reach are borrowed.**

## What `schedules.md` is for, after this

It stays, narrowed and honest:

- It is the runner for **anything that must happen without a laptop**, and for
  **anything that has to exist on Android**. Neither is negotiable for money.
- It is **not** the runner for work capture or memory reconcile. Those rows
  should not be added to `JOBS`.
- The `schedules` table was built so nothing a run needs is hardcoded. That
  property is what will let a *borrowed* runner read the same row later and
  honour the same time — one place where the user says when, whoever runs it.

Nothing built for it is wasted; the first job it runs is the one job that could
never be borrowed.

## Build order this suggests

1. **The MCP server** (`agent-everywhere.md`) — the twenty-three tools already
   defined, served over MCP, with the bearer token sign-in just landed. Every
   line below depends on this and nothing else does.
2. **The work routine** — now `spec/work-sync.md`: a Claude **cloud**
   routine reading Linear and Wispr Flow, through an MCP server that carries
   only its four tools rather than all twenty-three. This is the user's *"just
   make two or three routines"*; the prompt is one line, and the instructions
   are served by Spica.
3. ~~**The memory routine**~~ — archived 2026-09-26, `spec/archive/shared-memory.md`. Was: weekly, reconciles `~/.claude` memory files against
   `memories` rows. `notes.md` § *Memory sync* already ruled that pushing into
   a third party is the export leak the product refuses; reconciling files the
   user owns on their own machine is not that, and is worth re-reading before
   building.
4. **Cloud routines** — decided 2026-09-27: the backend is deployed on
   Render, running around the clock, which is also what the Android app needs.
   The work routine is the first cloud routine.

## Decided against

- **Moving the paisa categoriser to a borrowed runner.** It would arrive when a
  laptop happened to be open, and it is the job that has to work on the phone.
- **Exposing Postgres or the API publicly so cloud routines can reach it.** A
  personal ledger on a public endpoint is the largest risk in this project, and
  a tunnel with a bearer token is the same risk with a longer URL. If the
  backend ever leaves this laptop it should be a deployment decision taken on
  its own merits, not a side effect of wanting a cron. **Superseded
  2026-09-27** exactly as this said it should be: the backend is deployed on
  Render as its own decision — Android needs a server regardless — and
  `/mcp` sits behind OAuth with tokens scoped to it (`spec/work-sync.md`).
- **ChatGPT Tasks as the work runner**, for now. The ~hourly ceiling, the
  auto-pause when ignored, and the absence of an external trigger API all point
  the other way. Revisit if the work routine ends up wanting a model only
  OpenAI has.
- **Deleting `schedules`.** Two jobs above cannot be borrowed, and the Android
  app has no borrowed runner at all.

## Open

- **The morning brief's runner.** It is the one genuinely balanced case: it
  wants punctuality (Spica) and it wants a good model with broad context
  (borrowed). Deciding it needs the brief designed first.
- **Does a borrowed routine read the `schedules` row for its time?** It would
  keep one place where the user says *when*, and make the Profile screen tell
  the truth about routines it does not run. Cheap, and worth doing when the
  first borrowed routine exists.
- ~~**What the memory reconcile is allowed to write.**~~ Moot — archived 2026-09-26. Rows into Spica is
  clearly fine. Files into `~/.claude` is probably fine. Anything that pushes
  into a hosted assistant's own memory is the deferred question in `notes.md`
  and stays deferred.

---

### Sources

First-hand in this session: the `scheduled-tasks` tools, `RemoteTrigger`, the
live task list, and the token figures from the `cortex` database.

Read, not verified:
[ChatGPT Scheduled Tasks: Using Tools and Connectors](https://porteden.com/blog/chatgpt-scheduled-tasks-tools/) ·
[ChatGPT MCP: Setup, Plans, and Limits (2026)](https://coworker.ai/blog/chatgpt-mcp) ·
[OpenAI Codex Automations: Schedules and Triggers Guide](https://tudordaniel.ro/en/2026/04/24/openai-codex-automations-schedules-and-triggers-guide/) ·
[Introducing the Codex app](https://openai.com/index/introducing-the-codex-app/)
