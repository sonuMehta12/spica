"""
Projects — what the routes, the agent and the work sync share.
spec/done/projects.md.

A task always has a project. Where it lands is one rule, used by chat, the
routine and the API alike, stopping at the first step that answers:

1. the person named it — by id, name or alias;
2. the source names it — a Linear project, by its alias `linear:<name>`;
3. its nature — the model's call, marked `project_guessed`;
4. nowhere clearly — the default project.

Steps 1, 2 and 4 are lookups and live here. Step 3 is judgement, and it rides
the call already being made — the chat turn or the routine's run — which then
names the project it chose, as step 1 would.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import new_id
from app.models.work import Project, Task

#: A new project's colour, from the app's own palette — stored on the row, so
#: it is the same on every device (spec/done/work-data-model.md).
#:
#: The Work hue's family (THEME.md § Colour): OKLCH hue 230–255, stepped by
#: lightness and chroma, every one a mark at 3 : 1 or better on white and at
#: least 80° of hue from Jamun (335). It was the pre-Jamun greens and ambers,
#: and amber is the estimate dot's alone. Ordered so neighbours differ.
#:   #286CAB L .52 C .12 H 250 · 5.5 : 1      #3A95CD L .64 C .12 H 240 · 3.3
#:   #285388 L .44 C .10 H 255 · 7.8          #1785AF L .58 C .11 H 230 · 4.2
#:   #6588B6 L .62 C .08 H 255 · 3.7          #2E6386 L .48 C .08 H 240 · 6.5
#:   #5E93CA L .65 C .10 H 250 · 3.2
PALETTE = ("#286CAB", "#3A95CD", "#285388", "#1785AF", "#6588B6", "#2E6386", "#5E93CA")
#: The palette before Jamun, position for position — the migration that moved
#: existing projects reads it.
OLD_PALETTE = ("#16604A", "#C98A16", "#A6412E", "#8A5E0B", "#1D7A5E", "#5A6158", "#7A8578")
DEFAULT_NAME = "Personal"
DEFAULT_KEY = "personal"
#: The default project's neutral: `faint`, leaning to Jamun, 4.9 : 1 on white.
GREY = "#747073"

#: The named icons the app ships, Notion-style, beside any emoji. The frontend
#: draws them (`ProjectIcon.tsx`); the server only checks the name exists.
ICONS = frozenset({
    "briefcase", "code", "home", "heart", "book", "cart", "rocket", "star",
    "bolt", "leaf", "chat", "money", "globe", "tool", "person", "flag",
})


def now() -> datetime:
    return datetime.now(UTC)


def valid_icon(icon: str | None) -> bool:
    """An emoji — a short run of non-ASCII — or `icon:<name>` from the set."""
    if icon is None:
        return True
    if icon.startswith("icon:"):
        return icon[5:] in ICONS
    return 0 < len(icon) <= 16 and not any(c.isascii() and c.isalnum() for c in icon)


def fold(s: str) -> str:
    """How names and aliases are compared: case and outer space ignored."""
    return " ".join(s.split()).casefold()


def clean_aliases(aliases: list[str] | None) -> list[str]:
    out: list[str] = []
    for a in aliases or []:
        a = " ".join((a or "").split())
        if a and fold(a) not in {fold(x) for x in out}:
            out.append(a)
    return out


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-") or "project"


async def unique_key(session: AsyncSession, user: str, name: str) -> str:
    """A key from the name, suffixed until no project of theirs holds it —
    deleted ones included, since the unique constraint covers them."""
    base = slug(name)
    taken = set((await session.scalars(select(Project.key).where(
        Project.user_id == user, Project.key.like(f"{base}%")))).all())
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


async def next_colour(session: AsyncSession, user: str) -> str:
    used = set((await session.scalars(select(Project.color).where(
        Project.user_id == user, Project.deleted_at.is_(None)))).all())
    return next((c for c in PALETTE if c not in used), PALETTE[len(used) % len(PALETTE)])


async def default_project(session: AsyncSession, user: str) -> Project:
    """Theirs, made the first time a task needs it. Every task has a project."""
    row = await session.scalar(select(Project).where(
        Project.user_id == user, Project.is_default.is_(True), Project.deleted_at.is_(None)))
    if row is not None:
        return row
    row = Project(id=new_id(), user_id=user, key=await unique_key(session, user, DEFAULT_KEY),
                  name=DEFAULT_NAME, color=GREY, is_default=True)
    session.add(row)
    await session.flush()
    return row


async def live(session: AsyncSession, user: str) -> list[Project]:
    return list((await session.scalars(select(Project).where(
        Project.user_id == user, Project.deleted_at.is_(None)
    ).order_by(Project.archived_at.is_not(None), Project.name))).all())


async def find(session: AsyncSession, user: str, ref: str) -> list[Project]:
    """Every live project `ref` could mean — its id, its name, or an alias.

    One match is an answer; none is *no such project*; two is a question for
    the person. An exact id wins outright; a project not archived is preferred
    over one that is, so an old name does not shadow a current one.
    """
    ref = (ref or "").strip()
    if not ref:
        return []
    rows = await live(session, user)
    by_id = [p for p in rows if p.id == ref]
    if by_id:
        return by_id
    f = fold(ref)
    hits = [p for p in rows if fold(p.name) == f or f in {fold(a) for a in p.aliases}
            or fold(p.key) == f]
    current = [p for p in hits if p.archived_at is None]
    return current or hits


async def by_alias(session: AsyncSession, user: str, alias: str) -> Project | None:
    f = fold(alias)
    for p in await live(session, user):
        if f in {fold(a) for a in p.aliases}:
            return p
    return None


async def claim(session: AsyncSession, user: str, project: Project,
                aliases: list[str]) -> list[dict]:
    """Give `project` these aliases. An alias belongs to one project, so one
    another project held moves here — and the move is reported, so whoever
    asked can say so."""
    moved: list[dict] = []
    wanted = clean_aliases(aliases)
    folded = {fold(a) for a in wanted}
    for other in await live(session, user):
        if other.id == project.id:
            continue
        keep = [a for a in other.aliases if fold(a) not in folded]
        if len(keep) != len(other.aliases):
            for a in other.aliases:
                if fold(a) in folded:
                    moved.append({"alias": a, "from": other.name})
            other.aliases = keep
    project.aliases = clean_aliases([*project.aliases, *wanted])
    return moved


async def make_default(session: AsyncSession, user: str, project: Project) -> None:
    """Exactly one default: marking this one unmarks the old, in the same flush
    order the partial unique index needs."""
    old = await session.scalar(select(Project).where(
        Project.user_id == user, Project.is_default.is_(True),
        Project.deleted_at.is_(None), Project.id != project.id))
    if old is not None:
        old.is_default = False
        await session.flush()
    project.is_default = True
    project.archived_at = None


async def open_counts(session: AsyncSession, user: str) -> dict[str, int]:
    rows = (await session.execute(select(Task.project_id, func.count()).where(
        Task.user_id == user, Task.deleted_at.is_(None), Task.archived_at.is_(None),
        Task.status != "done").group_by(Task.project_id))).all()
    return {pid: n for pid, n in rows}


async def recent_titles(session: AsyncSession, user: str, per: int = 3) -> dict[str, list[str]]:
    """A few of each project's newest live tasks — what the model reads to place
    a task that names no project. A task the person moved sits in the right
    project here, so a correction teaches without being stored as one."""
    rows = (await session.execute(select(Task.project_id, Task.title).where(
        Task.user_id == user, Task.deleted_at.is_(None), Task.archived_at.is_(None),
        Task.project_id.is_not(None)
    ).order_by(Task.updated_at.desc()).limit(per * 40))).all()
    out: dict[str, list[str]] = {}
    for pid, title in rows:
        bucket = out.setdefault(pid, [])
        if len(bucket) < per:
            bucket.append(title)
    return out
