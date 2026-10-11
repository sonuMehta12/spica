"""
Work sync — what the routine asks, and what it writes. spec/work-sync.md.

A Claude cloud routine reads Linear and Wispr Flow through the connectors the
person already has, and writes the difference here through the four tools in
`app/mcp_server.py`. These are those tools' bodies, kept free of MCP so the
tests can call them straight.

Spica never talks to Linear or Wispr. It sorts sources by **shape**, not by
name, so a new source changes no line here:

- a **tracker item** (a Linear issue) keeps changing after it is first seen,
  so it is re-read every run and matched on `(source, source_key)`;
- a **document** (a meeting) never changes, so it is read once and its id is
  kept in `source_documents`.

The model's only judgement is whether a new document item is the same as an
open task. It never creates an id: it names one from the list `begin` gave it,
and the server checks it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import projects as P
from app.models.base import new_id
from app.models.chat import Message
from app.models.users import User
from app.models.work import Project, SourceDocument, Task

log = logging.getLogger(__name__)

SKILLS = Path(__file__).parent / "agent" / "skills" / "work-sync"
#: Who wrote the run's turn in the thread — and how the next run finds it.
MODEL = "routine:work-sync"

#: Placement is one rule, shared with chat — spec/done/projects.md.
PALETTE = P.PALETTE

#: How many open tasks `begin` hands over. The comparison needs all of them;
#: this is a ceiling against a runaway list, not a sample.
OPEN_CAP = 500


def now() -> datetime:
    return datetime.now(UTC)


def _iso(v: datetime | date | None) -> str | None:
    return v.isoformat() if v is not None else None


# ─── the instructions ────────────────────────────────────────────────────────

def instructions() -> str:
    """The static half: the run's steps, then every source's file.

    Read at call time, never cached: an edit to a file is live on the next run
    without a restart, which is the whole point of the server serving them.
    """
    parts = [(SKILLS / "README.md").read_text()]
    for f in sorted(SKILLS.glob("*.md")):
        if f.name != "README.md":
            parts.append(f.read_text())
    return "\n\n---\n\n".join(parts)


# ─── begin ───────────────────────────────────────────────────────────────────

def _open_task(t: Task) -> dict:
    return {
        "id": t.id, "title": t.title, "status": t.status, "source": t.source,
        "source_ref": t.source_ref, "project_id": t.project_id,
        "due": _iso(t.due), "priority": t.priority,
    }


async def to_move(session: AsyncSession, user: str) -> list[Task]:
    """Done here, stage unchanged there: the reminders still showing.

    The same condition as `Task.awaiting_move`, in SQL, so the list and the
    mark on Kaam cannot disagree."""
    return list((await session.scalars(select(Task).where(
        Task.user_id == user, Task.deleted_at.is_(None), Task.archived_at.is_(None),
        Task.source_key.is_not(None), Task.status == "done",
        Task.source_status.not_in(("done", "dropped")),
        (Task.source_state_at.is_(None)) | (Task.status_at.is_(None))
        | (Task.source_state_at < Task.status_at),
    ).order_by(Task.status_at))).all())


async def begin(session: AsyncSession, user: str) -> dict[str, Any]:
    """Everything the routine needs, in one call: how to run, and what is
    already known. Built from rows now, never stored."""
    person = await session.get(User, user)
    tz = ZoneInfo(person.timezone or "Asia/Kolkata")

    open_tasks = (await session.scalars(select(Task).where(
        Task.user_id == user, Task.deleted_at.is_(None), Task.archived_at.is_(None),
        Task.status != "done",
    ).order_by(Task.due.nulls_last(), Task.created_at).limit(OPEN_CAP))).all()

    waiting = await to_move(session, user)

    await P.default_project(session, user)
    projects = [p for p in await P.live(session, user) if p.archived_at is None]
    recent = await P.recent_titles(session, user)
    # Which ref prefixes each project's tracker tasks carry — `BUN` from
    # `ACM-121` — so a new issue lands where the last ones from that team did,
    # without a mapping table anyone has to keep.
    prefixes: dict[str, dict[str, list[str]]] = {}
    for pid, source, prefix in (await session.execute(text("""
        SELECT DISTINCT project_id, source, split_part(source_ref, '-', 1)
        FROM tasks
        WHERE user_id = :u AND project_id IS NOT NULL AND source_key IS NOT NULL
          AND source_ref ~ '^[A-Za-z][A-Za-z0-9]*-[0-9]+$'
    """), {"u": user})).all():
        prefixes.setdefault(pid, {}).setdefault(source, []).append(prefix)

    last = await session.scalar(select(func.max(Message.created_at)).where(
        Message.user_id == user, Message.model == MODEL))

    return {
        "instructions": instructions(),
        "you": {"name": person.display_name, "timezone": str(tz)},
        "today": datetime.now(tz).date().isoformat(),
        "open_tasks": [_open_task(t) for t in open_tasks],
        "to_move": [{
            "id": t.id, "title": t.title, "source": t.source, "source_ref": t.source_ref,
            "doc_ref": t.doc_ref, "source_state": t.source_state,
            "status_at": _iso(t.status_at),
        } for t in waiting],
        # What placement reads: the description, the names it goes by
        # elsewhere, and a few of its tasks — spec/done/projects.md.
        "projects": [{
            "id": p.id, "key": p.key, "name": p.name, "description": p.description,
            "aliases": list(p.aliases), "is_default": p.is_default,
            "recent_tasks": recent.get(p.id, []),
            "ref_prefixes": prefixes.get(p.id, {}),
        } for p in projects],
        "last_run": _iso(last),
    }


# ─── sources_unseen ──────────────────────────────────────────────────────────

async def sources_unseen(session: AsyncSession, user: str, source: str,
                         refs: list[str]) -> list[str]:
    """The refs this source has not been read for. Order kept, repeats dropped
    — the routine walks the answer in the order it asked."""
    wanted = list(dict.fromkeys(r for r in refs if r))
    if not wanted:
        return []
    seen = set((await session.scalars(select(SourceDocument.ref).where(
        SourceDocument.user_id == user, SourceDocument.source == source,
        SourceDocument.deleted_at.is_(None), SourceDocument.ref.in_(wanted)))).all())
    return [r for r in wanted if r not in seen]


# ─── tasks_upsert ────────────────────────────────────────────────────────────

class NewProject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(description="Stable key, e.g. 'linear:BUN'. Same key, same project.")
    name: str = Field(description="What the person sees.")


class TaskItem(BaseModel):
    """One task as the routine sends it. Types only: the rules between fields
    are checked per item in `_check`, so one bad item comes back with its
    reason and the rest still land."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="The task, as the person would write it.")
    source: str = Field(description="Free text: 'linear', 'wispr'.")
    source_ref: str | None = Field(
        None, description="Human pointer: 'ACM-121', or the meeting's id.")
    source_key: str | None = Field(
        None, description="Tracker items only: the source's own stable id (Linear's uuid).")
    source_status: Literal["open", "done", "dropped"] | None = Field(
        None, description="Tracker items only: which bucket the item's stage is in.")
    source_state: str | None = Field(
        None, description="Tracker items only: the stage's own name, 'In Progress'.")
    same_as: str | None = Field(
        None, description="Documents only: the id of an open task this item already is.")
    project_id: str | None = Field(None, description="An id from `projects`.")
    source_project: str | None = Field(
        None, description="The source's own project as an alias, 'linear:Kestrel'. "
                          "Resolved first; recorded on project_id when both are sent.")
    project_guessed: bool = Field(
        False, description="True when project_id is your call from the task's nature.")
    new_project: NewProject | None = None
    due: date | None = None
    priority: int | None = Field(None, description="1 most urgent … 3 least.")
    doc_ref: str | None = Field(None, description="Where the detail lives — the issue URL.")
    blocked_by: str | None = None


def _check(item: TaskItem) -> str | None:
    """The rules between fields. A string is the reason the item was refused."""
    if not item.title.strip():
        return "title is empty"
    if not item.source.strip():
        return "source is empty"
    if item.priority is not None and not 1 <= item.priority <= 3:
        return "priority is 1, 2 or 3"
    if item.source_key:
        if item.same_as:
            return "same_as is for documents; a tracker item is matched by its source_key"
        if item.source_status is None:
            return "a tracker item needs source_status"
    elif item.source_status or item.source_state:
        return "source_status and source_state belong to tracker items, which carry source_key"
    if item.project_id and item.new_project:
        return "give project_id or new_project, not both"
    return None


@dataclass
class _Outcome:
    result: str                 # created · updated · unchanged · matched · skipped · rejected
    id: str | None = None
    reason: str | None = None

    def out(self, index: int) -> dict:
        d = {"index": index, "result": self.result, "id": self.id}
        if self.reason:
            d["reason"] = self.reason
        return d


async def _project(session: AsyncSession, user: str,
                   item: TaskItem) -> tuple[str, bool]:
    """Where the item lands, and whether that was a guess — the placement rule
    of spec/done/projects.md, in its order.

    1. `project_id` — the routine chose one; recorded under `source_project`
       as an alias, so the next run finds it without choosing again.
    2. `source_project` — the source's own project, by alias.
    3. `new_project` — a project the source has and the person does not yet;
       it carries `source_project` as its alias.
    4. The default project.
    """
    if item.project_id:
        found = await session.scalar(select(Project).where(
            Project.id == item.project_id, Project.user_id == user,
            Project.deleted_at.is_(None)))
        if found is None:
            raise LookupError("project_id is not one of this person's projects")
        if item.source_project:
            await P.claim(session, user, found, [item.source_project])
        return found.id, bool(item.project_guessed) and not item.source_project \
            and not found.is_default
    if item.source_project:
        found = await P.by_alias(session, user, item.source_project)
        if found is not None:
            return found.id, False
    if item.new_project:
        key = item.new_project.key.strip()
        found = await session.scalar(select(Project).where(
            Project.user_id == user, Project.key == key))
        if found is not None and found.deleted_at is None:
            if item.source_project:
                await P.claim(session, user, found, [item.source_project])
            return found.id, False
        if found is None:
            row = Project(user_id=user, key=key,
                          name=item.new_project.name.strip() or key,
                          color=await P.next_colour(session, user), aliases=[])
            session.add(row)
            await session.flush()
            await P.claim(session, user, row, [item.source_project or key])
            return row.id, False
        # A project the person deleted stays deleted: the task goes home.
    return (await P.default_project(session, user)).id, False


FIELDS = ("title", "due", "priority", "doc_ref", "blocked_by", "source_ref")
#: What the tracker owns outright. Mirrored on every pull, absence included:
#: a due date removed in Linear is removed here, not kept as a stale promise.
MIRRORED = ("due", "priority", "blocked_by")


def _pull_status(row: Task, incoming: str, at: datetime) -> None:
    """Where the tracker's bucket moves Spica's own status.

    Spica's tick stands unless the tracker says something only it can know:
    finished, dropped, or sent back from finished. A stage that merely has not
    moved yet never undoes a tick — ticking here before moving it there is the
    normal order, not a conflict.
    """
    before = row.source_status
    if incoming == "done":
        if row.status != "done":
            row.status, row.done_at, row.done_by, row.status_at = "done", at, "mcp", at
    elif incoming == "dropped":
        # Canceled, a duplicate, back in the backlog, or given to someone else.
        if row.archived_at is None:
            row.archived_at = at
    else:  # open
        if before == "dropped" and row.archived_at is not None:
            # Back on their plate — reassigned, or out of the backlog.
            row.archived_at = None
        if before == "done" and row.status == "done":
            # From a completed-type stage back to a started one: a reviewer
            # sent it back. The one reopen that can be told from a move
            # forward without knowing the team's order.
            row.status, row.done_at, row.done_by, row.status_at = "open", None, None, at


async def _tracker(session: AsyncSession, user: str, item: TaskItem) -> _Outcome:
    row = await session.scalar(select(Task).where(
        Task.user_id == user, Task.source == item.source, Task.source_key == item.source_key))
    at = now()

    if row is None:
        if item.source_status != "open":
            # Finished or dropped before Spica ever saw it: there is nothing
            # to do, and a task born done is noise on the day it appears.
            return _Outcome("skipped", reason=f"already {item.source_status} in {item.source}")
        project_id, guessed = await _project(session, user, item)
        row = Task(
            id=new_id(), user_id=user, title=item.title.strip(), source=item.source,
            source_ref=item.source_ref, source_key=item.source_key,
            source_status=item.source_status, source_state=item.source_state,
            source_state_at=at, status="open", due=item.due, priority=item.priority,
            doc_ref=item.doc_ref, blocked_by=item.blocked_by, project_id=project_id,
            project_guessed=guessed,
        )
        session.add(row)
        await session.flush()
        return _Outcome("created", row.id)

    if row.deleted_at is not None:
        return _Outcome("skipped", row.id, "deleted in Spica")

    before = {f: getattr(row, f) for f in
              (*FIELDS, "project_id", "status", "archived_at", "source_status", "source_state")}

    for f in FIELDS:
        v = getattr(item, f)
        if f == "title":
            v = v.strip()
        if v is not None or f in MIRRORED:
            setattr(row, f, v)
    if row.project_id is None:
        row.project_id, row.project_guessed = await _project(session, user, item)

    # The stage: a change after the tick is the person having moved it.
    stage_changed = (item.source_state is not None and item.source_state != row.source_state) \
        or item.source_status != row.source_status
    if stage_changed:
        row.source_state = item.source_state if item.source_state is not None else row.source_state
        row.source_state_at = at
    _pull_status(row, item.source_status, at)
    row.source_status = item.source_status

    after = {f: getattr(row, f) for f in before}
    return _Outcome("updated" if after != before else "unchanged", row.id)


async def _document(session: AsyncSession, user: str, item: TaskItem) -> _Outcome:
    if item.same_as:
        found = await session.scalar(select(Task.id).where(
            Task.id == item.same_as, Task.user_id == user, Task.deleted_at.is_(None)))
        if found is None:
            return _Outcome("rejected", reason="same_as names no task of this person's")
        return _Outcome("matched", found)
    project_id, guessed = await _project(session, user, item)
    row = Task(
        id=new_id(), user_id=user, title=item.title.strip(), source=item.source,
        source_ref=item.source_ref, status="open", due=item.due, priority=item.priority,
        doc_ref=item.doc_ref, blocked_by=item.blocked_by, project_id=project_id,
        project_guessed=guessed,
    )
    session.add(row)
    await session.flush()
    return _Outcome("created", row.id)


async def tasks_upsert(session: AsyncSession, user: str,
                       items: list[TaskItem | dict]) -> list[dict]:
    """Write what the routine found. Each item stands alone.

    An unattended run that loses a whole batch to one bad row is worse than one
    that reports the row, so each item runs in its own savepoint and comes back
    with its own result.
    """
    results: list[dict] = []
    for i, raw in enumerate(items):
        try:
            item = raw if isinstance(raw, TaskItem) else TaskItem.model_validate(raw)
        except ValidationError as e:
            results.append(_Outcome("rejected", reason=_why(e)).out(i))
            continue
        reason = _check(item)
        if reason:
            results.append(_Outcome("rejected", reason=reason).out(i))
            continue
        try:
            async with session.begin_nested():
                outcome = await (_tracker if item.source_key else _document)(
                    session, user, item)
                if outcome.result == "rejected":
                    raise _Refused(outcome)
        except _Refused as r:
            outcome = r.outcome
        except LookupError as e:
            outcome = _Outcome("rejected", reason=str(e))
        results.append(outcome.out(i))
    await session.commit()
    return results


class _Refused(Exception):
    """Unwinds an item's savepoint while keeping its outcome."""

    def __init__(self, outcome: _Outcome):
        self.outcome = outcome


def _why(e: ValidationError) -> str:
    first = e.errors()[0]
    where = ".".join(str(p) for p in first.get("loc", ())) or "item"
    return f"{where}: {first.get('msg', 'invalid')}"


# ─── work_sync_finish ────────────────────────────────────────────────────────

class Processed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    ref: str
    title: str | None = Field(None, description="For provenance — 'Standup · 23 Sep'.")
    occurred_at: datetime | None = None
    tasks_created: int = 0


@dataclass(frozen=True)
class _Voice:
    key: str = "work-sync"
    label: str = "Work sync"
    blurb: str = "the morning pass over Linear and meetings"


async def finish(session: AsyncSession, user: str, processed: list[Processed | dict],
                 summary: str, narrated: bool = True) -> dict[str, Any]:
    """Record what was read, and say what the run did in the thread.

    What is still waiting to be moved comes from the rows, not from the
    routine's words — the reminder must not depend on the model remembering it.
    """
    from app.agent.jobs import narrate, post_turn

    recorded = 0
    at = now()
    for raw in processed:
        doc = raw if isinstance(raw, Processed) else Processed.model_validate(raw)
        if not doc.ref.strip():
            continue
        exists = await session.scalar(select(SourceDocument.id).where(
            SourceDocument.user_id == user, SourceDocument.source == doc.source,
            SourceDocument.ref == doc.ref, SourceDocument.deleted_at.is_(None)))
        if exists:
            continue
        session.add(SourceDocument(
            user_id=user, source=doc.source, ref=doc.ref, title=doc.title,
            occurred_at=doc.occurred_at, processed_at=at,
            tasks_created=max(0, doc.tasks_created)))
        recorded += 1
    await session.flush()

    waiting = await to_move(session, user)
    facts = {
        "documents_read": recorded,
        "still_to_move": [f"{t.source_ref or t.title} · {t.source_state or 'unmoved'}"
                          for t in waiting],
    }
    said = (await narrate(_Voice(), summary, facts)) if narrated else \
        f"Work sync: {summary}."
    from app.agent import cards as C
    await post_turn(session, user, said, [C.AgentCard(text=said).model_dump()],
                    [{"routine": "work-sync", "summary": summary, **facts}], MODEL)
    await session.commit()
    return {"recorded": recorded, "still_to_move": len(waiting), "said": said}
