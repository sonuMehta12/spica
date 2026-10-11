"""OAuth for the MCP endpoint, and a scope on every session

Revision ID: b8d3f1a6c2e5
Revises: a4c2e7f9b1d3
Create Date: 2026-09-27

claude.ai adds a custom connector by OAuth, so Cortex becomes the
authorization server for its own `/mcp` (spec/work-sync.md § Auth).

An access token is a `sessions` row, the same hash-in-a-table sign-in already
uses — which is why `sessions` gains a `scope`. Every existing session is the
app's, so the default `app` is exactly true of them. An `mcp` token opens
`/mcp` and nothing else, and an `app` token is refused there: each door has its
own key.

The OAuth tables hold only what the protocol adds around that token: who
registered, the request-then-code of one approval, and the rotating refresh
token. Secrets are stored as SHA-256 only, as sessions already are.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b8d3f1a6c2e5'
down_revision: str | Sequence[str] | None = 'a4c2e7f9b1d3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('sessions', sa.Column('scope', sa.String(length=8), server_default='app',
                                        nullable=False))
    op.add_column('sessions', sa.Column('client_id', sa.Text(), nullable=True))
    op.create_check_constraint('ck_sessions_scope', 'sessions', "scope IN ('app','mcp')")

    op.create_table(
        'oauth_clients',
        sa.Column('client_id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('info', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.PrimaryKeyConstraint('client_id'),
    )
    op.create_table(
        'oauth_codes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('request_hash', sa.Text(), nullable=False),
        sa.Column('code_hash', sa.Text(), nullable=True),
        sa.Column('client_id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=True),
        sa.Column('redirect_uri', sa.Text(), nullable=False),
        sa.Column('redirect_uri_provided_explicitly', sa.Boolean(), nullable=False),
        sa.Column('code_challenge', sa.Text(), nullable=False),
        sa.Column('state', sa.Text(), nullable=True),
        sa.Column('scopes', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('resource', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['oauth_clients.client_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_hash'),
        sa.UniqueConstraint('request_hash'),
    )
    op.create_table(
        'oauth_refresh_tokens',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('client_id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('scopes', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['oauth_clients.client_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index('ix_oauth_refresh_tokens_user_client', 'oauth_refresh_tokens',
                    ['user_id', 'client_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_oauth_refresh_tokens_user_client', table_name='oauth_refresh_tokens')
    op.drop_table('oauth_refresh_tokens')
    op.drop_table('oauth_codes')
    op.drop_table('oauth_clients')
    op.drop_constraint('ck_sessions_scope', 'sessions', type_='check')
    op.drop_column('sessions', 'client_id')
    op.drop_column('sessions', 'scope')
