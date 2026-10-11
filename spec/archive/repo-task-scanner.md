# Repo task scanner — tasks from markdown checkboxes

> **Archived 2026-09-27 — not being built.** This was `task-sync.md`: a
> Claude Code plugin that scanned repositories for `- [ ]` lines, wrote an
> invisible `<!--cx:a7f2-->` marker into each so a task survived rewording,
> and reconciled ticks between the file and the phone. The work sync that
> replaced it reads **Linear and Wispr Flow** instead — `spec/work-sync.md` —
> and neither needs file markers, a scanner or file-versus-phone conflict
> rules. Why it was parked and what would bring it back:
> `spec/notes.md` § *Repo checkboxes as a task source — archived*.
>
> Kept for the identity argument (why only a marker survives rewording) and
> the conflict table, which are the parts worth reusing if repos ever become a
> source. The memory tools it mentions were archived separately —
> `spec/archive/shared-memory.md`.

> Status: **in progress** — the next build, and the largest one.
> Surface: a Claude Code plugin (MCP server) · backend · frontend
> Feeds: Work mode — `spec/../frontend/README.md`, the Work section
> Slice of: `spec/agent-everywhere.md` — the same plugin, all three modes

## What has changed since this was drafted

Four things were settled while the rest of the app was built, and they change
what this plugin has to be:

- **The backend it writes to already exists.** `tasks` and `projects` shipped
  with `spec/done/work-data-model.md`, and `POST/PATCH/DELETE /tasks` with
  `spec/done/ledger-writes.md`. The plugin is a *client* of an API that is
  built and tested — it adds no tables.
- **It is not only about tasks.** `spec/done/users-profile.md` put the user's
  memory in Cortex in our own format, and decided the same MCP server carries
  `profile_get`, `memory_search` and `memory_add` — three thin wrappers on
  `/users/me` and `/memories`. One plugin, one auth, one sync loop; a second
  plugin for memory was explicitly decided against.
- **Backend features land with their tests** (CLAUDE.md). Everything the plugin
  calls is already covered by `backend/tests/`; anything new it needs gets a
  test in the same commit.
- **`user_id` is real.** The seam returns the one user's ULID, so a token maps
  to a user the day auth exists. The plugin sends no user id and never could.

### The token, which this spec did not have

The plugin talks to the same API the phone does, and that API has no auth yet
(`spec/notes.md` § Auth). For a plugin running on the user's own laptop against
`localhost`, that is survivable and it is what v1 does. **The moment the backend
is not on localhost, this needs the bearer token the seam was built for** — one
token, in the plugin's config, checked in `app/auth.py`. That is the first thing
to add, and it is small because the seam already exists.

## The architecture decision, first

Everything else in this file follows from one line:

> **Claude Code is the super app. Cortex is the quick way, on the phone.**

Linear, email, Confluence, meeting transcripts from Wispr Flow — all of them
connect to **Claude Code**, which already has MCP servers for that sort of
thing. **Cortex connects to exactly one thing: this plugin.**

What that buys, and it is a lot:

| | |
| --- | --- |
| **Integration surface** | One. Not one per source |
| **Adding a new source** | Configure Claude Code. Cortex changes by zero lines |
| **Auth to maintain** | One token, not five OAuth flows with five refresh cycles |
| **Play Store review** | No Gmail scope, no calendar scope, nothing to justify |
| **What Cortex has to know about Linear** | Nothing, ever |

This also **shrinks `spec/api.md`**. That spec assumed adapters — a browser
extension, a notification listener, Health Connect, `hamsun-api`. For *work
data*, there is now one inbound path, and it is this.

**The cost, stated plainly:** Cortex only learns about new repo tasks when
Claude Code has run. Laptop off for three days means three days of nothing new
in Kaam. The phone still reads everything already synced — it just does not
grow. That is acceptable because work tasks are created *at* the laptop anyway,
but it is a real dependency and it should not be discovered later.

---

## The problem

Tasks arrive from meetings, Linear, Confluence, and from writing them down. But
in practice they all end up in the same place: **written in Claude Code, while
working.**

And there they scatter. A task lives wherever the feature lives — a checkbox in
`spec/workout.md`, another in `TODO.md`, another halfway down a design note.
By Thursday, "what was I supposed to do" means opening four files.

The scatter is not the problem to fix. **The scatter is fine — it is where the
task belongs, next to the work.** What is missing is an index.

---

## The protocol — markdown checkboxes, wherever they already are

No new format. The user already writes:

```markdown
- [ ] Retry logic on 429
- [x] Auth middleware split
```

That is the protocol. The plugin scans for it. Nothing to adopt, nothing to
remember, and a task written by hand in a file the plugin has never seen still
gets picked up the next time it runs.

**Scan scope**, in order of confidence:

| Where | Treated as |
| --- | --- |
| `TODO.md` at repo root | Tasks |
| `spec/**/*.md` | Tasks |
| Any `*.md` with a `## Tasks` or `## To-do` heading | Tasks under that heading only |
| Everywhere else | Ignored |

That last row matters: **not every checkbox in every markdown file is a task.**
A spec's testing checklist is not something to put on a phone. Scanning
everything would flood Kaam with noise on day one, and a noisy list is one
nobody opens.

---

## Identity — the genuinely hard part

A task is a line of text in a file that gets reworded, moved, and re-indented.
None of the obvious keys survive that:

| Key | Breaks when |
| --- | --- |
| Content hash | You reword the task — which is most of what editing a task is |
| `file:line` | You insert a line above it |
| `(repo, file, text)` | Both of the above |

Every one of these turns an edit into "old task disappeared, new task appeared",
which loses its date, its priority, and the fact that you already ticked it once.

**The fix: the plugin writes a short id back into the line, once.**

```markdown
- [ ] Retry logic on 429 <!--cx:a7f2-->
```

An HTML comment is **invisible in rendered markdown** — on GitHub, in a preview,
in anything that renders. It survives rewording, re-indenting, and moving the
line to a different file. It is the only thing that does.

This does mean **the plugin edits your files.** That is a real cost and worth
being explicit about:

- It only ever appends a marker to a line that is already a task
- It never reorders, reformats, or rewrites anything else
- It runs on your machine, in a git repo, so every write is reviewable and
  revertible like any other change

**The fallback, if that is unacceptable:** key on `(repo, normalised text)` and
accept that rewording orphans the old task and creates a new one. Simpler, no
file writes, and it loses history. My recommendation is the marker — but this is
a call worth making deliberately rather than by default.

---

## The plugin is three things

### 1. A scanner

Runs on a Claude Code hook — `SessionStart` and after any `Write`/`Edit` that
touched a scanned path. Walks the scope above, parses checkboxes, and pushes the
delta.

```
- [ ] text            → open task
- [x] text            → done
line removed          → deleted (soft)
- [ ] → - [x]         → completed, with the timestamp
```

### 2. An MCP server

So Claude Code can create and read tasks directly, without a file — which is how
a task from a meeting transcript or a Linear issue gets in.

| Tool | Does |
| --- | --- |
| `task_add` | Create a task. `{ title, project?, due?, priority?, source }` |
| `task_list` | What is open, optionally by project or due window |
| `task_done` | Close one |
| `task_sync` | Force a full rescan of the current repo |
| `profile_get` | The user's row — targets, timezone, city. `GET /users/me` |
| `memory_search` | Facts about the user, by kind or text. `GET /memories` |
| `memory_add` | Remember one, in our format. `POST /memories` — same slug updates |

The last three are `spec/done/users-profile.md`'s: they are why Claude Code
knows who it is talking to without the user retyping it each session. They are
thin — the API does the work, and the tool is a shape and a sentence.

`task_add` writes to the DB **and** appends the line to that repo's `TODO.md`,
so a task created from a meeting still lives next to the work rather than only
in a database. One place to look, whichever way it arrived.

### 3. An organiser, on a schedule

The piece the first draft missed. Scanning collects; nothing **kept things
clean** — and the real repos (see the samples in
`spec/done/work-data-model.md`) show what unkept looks like: the same
task written twice, priorities in three private syntaxes, status buried in
prose.

A scheduled run — every morning, optionally once more midday — does what a
person never sticks to doing:

1. Scan the repo (checkboxes **and** prose — the LLM reads `pending/` folders,
   `## Status:` lines, notepad-style scribbles)
2. Normalise into the repo's **standard task file** — one file, sections by
   state: `Doing / Open / Waiting / Done (recent)`
3. Dedupe — a CAPS line written twice is one task, and the LLM is the only
   parser that can tell
4. Push the delta to Cortex, so the phone is current before the day starts

**This resolves a tension rather than reversing a decision.** The rule *"nobody
adopts a format"* stands — for the human. You keep scribbling in whatever
dialect the day produces. The standard file is the **plugin's output**, not
your input: the format is adopted by the machine, which never forgets to
follow it.

The human may edit the standard file directly too — it is markdown in the
repo, and the scanner treats it like any other scanned file.

---

## Which way does state flow

The Kaam design note said mirrored tasks were read-only on the phone — tick them
in the repo. That was the safe answer, and it is the wrong one now: **ticking on
the phone is exactly the "quick way" the phone is for.**

The resolution is not two-way file editing. It is:

> **The phone writes to the DB. The plugin is the only thing that writes files.**

```
phone tick ──▶ DB: done, at 14:22
                     │
                     ▼  (next time Claude Code runs)
              plugin sees DB is ahead
                     │
                     ▼
              rewrites the line to - [x]
```

The phone never touches a file, never needs the repo, never fights git. The
laptop reconciles when it is next on.

**Conflicts.** File says `- [ ]`, DB says done. Compare timestamps:

| Situation | Winner |
| --- | --- |
| DB `updatedAt` > plugin's last scan | DB — mark the file done |
| File modified after the last scan | File — the human edited it more recently |
| Both changed since last scan | File wins, and the plugin logs it |

The file wins ties on purpose: it is the thing sitting in a git diff where
someone can see it.

---

## Projects

Kaam groups by project, so tasks need a stable project key.

```
git remote get-url origin   →  github.com/sonu/novacart-chan   ← preferred
no remote                   →  directory name                 ← fallback
```

The remote is the right key: a repo cloned to a different path is still the same
project, and a directory renamed locally should not split a project in two. The
display name is the last path segment — `novacart-chan`.

---

## Data

Tasks are **ledger-adjacent but mutable** — a task is state, not an event, which
is the one place `spec/substrate.md` allows an in-place update.

```ts
interface Task {
  id: string;            // "a7f2" — the marker, and the DB key
  title: string;
  done: boolean;
  doneAt?: string;
  doneBy?: 'phone' | 'file' | 'mcp';

  project?: string;      // git remote, normalised
  due?: string;          // "2026-08-27"
  priority?: 1 | 2 | 3;

  // provenance — the answer to "kahan pe likha tha"
  source: 'file' | 'mcp';
  repo?: string;
  path?: string;         // "spec/workout.md"
  line?: number;         // last known — for a jump link, never for identity

  createdAt: string;
  updatedAt: string;
  deletedAt?: string;
}
```

`line` is stored but explicitly **not** part of identity — it is there so the
phone can show `spec/workout.md:44` and a future desktop link can jump to it.
It goes stale constantly and that is fine.

### Due dates and priority, without a new syntax

Inline, in the line, because a separate metadata block is a thing nobody fills:

```markdown
- [ ] Retry logic on 429 @27aug !1
```

`@date` and `!1..3`. Both optional, both stripped from the title before display.
If neither is present the task is undated — which `spec/../frontend/README.md`
already handles: undated work stays out of the week's bars and only appears
under `Poora`.

---

## What this replaces

| Was going to be | Now |
| --- | --- |
| A `PostToolUse` hook that POSTs deltas (Kaam design note) | A plugin. A hook is fire-and-forget; this needs to read back, so it has to be bidirectional |
| Adapters per source in `spec/api.md` | One inbound path for work data |
| Cortex integrating Linear / Gmail / calendar | Claude Code does. Cortex never learns those APIs |

---

## Testing

- A checkbox in `TODO.md` appears in Kaam after one scan
- Rewording a task keeps its id, its due date and its done state
- Moving a task to another file keeps its id, and `path` updates
- A checkbox outside the scan scope is **not** picked up
- `task_add` from MCP lands in both the DB and `TODO.md`
- Tick on the phone → next scan rewrites the file to `- [x]`
- Tick in the file → phone reflects it after the next scan
- Both changed since last scan → file wins, and the conflict is logged
- Deleting the line soft-deletes rather than dropping the row
- A repo with no git remote still gets a stable project key
- Two repos cloned to different paths with the same remote are one project

## Definition of done

1. Writing `- [ ] something` in a scanned file makes it appear in Kaam without
   any other action.
2. Ids survive rewording, re-indenting, and moving between files.
3. The plugin never modifies a line other than to append or update its marker or
   its checkbox.
4. Ticking on the phone reaches the file on the next Claude Code run.
5. Conflicts resolve by the table above, and every one is logged where a person
   will see it.
6. `task_add`, `task_list`, `task_done`, `task_sync` all work from a Claude Code
   session.
7. Scan of a repo with 200 markdown files completes fast enough not to be
   noticed at session start.
8. Cortex has no credentials for Linear, Gmail, or anything else.

## Decided against

| Option | Why not |
| --- | --- |
| A new task file format | Nobody adopts a format. Markdown checkboxes are already being written |
| Scanning every `.md` for checkboxes | A spec's test checklist is not a task. Kaam floods on day one and stops being opened |
| Content hash as identity | Rewording is most of what editing a task is, and it would orphan every edit |
| `file:line` as identity | One inserted line above breaks every task below it |
| The phone writing files directly | Collides with git state, needs the repo on the device, and turns a tick into a merge conflict |
| Cortex integrating Linear / Gmail itself | Five OAuth flows, five refresh cycles, and Play Store scopes to justify — for data Claude Code can already reach |
| A hook instead of a plugin | Fire-and-forget. This has to read back to reconcile phone ticks |
| Storing `line` as part of the key | It goes stale constantly. Useful to show, useless to identify |

## When it runs — decided

The schedule is primary; hooks are secondary.

| Trigger | Job |
|---|---|
| **Morning schedule** (and optionally midday) | The full organiser pass above |
| `SessionStart`, debounced | Catch-up scan, so a session sees last night's edits |
| After `Write`/`Edit` on a scanned path | Cheap delta scan only — never the organiser |

Cortex follows the push; if polling is ever needed, it polls a few minutes
after the scheduled run rather than on its own clock, so the two stay in step.

## Open

- **Does the marker-in-file trade sit right?** It is the only thing that makes
  identity survive an edit, but it does mean a tool writes into your source. The
  fallback is described above and is genuinely worse — but it is your call.
- Should completing a task in Kaam that came from `spec/**` also be reflected in
  that spec's own status line, or only in the checkbox?
- **Is `TODO.md` the right home for MCP-created tasks**, or should meeting tasks
  live somewhere that is not a repo at all? A task from a meeting may not belong
  to any project.
- **`spec/api.md`'s build order is spent.** `GET /deck` shipped, and so did
  everything after it that does not need the agent. This is the last agent-free
  spec.
