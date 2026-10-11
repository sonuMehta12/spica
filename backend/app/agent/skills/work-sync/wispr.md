# Source: Wispr Flow — documents

A meeting never changes once recorded, so each one is read **once**. Spica
keeps the ids of the meetings already read; you ask it which are new.

## Fetch

1. `search_meetings` with `since` fourteen days before `today` and `until` now,
   both ISO datetimes with an offset. Page with `cursor` until `has_more` is
   false. Keep every meeting's `id`.
2. `sources_unseen` with `source: "wispr"` and those ids. Read only the ones it
   returns.
3. For each: `get_meeting` with `view_transcript: {}`. The summary's *next
   steps* section holds the action items; the transcript is the source of truth
   for who said they would do what. Page the transcript only when the owner of
   an item is unclear.

A meeting with no notes and no transcript yet is still being processed by
Wispr. Leave it out of `processed`, so it is read on the next run.

## Which items are the person's

Their name is `you.name`.

- **Theirs:** assigned to them by name, or something they said they would do —
  *"I'll send the deck"*, *"main bhej dunga"*. An item for everyone in the room
  is theirs too.
- **Not theirs:** an item someone else took. A decision, an FYI, or a
  question that was answered is not a task at all.

## One item, one task — or `same_as`

Compare each item with `open_tasks` first, by what the work is rather than by
its words: *"send the deck to the client"* and an open *"Deck to client by
Friday"* are the same task. Then:

- **the same work** → an item with `same_as` set to that task's id, and nothing
  else needed;
- **new** → an item with `source: "wispr"`, `source_ref` set to the meeting's
  `id`, a `title`, and `due` if a date was said. Its project follows the
  README's § Projects, step 2: a project whose description plainly fits the
  meeting or the item, with `project_guessed: true`, or none. No
  `source_key`, `source_status` or `source_state` — a meeting is not a tracker.

When unsure, create it.

## Record what you read

For every meeting you read to the end, add to `work_sync_finish`'s `processed`:
`source: "wispr"`, `ref` as the meeting's `id`, `title` as the meeting's title
and day — *Standup · 23 Sep* — `occurred_at` as its start, and
`tasks_created` as how many tasks it produced. **Include meetings that
produced none** — that is what stops them being read again tomorrow.
