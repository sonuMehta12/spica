"""Projects the person makes. spec/done/projects.md."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.deck import ProjectOut
from app.schemas.writes import Id, Patch


class ProjectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Id
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)
    #: An emoji, or `icon:<name>` from the app's set.
    icon: str | None = Field(None, max_length=40)
    aliases: list[str] = []
    #: Stored, not assigned at render; the palette picks one when absent.
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_default: bool = False


class ProjectPatch(Patch):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=40)
    #: Replaces the list. An alias another project holds moves here.
    aliases: list[str] | None = None
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    archived: bool | None = None
    #: True makes this the default and unmarks the old one. False on the
    #: default is refused: mark another one instead.
    is_default: bool | None = None


class ProjectRow(ProjectOut):
    """A project as Profile lists it: the row, and what is open in it."""

    archived_at: datetime | None = None
    open_tasks: int = 0
    #: Aliases this write took from another project, so the caller can say so.
    moved_aliases: list[dict] = []
