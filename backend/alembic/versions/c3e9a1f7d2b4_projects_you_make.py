"""Projects you make: a description, an icon, aliases, and one default

Revision ID: c3e9a1f7d2b4
Revises: b8d3f1a6c2e5
Create Date: 2026-09-27

Projects existed and nobody could make one (spec/done/projects.md).
They gain what a person gives them — a description the agent reads to place a
task, an icon, the names the project goes by elsewhere — and one of them
becomes the **default**, where every task that fits nowhere else lands.

Every person gets a default named *Personal* here, and every task that had no
project moves into it: from this revision on, a task always has a project. A
person whose key `personal` is already taken keeps that project and has it
marked default instead, so no key collides.

`tasks.project_guessed` is false for every existing row: nothing placed them
by guessing, because nothing placed them at all.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from ulid import ULID

revision: str = 'c3e9a1f7d2b4'
down_revision: str | Sequence[str] | None = 'b8d3f1a6c2e5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The app's grey — a default project should not look like a work one.
GREY = "#7A8578"


def upgrade() -> None:
    op.add_column('projects', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('icon', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('aliases', postgresql.ARRAY(sa.Text()),
                                        server_default='{}', nullable=False))
    op.add_column('projects', sa.Column('is_default', sa.Boolean(),
                                        server_default=sa.text('false'), nullable=False))
    op.create_index('uq_projects_user_default', 'projects', ['user_id'], unique=True,
                    postgresql_where=sa.text('is_default AND deleted_at IS NULL'))
    op.add_column('tasks', sa.Column('project_guessed', sa.Boolean(),
                                     server_default=sa.text('false'), nullable=False))

    conn = op.get_bind()
    for (user_id,) in conn.execute(sa.text("SELECT id FROM users")).all():
        taken = conn.execute(sa.text(
            "SELECT id FROM projects WHERE user_id = :u AND key = 'personal'"),
            {"u": user_id}).scalar()
        if taken:
            conn.execute(sa.text(
                "UPDATE projects SET is_default = true, deleted_at = NULL, archived_at = NULL "
                "WHERE id = :p"), {"p": taken})
            default_id = taken
        else:
            default_id = str(ULID())
            conn.execute(sa.text(
                "INSERT INTO projects (id, user_id, key, name, color, is_default, "
                "created_at, updated_at) VALUES (:p, :u, 'personal', 'Personal', :c, true, "
                "now(), now())"), {"p": default_id, "u": user_id, "c": GREY})
        conn.execute(sa.text(
            "UPDATE tasks SET project_id = :p WHERE user_id = :u AND project_id IS NULL"),
            {"p": default_id, "u": user_id})


def downgrade() -> None:
    op.drop_column('tasks', 'project_guessed')
    op.drop_index('uq_projects_user_default', table_name='projects',
                  postgresql_where=sa.text('is_default AND deleted_at IS NULL'))
    for col in ('is_default', 'aliases', 'icon', 'description'):
        op.drop_column('projects', col)
