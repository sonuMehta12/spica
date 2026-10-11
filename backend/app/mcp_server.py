"""
Spica's MCP server — four tools for the work sync, behind OAuth.
spec/work-sync.md § The MCP server.

Mounted into the FastAPI app at the root, so the SDK's own routes sit where
OAuth clients look for them: `/mcp`, `/authorize`, `/token`, `/register`,
`/revoke` and the `/.well-known/…` discovery documents. FastAPI's routes are
matched first; this app answers only what they do not.

**Four tools, and only these.** Every tool is a door into the ledger, and an
unattended cloud routine needs the door to tasks, not to payments. The rest of
the agent's tools reaching Claude is `spec/agent-everywhere.md`, later.

Stateless and JSON, not streamed: every call is one request and one answer,
which is all four tools need and what a proxy in front of Render handles best.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

import app.db as db
from app import work_sync as W
from app.config import settings
from app.oauth import SCOPE, SpicaOAuthProvider, resource_url

INSTRUCTIONS = (
    "Spica is one person's to-do list. Start with work_sync_begin: it returns the "
    "instructions for the work sync and everything Spica already knows. Spica never "
    "writes to Linear or Wispr, and neither should you."
)


def _user() -> str:
    """The person this call acts for — the token's subject, never an argument."""
    token = get_access_token()
    if token is None or not token.subject:
        raise PermissionError("no person behind this token")
    return token.subject


def build() -> MCPServer:
    base = settings().public_url.rstrip("/")
    server = MCPServer(
        name="spica",
        title="Spica",
        instructions=INSTRUCTIONS,
        auth_server_provider=SpicaOAuthProvider(),
        auth=AuthSettings(
            issuer_url=base,
            resource_server_url=resource_url(),
            required_scopes=[SCOPE],
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]),
            revocation_options=RevocationOptions(enabled=True),
            # Every token this server issues is for this server; the verifier
            # stamps the resource itself, so there is no audience to compare.
            validate_token_resource=False,
        ),
    )

    @server.tool(description=(
        "Start here, once per run. Returns the run's instructions and what Spica "
        "already knows: the person, today, open tasks, projects, and the Linear tasks "
        "ticked done in Spica but not yet moved in Linear."))
    async def work_sync_begin() -> dict[str, Any]:
        async with db.SessionLocal() as s:
            return await W.begin(s, _user())

    @server.tool(description=(
        "Which of these document ids (meeting ids) Spica has not read yet. Read only "
        "those."))
    async def sources_unseen(source: str, refs: list[str]) -> dict[str, list[str]]:
        async with db.SessionLocal() as s:
            return {"unseen": await W.sources_unseen(s, _user(), source, refs)}

    @server.tool(description=(
        "Write tasks: tracker items (Linear issues, matched by source_key) and document "
        "items (from meetings — new, or same_as an open task's id). Each item comes "
        "back with its own result; fix and resend only the rejected ones."))
    async def tasks_upsert(tasks: list[W.TaskItem]) -> dict[str, list[dict]]:
        async with db.SessionLocal() as s:
            return {"results": await W.tasks_upsert(s, _user(), tasks)}

    @server.tool(description=(
        "End the run, once: record every document read to the end (including those "
        "that produced no tasks) and leave a one-line summary in Spica's thread."))
    async def work_sync_finish(processed: list[W.Processed], summary: str) -> dict[str, Any]:
        async with db.SessionLocal() as s:
            return await W.finish(s, _user(), processed, summary)

    return server


def transport_security() -> TransportSecuritySettings:
    """DNS-rebinding protection, with this server's own public host allowed.

    The SDK turns it on for localhost by default and then refuses every other
    Host header — which would refuse Render's."""
    host = urlparse(settings().public_url).netloc
    hosts = ["localhost", "127.0.0.1", "localhost:*", "127.0.0.1:*", "[::1]:*"]
    origins = ["http://localhost:*", "http://127.0.0.1:*", "http://[::1]:*"]
    if host and host not in hosts:
        hosts += [host, f"{urlparse(settings().public_url).hostname}:*"]
        origins.append(settings().public_url.rstrip("/"))
    return TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                     allowed_hosts=hosts, allowed_origins=origins)


server = build()
app = server.streamable_http_app(stateless_http=True, json_response=True,
                                 transport_security=transport_security())
