"""
Work. Specs: spec/done/work-data-model.md, spec/work-sync.md.

One level of task, whatever the origin — Linear, a meeting, typed by hand.
Everything is rewritten into this shape at ingestion. Nothing is written back:
a Linear task ticked here is a reminder to move it there (work-sync.md).
"""

from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Envelope


class Project(Envelope, Base):
    """A thing being built. Earned a table the moment it gained facts of its
    own — color, key vs display name, archive — which a text column on tasks
    would repeat until the copies disagreed."""

    __tablename__ = "projects"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    # git remote, normalised; directory name when there is no remote. A repo
    # cloned to a different path is still the same project.
    key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Stored, not assigned at render: a project that changes colour per device
    # stops being recognisable.
    color: Mapped[str] = mapped_column(String(9), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── made by the person (spec/done/projects.md) ────────────────────
    # What it is, in their words. The agent and the routine read it to place a
    # task that names no project — the most useful field on the row.
    description: Mapped[str | None] = mapped_column(Text)
    # An emoji, or `icon:<name>` from the app's own set — the way Notion offers
    # both. NULL draws the first letter in the project's colour. Nothing is
    # uploaded: the app has no file storage, and 12 pixels do not need one.
    icon: Mapped[str | None] = mapped_column(Text)
    # What it is called elsewhere — `linear:Kestrel`, a repo, *novachan*.
    # Matched case-insensitively. It is what turns placement into a lookup.
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False,
                                               server_default="{}")
    # Where everything unplaced lands. One per person, enforced below.
    is_default: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))

    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_projects_user_key"),
    )


class Task(Envelope, Base):
    """Mutable state, not a ledger event — the one exception substrate allows.
    The id is the file marker (<!--cx:a7f2-->), so it is short and assigned by
    whoever creates the task, never regenerated."""

    __tablename__ = "tasks"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # 'pending' and 'open' are the same word said twice; three states, no more.
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="open")
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done_by: Mapped[str | None] = mapped_column(String(8))
    # Out of every view without deleting history. Not done (done is a result),
    # not deleted (it happened) — just no longer worth showing.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    due: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[int | None] = mapped_column(Integer)
    # Labels, not a kind enum: not yet sure diet/paisa tasks belong in the todo
    # at all, and a label costs nothing either way.
    labels: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")

    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    # The model chose the project, not the person or the source — drawn with
    # the amber dot like every inferred value, and cleared the moment the
    # person moves the task or says it is right.
    project_guessed: Mapped[bool] = mapped_column(nullable=False,
                                                  server_default=text("false"))

    # Where it CAME FROM, and the pointer back. Free text like meal_type —
    # new sources will appear, and an enum would refuse them.
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text)   # 'ENG-142', a message id
    # Where the DETAIL lives — the spec/PRD this task is about. Local path or
    # remote URL. NULL for a task that is only a sentence.
    doc_ref: Mapped[str | None] = mapped_column(Text)
    # The dependency, in Linear's and Jira's own word. Free text: the blocker
    # is usually outside the system — a person, another team's feature.
    blocked_by: Mapped[str | None] = mapped_column(Text)

    # Provenance of the task LINE itself, for file-sourced tasks.
    repo: Mapped[str | None] = mapped_column(Text)
    path: Mapped[str | None] = mapped_column(Text)
    line: Mapped[int | None] = mapped_column(Integer)      # display only, never identity

    # ── a tracker's view of this task (spec/work-sync.md) ────────────────────
    # The source's own stable id — Linear's issue UUID, never `ENG-142`, which
    # changes when an issue moves team. Unique per source *including deleted
    # rows*: that is what stops a task deleted here from coming back.
    source_key: Mapped[str | None] = mapped_column(Text)
    # open · done · dropped, as last pulled. Spica knows no team's stages;
    # this is the one bucket the routine sorts a stage into.
    source_status: Mapped[str | None] = mapped_column(String(8))
    # The stage's own name — "Dev in progress". Shown in the reminder,
    # compared on every pull.
    source_state: Mapped[str | None] = mapped_column(Text)
    # When a pull last saw the stage change. Later than the tick means the
    # person moved it, whatever their team calls the stage.
    source_state_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When Spica's status last changed, by anyone. Not `updated_at`: a pull
    # refreshes titles and dates on every run, so that moves regardless.
    status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def tracked(self) -> bool:
        """Came from a tracker — ticking it here means moving it there next."""
        return self.source_key is not None

    @property
    def awaiting_move(self) -> bool:
        """Done here, not yet moved in the tracker: the reminder is showing.

        Derived, never stored — a stored flag would have to be cleared by
        whoever noticed the move, and the pull already notices it."""
        return (
            self.source_key is not None
            and self.status == "done"
            and self.source_status not in ("done", "dropped")
            and (self.source_state_at is None
                 or self.status_at is None
                 or self.source_state_at < self.status_at)
        )

    __table_args__ = (
        CheckConstraint("status IN ('open','doing','done')", name="ck_tasks_status"),
        CheckConstraint("priority IS NULL OR priority BETWEEN 1 AND 3",
                        name="ck_tasks_priority"),
        CheckConstraint("done_by IS NULL OR done_by IN ('phone','file','mcp')",
                        name="ck_tasks_done_by"),
        Index("ix_tasks_user_status", "user_id", "status"),
        Index("ix_tasks_user_due", "user_id", "due"),
        Index("ix_tasks_sync", "user_id", "updated_at", "id"),
        Index("ix_tasks_labels", "labels", postgresql_using="gin"),
        CheckConstraint("source_status IS NULL OR source_status IN ('open','done','dropped')",
                        name="ck_tasks_source_status"),
        # Deleted rows included, deliberately — see `source_key`.
        Index("uq_tasks_user_source_key", "user_id", "source", "source_key", unique=True,
              postgresql_where=text("source_key IS NOT NULL")),
    )


# One default project per person, among live rows.
Index("uq_projects_user_default", Project.user_id, unique=True,
      postgresql_where=text("is_default AND deleted_at IS NULL"))


class SourceDocument(Envelope, Base):
    """An outside document the work sync has read — a meeting, later an email.

    A document never changes once written, so it is read once and never again.
    A task row cannot be that record: a meeting that produced nothing for this
    person leaves no task, and would be re-read every run forever. Soft-deleting
    a row is the one control for reading it again.
    """

    __tablename__ = "source_documents"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)          # 'wispr'
    ref: Mapped[str] = mapped_column(Text, nullable=False)             # the meeting's id
    # What Kaam shows as provenance — "Standup · 23 Sep". Stored once, here.
    title: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tasks_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


# Live rows only: soft-deleting a document is how it becomes unseen again, so
# the fresh read must be able to write a new row beside the old one.
Index("uq_source_documents_user_source_ref", SourceDocument.user_id, SourceDocument.source,
      SourceDocument.ref, unique=True, postgresql_where=SourceDocument.deleted_at.is_(None))
