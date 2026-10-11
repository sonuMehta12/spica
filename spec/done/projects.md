# Projects you make, and tasks you can say

> Status: **shipped 2026-09-27** — `backend/tests/test_projects.py`, and
> verified in the browser (§ Definition of done).
> Surface: both — backend (a migration, `/projects`, two agent tools, one
> placement rule shared with work sync) · frontend (Projects in Profile, the
> Work composer switched on)
> Extends: `spec/done/work-data-model.md` (the tables), `spec/work-sync.md`
> (which places tasks by the same rule)
> Shape borrowed from: `spec/done/habits.md` — a library the person can add
> to, one screen, one agent tool

## The problem

Projects exist in the data and nobody can make one. Every task can belong to a
project, but no route, no screen and no agent tool creates, renames or
describes a project: only the old import script and the work sync have ever
written one. And Cortex's own agent has **no tool that touches tasks at all** —
*"ye task add kar do novachan me"* gets an honest *"I can't"*, and the
composer on the Work card is switched off with a placeholder left from the
archived repo-sync plan.

The person's work is shaped simply: one or two work projects, and personal
tasks. What is missing is a way to say which is which — once — and have every
task land in the right one, whether it was said in chat or arrived from Linear
or a meeting.

## What it does

### Projects, in Profile — below Health

A **Projects** group, the way Habits live under Health:

- one row per project: its icon, its name, one line of its description, and
  how many tasks are open in it;
- tap a row to edit: name, description, icon, *also known as*; archive; delete;
- **New project** at the bottom;
- the default project is marked *Default — tasks with no project land here*,
  and can be renamed but not archived or deleted.

### Four routes

```
GET    /projects          every live project, archived ones last, with open-task counts
POST   /projects          client ULID, like every write
PATCH  /projects/{id}     name, description, icon, aliases, archived
DELETE /projects/{id}     soft; its tasks move to the default project
```

The deck already sends projects; it gains the new fields.

### The agent can manage projects and tasks

Two tools, following `manage_habit`'s pattern — a name *or* an id wherever a
project or task is named, resolved on the server:

| Tool | Does |
|---|---|
| `manage_project` | a name alone makes one; `project` names one to change (name, description, icon, aliases — added to, not replaced), `archive`, `delete`, `make_default` |
| `save_task` | no `task` **adds** one, placed by § Placement: `title`, and `project`, `due`, `priority` when said. A `task` — its id or words from its title — **changes** one: tick or untick, rename, re-date, re-prioritise, archive, or move it to another project |
| `work_report` | **reads** them: what is due today, tomorrow, this week or month, what is late or undated, what is open in a project, what got done — with each project's open, overdue, due-today and done-this-week counts. For a finished task the window is when it was finished |

**Two, not three.** Adding and changing a task were drawn as separate tools;
together with `manage_project` that put the agent at twenty-six, past the
ceiling of twenty-five `spec/agent-tools.md` set because a model picks among
fewer tools more reliably. One `save_task` keeps the rule, the way
`manage_habit` already starts, renames and stops a habit.

**A task is found the way it is said.** *"veg filter wala task"* names
*"Recipe list me veg filter lagana hai"*: the exact title first, then the
phrase inside a title, then every word left once the filler that points at a
task — *wala*, *task*, *ko*, *the* — is dropped. Two matches ask which.

A project that does not exist is never created silently. *"Isko Cortex-2 mein
daal do"* with no such project gets *"Cortex-2 nahi hai — bana doon?"*, and
`manage_project` runs only on a yes.

### The Work composer is switched on

Typing on the Work card talks to the agent like any other card. The
placeholder says what can be said there: *Add a task, or ask about work*.

## Data

### `projects` — four columns

| Column | Type | |
|---|---|---|
| `description` | text, null | One or two lines of what the project is, in the person's words. The agent and the routine read it to place a task that names no project — it is the most useful field here |
| `icon` | text, null | An emoji (`🛒`), or an icon from the app's set by name (`icon:briefcase`), the way Notion offers both. NULL draws the project's first letter in its colour. Nothing is uploaded |
| `aliases` | text[], default `{}` | What it is called elsewhere — `linear:Kestrel`, a repo remote, *NovaCart-chan*, *novachan*. Matched case-insensitively. What turns placement into a lookup rather than a guess |
| `is_default` | boolean, default false | The one project where everything unplaced lands. One per person, enforced by a partial unique index on live rows |

`key` stays what it is: the stable machine handle, unique per person. A
project made in the app gets a key from its name.

### `tasks` — one column, and no more tasks without a project

| Column | Type | |
|---|---|---|
| `project_guessed` | boolean, default false | The project was chosen by the model, not by the person or the source. Drawn with the amber dot, like every inferred value. Cleared the moment the person moves the task or confirms it |

Every task has a project from here on. The migration gives every person a
default project named **Personal** and moves their project-less tasks into it
(one task in the dev data today). A person who has none yet gets theirs the
first time a task needs it.

## Placement — one rule, used everywhere

Chat, the routine and the API place a task the same way, in this order, and
stop at the first that answers:

1. **The person named it** — *"novachan mein"*, or a `project_id`. Found by id,
   name or alias.
2. **The source names it** — a Linear issue's project. Found by the alias
   `linear:<project>`. When none has it, the model may decide it is plainly an
   existing project — Linear's *Kestrel* is the person's *kestrel* — and the
   server **adds the alias**, so the next run finds it without asking. When
   nothing fits, a new project named as in the source, with that alias. A
   project someone made deliberately in Linear is worth one here.
3. **Its nature** — a meeting item, a Linear issue with no project, a chat
   task that named none. The model reads every project's name, description and
   a few of its recent tasks, and places the task where it plainly belongs —
   marked `project_guessed`, and said: *"NovaCart-chan mein daal diya."*

   **In chat, whether it was a guess is read from the person's words, not
   trusted to the model.** A project whose name, key or alias does not appear
   in what they said — compared as letters and digits, so *novachan me* names
   *novachan* — was the model's choice, and is marked. Seen live before this
   rule: the model placed a task well and left the flag off. The words reach
   the tool from the runner, never as an argument the model can set. The
   routine, which has no one's words, says so itself with `project_guessed`.
4. **Nowhere clearly** — the default project, not guessed, and nothing said.

**It gets better by being corrected.** A task the person moves out of a
guessed project is the best example there is, and it now sits in the right
project's recent tasks — exactly what step 3 reads next time. Nothing extra is
stored to learn from; the rows already say it. How the model reads them is in
the skill files, which improve without a migration.

## Work sync, changed by this

- `work_sync_begin`'s projects gain `description`, `aliases`, `is_default`,
  and a few recent task titles each — the context step 3 reads.
- `tasks_upsert` gains `source_project` (`linear:Kestrel`): resolved by alias
  first, recorded as an alias when the routine picks an existing project, and
  used as the new project's alias when it makes one.
- An item that lands by step 3 is `project_guessed`; by step 4, the default.
- A Linear issue with no Linear project goes through step 3, not into a
  project named after the team. (*Acme*, made that way in the live test,
  stays — the person chose to keep it.)
- The instructions (`skills/work-sync/`) carry the rule above in the routine's
  words.

## Rules and edge cases

- **The default project** can be renamed, never archived or deleted; the only
  way to change which project is the default is to mark another one.
- **Deleting a project moves its tasks to the default project** — a delete
  never takes tasks with it. Archiving hides the project and its tasks from
  the deck, as `archived_at` already does.
- **An alias belongs to one project.** Adding one another project holds moves
  it, and says so.
- **Two projects with the same name** are allowed — keys and ids differ — but
  a named lookup that finds two asks which.
- **A guessed placement the person leaves alone** stays guessed; ticking the
  task does not confirm its project. Only moving it, or saying it is right,
  does.

## Decided against

| Option | Why not |
|---|---|
| Uploaded logos | Needs file storage the app does not have. An emoji or a named icon says the same at 12 pixels |
| Tasks with no project | Every task in one bucket or another is simpler to show and to move; the default project is the bucket for the rest |
| Creating a project silently from chat | A typo would become a project. One question costs a second |
| A project per Linear team | A team is usually the whole company; the live test showed it (*Acme*) |
| A table of placement corrections | The corrected task already sits in the right project, which is what the next guess reads |
| An LLM call to place every task | Steps 1, 2 and 4 are lookups; only step 3 needs judgement, and it rides the call already being made — the chat turn, or the routine's run |

## Definition of done

| # | Check | Verified by |
|---|---|---|
| 1 | `POST /projects` creates one; a replay returns it; `PATCH` changes name, description, icon, aliases | test |
| 2 | The default project cannot be archived or deleted; renaming it works | test |
| 3 | Deleting a project moves its open and done tasks to the default project | test |
| 4 | An alias lives on one project; adding it to a second moves it | test |
| 5 | `save_task` adding with a named project lands there; with an unknown one, nothing is written and the agent asks | test |
| 6 | `save_task` adding with no project named lands in the default one, or in a guessed one marked `project_guessed` | test |
| 7 | `save_task` with a `task` finds it by title, ticks it, and moves it; moving clears `project_guessed` | test |
| 8 | `tasks_upsert` with `source_project` resolves by alias, records the alias when the routine picks an existing project, and makes a project carrying it when nothing fits | test |
| 9 | The migration leaves no live task without a project, and every person with tasks has one default | test |
| 10 | Profile shows Projects below Health; a project made there appears on the Work card | browser, 2026-09-27 — made *NovaCart-chan* with a description, the cart icon and two aliases; it appeared on the Work card at once |
| 11 | The Work composer takes typing; *"ye task add kar do novachan me"* adds it to NovaCart-chan | browser, 2026-09-27 — landed by alias; a recipe task naming no project was placed in *Kestrel* with the dot; a grocery errand went to *Personal*, no dot; *"veg filter wala task novacart me move kar do"* moved it and cleared the guess |
| 12 | A project the person's words do not name is marked a guess; an alias in them is naming it; the model cannot supply the words | test |
| 13 | A task is found by the words that carry it, filler dropped; a project's name narrows; the best clear overlap wins | test |
| 14 | The same open task said twice in one project is one task | test |
| 15 | `work_report` answers due today, tomorrow, late, undated, open in a project, done this week; its counts come from rows | test |
| 16 | Every turn carries a `[work]` line; *"aaj aur kal kya due hai?"* asked from the Paisa card is answered with the right two tasks | test, and browser 2026-09-27 |

## Settled while building

- **The default project is named *Personal*.** Renameable; `personal` is its
  key, and a person who already had that key keeps that project as the
  default rather than a colliding second one.
- **Sixteen named icons ship**: briefcase, code, home, heart, book, cart,
  rocket, star, bolt, leaf, chat, money, globe, tool, person, flag — filled
  14-pixel shapes in the habit glyphs' style, drawn in the project's colour
  (`frontend/src/components/ProjectIcon.tsx`). The server accepts exactly
  these names (`app/projects.py`).
- **The Work card's chips stay money and food.** The composer takes typing
  there; the three quick-log chips are not work, so they do not show on it.
- **Deleting a task from chat** is deferred — `spec/notes.md`.

## Found using it, 2026-09-27

- **The agent could not read a task.** *"Aaj kya due hai?"* and *"NovaCart-chan
  me kitne open hain?"* both went to `paisa_report`. Two changes, and both were
  needed: `work_report`, the twenty-sixth tool — the ceiling raised on purpose
  (`spec/agent-tools.md`) — and a `[work]` line in every turn's context, beside
  `[paisa]` and `[diet]`: open, due today, due tomorrow, late, done since
  Monday. The tool alone was not enough; with money and food the only things
  the turn mentioned, the model kept reaching for money. The same line tells
  it that *kal* is tomorrow for a due date and yesterday for something that
  happened.

- **The Work card hid every undated task** — its list showed dated tasks
  only, its week and month bars counted only tasks due in them — so tasks said
  in chat never appeared. The rule was the prototype's; it is revised in
  `frontend/README.md` § Kaam: an undated or late open task is on the plate
  now.
- **The same task said twice is one task.** Pasting a reply back into the
  composer added three tasks a second time. `save_task` returns the open task
  with the same title in the same project, and its card says *already on the
  list*.
- **A yes looped.** Told *"haan bana do"*, the model retried `save_task`, read
  "ask whether to create it" in the refusal and asked again. The refusal now
  names the step for each answer — `if_they_said_yes: call manage_project
  first` — and the prompt says not to ask twice.
- **A task is found across languages and projects.** *"Kestrel wala 3 recipes
  dikhane ka task"* names *"By default we should show 3 recipes"*: a word that
  names a project narrows the search to it, and when no title holds every word
  the one sharing the most — at least two, and clearly ahead — is the task.
- **Words match as words.** Running the suite twenty times caught a test
  failing one run in five: the word *"3"* was matched as a substring, so it
  found every title with a 3 anywhere in it — *ACM-123*, a date — and tied.
  A short word now has to equal a word in the title; from four letters a
  prefix counts, so *recipe* still finds *recipes*.
