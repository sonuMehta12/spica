"""sign-in: identity on users, and a sessions table

The users table has held the person since 4b1c9e7d2a10; this gives it an
identity to prove. `google_sub` is the identity — Google's own guidance is that
`sub` is unique and never reused, while an account's email can change — and
`email` is a label kept fresh on every sign-in.

`sessions` is deliberately not an Envelope: a session is not the user's data,
and deleting it outright is the entire revocation story.

spec/in-progress/sign-in.md

Revision ID: e1a9c7d4f302
Revises: b82e4f19c7a3
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'e1a9c7d4f302'
down_revision: str | Sequence[str] | None = 'b82e4f19c7a3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('google_sub', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'users', sa.Column('onboarding_done_at', sa.DateTime(timezone=True), nullable=True)
    )
    # Unique but nullable: rows that predate sign-in have neither, and many
    # NULLs do not collide in Postgres.
    op.create_unique_constraint('uq_users_email', 'users', ['email'])
    op.create_unique_constraint('uq_users_google_sub', 'users', ['google_sub'])

    op.create_table(
        'sessions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.Text(), sa.ForeignKey('users.id'), nullable=False),
        # The raw token is returned once and never stored. A database dump
        # therefore cannot be replayed as a login.
        sa.Column('token_hash', sa.Text(), nullable=False, unique=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_sessions_user', 'sessions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_sessions_user', table_name='sessions')
    op.drop_table('sessions')
    op.drop_constraint('uq_users_google_sub', 'users', type_='unique')
    op.drop_constraint('uq_users_email', 'users', type_='unique')
    for col in ('onboarding_done_at', 'last_seen_at', 'avatar_url', 'google_sub', 'email'):
        op.drop_column('users', col)
