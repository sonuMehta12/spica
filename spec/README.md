# spec

What gets built, and why — written **before** the code.

## Layout

```
spec/
├── README.md          this file — the rules
├── notes.md           deferred decisions — what we chose *not* to build, and why
├── _TEMPLATE.md       the shape every feature spec takes
├── <feature>.md       one file per feature, settled but not yet built
├── in-progress/       whatever is being decided right now
├── done/              the feature shipped — this is now why the code is like this
├── archive/           argued and deliberately not built — nothing there is owed
└── reference/         source material — design exports, notes
```

## The rules

**A feature gets a spec file before it gets code.** A page is usually enough. A
decision written down once does not get re-argued three weeks later.

**Specs hold decisions, not conversations.** No questions, no "you asked X", no
answers to review comments. If a discussion produced a decision, the spec records
the decision and its reason — the discussion itself belongs in chat. Anyone
reading a spec cold should find a clean document, not a transcript.

**Write the reason, not just the choice.** A future disagreement should be with
the reason rather than with the person who wrote it. If a section has no reason
worth writing, it probably has no decision in it.

**Record what was decided against.** The rejected option and why is often the
most useful part of the file. It is what stops the same argument happening again.

**Deferred decisions go in `notes.md`.** When something is deliberately not built
yet, write it there: what, why, and what would change our mind. A deferred
decision and an overlooked one look identical six weeks later — and without the
note, someone rebuilds the argument or quietly does the thing we decided against.

**`in-progress/` is for arguing.** A file there is unfinished by definition —
open questions, half-decisions. When it settles it **moves up** to `spec/`.
Ideally one at a time; two means two things are half-built.

**`archive/` is for parked.** A design that was written and then decided against
moves there, with a header pointing at its `notes.md` entry. It is not owed, and
it is not deleted: if the reason to park it goes away, the argument restarts
from the file rather than from memory.

**`done/` is for shipped.** A spec moves there when the thing is built and
verified — not when the writing is finished. The split matters because `spec/`
then answers *what is still owed*, and `done/` answers *why the code is like
this*. Without it a folder of thirty files says nothing about either.

## Naming

Lowercase, hyphenated, named for the thing a person would call it:

```
work-sync.md      paisa-categorise.md      workout.md
```

Not `feature-01.md`. The filename is the index.

## Language

English for identifiers — table names, columns, fields, types. Hinglish belongs
in UI copy and in the data itself, not in the schema.

## The Definition of done is what the tests assert

A backend spec's DoD table is not prose — `backend/tests/test_<spec>.py` turns
each row into a test, so a claim in a spec is checkable. Write the DoD as
things a machine could verify, and say plainly which rows were verified by hand
instead (a browser click, a one-off query) so the gap is visible.
