# Source: Linear — a tracker

A Linear issue keeps changing after Spica first sees it, so it is read
**every run**. Spica matches it by its `uuid` — you make no judgement about
duplicates here, and you send every issue you fetch, changed or not. Spica
decides what changed; an unchanged item costs nothing.

## Fetch

Call `list_issues` with `assignee: "me"` three times, paging with `cursor`
until `hasNextPage` is false:

1. `state: "unstarted"`
2. `state: "started"`
3. `updatedAt: "-P14D"` — whatever changed in the last fortnight, which is how
   an issue that was finished, canceled or sent back reaches Spica.

Ask for these `fields`: `uuid`, `title`, `status`, `statusType`, `updatedAt`,
`dueDate`, `priority`, `url`, `team`, `project`. The identifier (`ENG-142`)
comes back as `id`.

Then, for every task in `open_tasks` and `to_move` whose `source` is `linear`
and which none of the three lists returned, call `get_issue` with its
`source_ref`. If it is no longer assigned to the person, it has left their
plate — send it as `dropped`.

## One issue, one item

| Item field | From the issue |
|---|---|
| `source` | `"linear"` |
| `source_key` | `uuid` — never the identifier |
| `source_ref` | the identifier, `ENG-142` |
| `title` | `title` |
| `source_state` | `status` — the stage's own name, whatever the team calls it |
| `source_status` | from `statusType`, below |
| `due` | `dueDate`, if set |
| `priority` | Urgent or High → 1 · Medium → 2 · Low → 3 · No priority → leave it out |
| `doc_ref` | `url` |
| project | the issue's `project`, if it has one, as `source_project: "linear:<project>"` — then the README's § Projects. An issue in no project goes by its nature, never by its team |

| `statusType` | `source_status` |
|---|---|
| `unstarted`, `started` | `open` |
| `completed` | `done` |
| `canceled`, `duplicate`, `backlog`, `triage` | `dropped` |
| no longer assigned to the person | `dropped` |

Map by `statusType`, never by the stage's name: teams name their stages
anything, and a stage called *Testing* can be a completed one. Do not decide
from the names which stage comes next — Spica does not guess that either.

Send completed and dropped issues too. Spica skips one it has never seen and
closes or archives one it has.

## Never

`save_issue`, comments, or any other write. Not even to fix something you are
sure is wrong.
