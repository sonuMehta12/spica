# Work — data model

> The mode's English name is **Work** — the frontend's `Mode` type already says
> `'work'`, and identifiers are English by the spec rules. Kaam survives only in
> UI copy, where Hinglish belongs.

> Built, seeded and verified — 13/13 checks green against the reviewed CSVs.
> **Grounded in the user's own data first; generalising to other users is a
> later, separate step.** Three real samples below replace the workbook the
> other modes had.
> Reads from: `spec/task-sync.md`, `frontend/src/types.ts`

## Scope

The tables behind Work: projects and tasks, with provenance. **In:** the schema,
the Linear↔repo hierarchy, where non-repo tasks live, what ingestion must parse.
**Out:** plugin mechanics (scanning, markers, conflicts — `spec/task-sync.md`),
and Cortex talking to Linear, ever.

## How work actually moves

```
meeting recording ──┐
                    ├──▶  Linear issue         ← manager writes it, COARSE
Confluence / email ─┘        │
                             ▼
                    repo tasks + notepad       ← user writes them, FINE
                             │
                             ▼
                    Claude Code sees all of it
                             │
                             ▼
                    Cortex / phone             ← the quick way: read, tick
```

Two granularities, owned by different people. The scatter is deliberate — a task
lives next to its work; Work is the index, never the home. Some tasks have no
repo at all.

## The three samples

### 1. This repo — the tidy dialect

```
9 checkbox lines: 2 real tasks (TODO.md), 7 examples inside task-sync.md
```

Checkboxes, `TODO.md`, status expressed by folder (`spec/in-progress/` →
`spec/done/`). Also a bug: the decided scan scope would import task-sync's own
*example* checkboxes as real tasks.

### 2. The office repo (`NovaCart-chan/backend/design-docs`) — the prose dialect

54 entries over five months. **Zero markdown checkboxes anywhere.** Tasks exist,
but in none of the forms the protocol expects:

| Pattern | Real example |
|---|---|
| Status as **location** | `pending/` and `Archive/` folders — the doc's place is its state |
| A whole file **is** one task | `pending/DOCUMENT_VISION_DEFERRED.md` |
| Task files with prose sections | `TO-DO.md`, `ACTION-ITEMS.md` — headed items, no checkboxes |
| Status as a **prose line** | `## Status: files 1-7 reviewed; … remaining: files 9, 10, 12` |
| Ticket key in the **filename** | `FAI-1-known-issue-mcp-…` — a Linear-style id, hand-written |
| Waiting-on as prose | `Status: WAITING on the My Vets feature` |
| Names that don't index | `obserbility`, `suggested_quesitons`, `auth_intt` — typos frozen forever |

### 3. The notepad — the raw dialect

A direct dump, verbatim fragments:

```
Today( Important tab)
* Improve suggested question … ( po)
* Thinking dynamic  ( p1)
* Progress bar improvements ( p2)
* IMPRTANT CREATE LOG OR TRACKING FOR THE RESPOSNE, OBSERBLITY  ( report button)
====================
- Kestrel recipes
* Add the recipes  ( mere end )
* Peronna anliğning prompts changes with jordan
…
* IMPRTANT CREATE LOG OR TRACKING FOR THE RESPOSNE, OBSERBLITY
```

| Pattern | What it encodes |
|---|---|
| `( po) ( p1) ( p2)` | priority — a private syntax, `po` a typo for p0 |
| ALL CAPS | importance — a second, parallel priority syntax |
| `====` separators | context/project boundaries: Today, Kestrel, meeting notes |
| `( mere end )`, `for health ai` | ownership and project, parenthetically |
| `with jordan` | a person attached to a task |
| a full paragraph about emergency responses | an observation that is *almost* a task — not every line is one |
| a numbered list pasted from a meeting summary | already-structured tasks arriving as prose |
| **the same CAPS task appears twice** | the forgetting, visible in the data itself |
| empty `*` bullets | intent that never got words |

That duplicate is the sharpest row in all three samples: the system being built
exists because the current one loses things, and the loss is right there.

## What the samples change

**The checkbox scanner is one dialect, not the protocol.** `task-sync.md` built
on "the user already writes `- [ ]`" — true in this repo, false in the office
repo (zero in five months) and false in the notepad. Running the scanner on all
three today yields: 2 real tasks, 7 fictional ones, and nothing from the two
places with the most real work in them.

So the general inbound path is the one task-sync already has as its second
door: **Claude Code reads the prose and calls `task_add`.** An LLM is exactly
the thing that can read `## Status: … remaining: files 9, 10, 12` and produce
three tasks, or spot that a CAPS line written twice is one task. The scanner
stays — for repos that do use checkboxes it is cheap and exact — but it is an
optimisation, not the definition.

**Generalisation is explicitly deferred.** These parsers get built against the
three dialects above. Whether other people's notepads look like this is a
question for after the owner's own pain is solved.

## What already binds this schema

**The requirement in one line, from the user:** *Linear jaisa, par simple —
Linear mere paas pehle se hai.* A task is title + labels + date + project +
where its detail document lives; the standard file per repo is maintained **by
the plugin on a schedule**, never demanded from the human (see
`spec/task-sync.md` § An organiser).

**The prototype** (`frontend/src/types.ts` — a running UI, so requirements):

| Field | What the Work card does with it |
|---|---|
| `project` | groups the list; keys a bar in the chart |
| `due` | the chip, overdue tone |
| `priority` 1–3 | sort; undefined sorts last |
| `doneDay` | ticked tasks stay for the day, then drop |
| `src` | provenance — `spec/workout.md:44`, *"kahan likha tha"* |
| `kind` work/paisa/diet | becomes a **label** at the deck layer — see the table below |

**`spec/task-sync.md`** (settled there): identity = the `<!--cx:a7f2-->` marker;
project = git remote normalised; `@date !1..3` inline syntax; tasks are mutable
state (the one exception substrate allows); phone writes DB, only the plugin
writes files; `line` is display, never identity.

## The tables

```sql
CREATE TABLE projects (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL,
  key         TEXT NOT NULL,          -- git remote normalised; dir name; or a
                                      -- bare label like 'kestrel'
  name        TEXT NOT NULL,          -- 'novacart', 'cortex'
  color       TEXT NOT NULL,        -- from a palette at creation; stored, see below
  archived_at TIMESTAMPTZ,
  UNIQUE (user_id, key),
  ...envelope
);

CREATE TABLE tasks (
  id          TEXT PRIMARY KEY,       -- 'a7f2' — the file marker IS the key
  user_id     TEXT NOT NULL,
  title       TEXT NOT NULL,
  -- 'pending' and 'open' are the same word said twice; three states, no more.
  status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','doing','done')),
  done_at     TIMESTAMPTZ,
  done_by     TEXT,                   -- 'phone' | 'file' | 'mcp'
  -- Out of every view without deleting history. Not done (done is a result),
  -- not deleted (it happened) — just no longer worth showing.
  archived_at TIMESTAMPTZ,

  due         DATE,
  priority    INTEGER CHECK (priority BETWEEN 1 AND 3),   -- p0/CAPS → 1
  -- 'personal' / 'work' / 'diet' / 'paisa' / whatever earns its place.
  -- Deliberately labels and not a kind enum: the user is not yet sure diet and
  -- paisa tasks live in the todo at all, and a label costs nothing either way.
  labels      TEXT[] NOT NULL DEFAULT '{}',

  project_id  TEXT REFERENCES projects(id),   -- NULL is normal: 'complete POSH
                                              -- training' is just a task
  -- Where it CAME FROM, and the pointer back. Free text like meal_type — new
  -- sources will appear, and an enum would refuse them.
  source      TEXT NOT NULL,          -- 'self' | 'linear' | 'email' | 'meeting' | 'file' …
  source_ref  TEXT,                   -- 'ENG-142', a message id — nothing syncs, it just points
  -- Where the DETAIL lives, when there is one: the spec/PRD this task is about.
  -- A local path or a remote URL. NULL for a task that is only a sentence.
  doc_ref     TEXT,
  -- The dependency: what this task cannot move without. 'blocked by' is the
  -- word Linear and Jira both use. Free text on purpose — the blocker is
  -- usually OUTSIDE the system ('jordan — prompt', 'My Vets feature'), and a
  -- task-to-task foreign key can arrive later if real need shows up.
  blocked_by  TEXT,

  -- Provenance of the task LINE itself, for file-sourced tasks: the answer to
  -- 'kahan pe likha tha', and the jump link.
  repo        TEXT,
  path        TEXT,
  line        INTEGER,               -- display only, never identity

  ...envelope
);
```

## Why `projects` is a table and `labels` is a column

A column holds a value; a table holds a thing with facts of its own. Project
earned a table the moment it gained three facts — `color`, `key` vs display
name, `archived_at`. Repeat those on every task row and they can disagree:
change the colour and miss one row, and the bar's colour depends on which task
got read first; rename and miss one, and the project silently splits into two
bars. One row holds the truth; tasks point at it.

Labels stay a column because a label has no facts — it is only a word. The day
labels need colours, they earn a table too. Same pattern Paisa already uses:
`counterparty_name` is text on the row, but the counterparty's own facts
(`is_peer`, `default_category`) live in their table.

## Settled in review

| Question | Answer |
|---|---|
| Q1 — Linear in the schema? | **No hierarchy at all.** Whatever arrives — Linear, notepad, email, any format — is processed and rewritten in **our** format as ordinary tasks. Linear is a `source`, its key is a `source_ref`, and nothing syncs back |
| Q2 — task with no project | Normal, expected, in the list. *'Complete POSH training' from an email is just a task with a source* |
| Q3 — which level do bars count | Dissolved by Q1: there is only one level. Every task counts equally |
| Q6 — `doneDay` | Derived from `done_at` in the user's timezone. No column |
| Q7 — duplicates | Cleaned at ingestion: the LLM sees existing open tasks when writing and merges instead of inserting |
| `kind` enum | Dropped for `labels` — not yet sure diet/paisa tasks belong in the todo, and a label costs nothing either way |
| Archive | `archived_at` on both tables. Not done, not deleted — no longer shown |
| Q8 — the dependency column | **Keep, named `blocked_by`** — the term Linear and Jira use. Free text: the blocker is usually outside the system (a person, another team's feature). A task-to-task FK is deferred until a real need |
| Q3 — one level of task | Confirmed again: a task is a task, Linear's big one or your small one. Priority carries urgency and importance, and that is enough |
| Q5 — `color` | **Stored on the project**, assigned from a palette at creation, user-changeable later. Precedent: Linear projects and GitHub labels both store their colour. The deciding argument: recognition — a project that changes colour per device stops being recognisable, and the deck must render identically from the DB |

## Deferred to the task-sync work session

> **Resolved 2026-09-27.** Repo scanning was archived
> (`spec/archive/repo-task-scanner.md`); work tasks arrive from Linear and
> Wispr Flow through a Claude routine — `spec/work-sync.md`.

How scanning actually works — what gets read, how prose becomes tasks, the
fenced-code-block fix — is deliberately not designed here. It is the first item
when `spec/task-sync.md` goes into build.

## Definition of done (draft)

| Check | Expected |
|---|---|
| This repo imports | exactly 2 tasks, none from task-sync's examples |
| The notepad, fed through Claude Code | its real tasks land with priorities mapped (`p0`→1, CAPS→1, `p1`→2, `p2`→3), sections becoming projects (`kestrel`), and the duplicated CAPS task landing **once** |
| An email task | lands with `source='email'`, no project, no doc — and renders fine |
| Archiving a task | removes it from every view; the row and its history remain |
| The office repo, fed through Claude Code | `pending/*` and the `## Status:` remainders land as open tasks; `FAI-1` becomes a `parent_ref` |
| Rewording a task | keeps id, due, priority, status |
| The morning run | rewrites the standard file sectioned by status, and Cortex matches it |
| Tick on phone | file shows `- [x]` after the next Claude Code run |
| The deck swap | Kaam card renders identically from these tables vs `seed.ts` |
