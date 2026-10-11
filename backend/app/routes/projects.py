"""
Projects the person makes. spec/done/projects.md.

The shape every library here has — list, create with a client ULID, patch,
soft delete — plus the two rules only projects carry: there is always exactly
one default, and deleting a project never takes its tasks with it.
"""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import update

from app import projects as P
from app.auth import CurrentUser
from app.db import SessionDep
from app.models.work import Project, Task
from app.routes.writes import existing, live_or_404, now
from app.schemas.projects import ProjectIn, ProjectPatch, ProjectRow

router = APIRouter(tags=["projects"])


def _bad_icon() -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                         "icon is an emoji, or icon:<name> from the app's set")


async def _row(session, user: str, p: Project, moved: list[dict] | None = None) -> ProjectRow:
    counts = await P.open_counts(session, user)
    out = ProjectRow.model_validate(p)
    out.open_tasks = counts.get(p.id, 0)
    out.moved_aliases = moved or []
    return out


@router.get("/projects")
async def list_projects(session: SessionDep, user: CurrentUser) -> list[ProjectRow]:
    """Every live project, archived ones last. The default is made here if the
    person has none yet, so the list is never missing the one that must exist."""
    await P.default_project(session, user)
    await session.commit()
    counts = await P.open_counts(session, user)
    rows = []
    for p in await P.live(session, user):
        r = ProjectRow.model_validate(p)
        r.open_tasks = counts.get(p.id, 0)
        rows.append(r)
    return rows


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectIn, session: SessionDep, user: CurrentUser,
                         response: Response) -> ProjectRow:
    found = await existing(session, Project, body.id, user)
    if found is not None:
        response.status_code = status.HTTP_200_OK
        return await _row(session, user, found)
    if not P.valid_icon(body.icon):
        raise _bad_icon()
    row = Project(id=body.id, user_id=user, key=await P.unique_key(session, user, body.name),
                  name=body.name.strip(), description=(body.description or None),
                  icon=body.icon, aliases=[],
                  color=body.color or await P.next_colour(session, user))
    session.add(row)
    await session.flush()
    moved = await P.claim(session, user, row, body.aliases)
    if body.is_default:
        await P.make_default(session, user, row)
    await session.commit()
    return await _row(session, user, row, moved)


@router.patch("/projects/{row_id}")
async def patch_project(row_id: str, body: ProjectPatch, session: SessionDep,
                        user: CurrentUser) -> ProjectRow:
    row = await live_or_404(session, Project, row_id, user)
    changes = body.model_dump(exclude_unset=True)
    if "icon" in changes and not P.valid_icon(changes["icon"]):
        raise _bad_icon()
    if row.is_default and changes.get("archived"):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "the default project cannot be archived — mark another one "
                            "default first")
    if row.is_default and changes.get("is_default") is False:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "there is always one default — mark another project instead")

    if changes.get("name"):
        row.name = changes["name"].strip()
    if "description" in changes:
        row.description = (changes["description"] or "").strip() or None
    if "icon" in changes:
        row.icon = changes["icon"] or None
    if changes.get("color"):
        row.color = changes["color"]
    moved: list[dict] = []
    if "aliases" in changes:
        row.aliases = []
        moved = await P.claim(session, user, row, changes["aliases"] or [])
    if "archived" in changes:
        row.archived_at = now() if changes["archived"] else None
    if changes.get("is_default"):
        await P.make_default(session, user, row)
    await session.commit()
    await session.refresh(row)
    return await _row(session, user, row, moved)


@router.delete("/projects/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(row_id: str, session: SessionDep, user: CurrentUser) -> None:
    """Soft, and its tasks move to the default project — a delete never takes
    the work with it."""
    row = await live_or_404(session, Project, row_id, user)
    if row.is_default:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "the default project cannot be deleted — mark another one "
                            "default first")
    home = await P.default_project(session, user)
    await session.execute(update(Task).where(
        Task.user_id == user, Task.project_id == row.id).values(
        project_id=home.id, project_guessed=False))
    row.deleted_at = now()
    await session.commit()
