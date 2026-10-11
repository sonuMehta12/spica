"""
spec/work-sync.md — the Definition of done, row by row.

The four tools' bodies are called straight (`app.work_sync`), then the same
four through `/mcp` with an OAuth token, the way a Claude routine calls them.
Linear and Wispr are never touched: the routine is the only thing that talks to
them, so these tests play the routine and hand Spica what it would have read.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import work_sync as W
from app.models.work import SourceDocument, Task
from tests.helpers import the_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


def key() -> str:
    """A fresh tracker id — every test owns its issues, whatever ran before."""
    return str(uuid.uuid4())


def issue(k: str, status="open", state="Todo", **over) -> dict:
    """One Linear issue as the routine sends it."""
    body = {"title": "Retry on 429", "source": "linear", "source_key": k,
            "source_ref": "ENG-142", "source_status": status, "source_state": state}
    body.update(over)
    return body


async def fresh(db, task_id: str) -> Task:
    db.expire_all()
    return await db.scalar(select(Task).where(Task.id == task_id))


async def upsert(db, user, *items) -> list[dict]:
    return await W.tasks_upsert(db, user, list(items))


# ─── 1 · 2 — a tracker item is matched by key, deleted rows included ────────

async def test_1_a_keyed_upsert_creates_once_and_the_same_call_writes_nothing(
        client, db_session):
    user = await the_user(db_session)
    k = key()
    [first] = await upsert(db_session, user, issue(k))
    assert first["result"] == "created" and first["id"]
    row = await fresh(db_session, first["id"])
    before = row.updated_at

    [again] = await upsert(db_session, user, issue(k))
    assert again == {"index": 0, "result": "unchanged", "id": first["id"]}
    assert (await fresh(db_session, first["id"])).updated_at == before, "nothing was written"
    count = len((await db_session.scalars(select(Task.id).where(
        Task.user_id == user, Task.source_key == k))).all())
    assert count == 1


async def test_2_a_task_deleted_in_spica_is_skipped_and_never_recreated(client, db_session):
    user = await the_user(db_session)
    k = key()
    [made] = await upsert(db_session, user, issue(k))
    assert (await client.delete(f"/tasks/{made['id']}")).status_code == 204

    [back] = await upsert(db_session, user, issue(k, title="Retry on 429, reworded"))
    assert back["result"] == "skipped" and back["reason"] == "deleted in Spica"
    rows = (await db_session.scalars(select(Task).where(Task.source_key == k))).all()
    assert len(rows) == 1 and rows[0].deleted_at is not None


# ─── 3 · 4 — a tick is a reminder; an unmoved stage never undoes it ─────────

async def test_3_a_tick_waits_in_to_move_until_the_stage_changes(client, db_session):
    user = await the_user(db_session)
    k = key()
    [made] = await upsert(db_session, user, issue(k, state="In Progress"))
    assert (await client.patch(f"/tasks/{made['id']}", json={"status": "done"})).status_code == 200

    waiting = [t["id"] for t in (await W.begin(db_session, user))["to_move"]]
    assert made["id"] in waiting
    deck = (await client.get("/deck?to=2026-09-27")).json()["work"]["tasks"]
    mine = next(t for t in deck if t["id"] == made["id"])
    assert mine["awaiting_move"] is True and mine["source_state"] == "In Progress"

    # The same stage again: still waiting.
    await upsert(db_session, user, issue(k, state="In Progress"))
    assert made["id"] in [t["id"] for t in (await W.begin(db_session, user))["to_move"]]

    # They moved it. Whatever the team calls the stage, a change clears it.
    [moved] = await upsert(db_session, user, issue(k, state="Dev complete"))
    assert moved["result"] == "updated"
    assert made["id"] not in [t["id"] for t in (await W.begin(db_session, user))["to_move"]]
    row = await fresh(db_session, made["id"])
    assert row.status == "done" and row.awaiting_move is False


async def test_4_a_pull_with_an_unchanged_stage_never_undoes_a_tick(client, db_session):
    user = await the_user(db_session)
    k = key()
    [made] = await upsert(db_session, user, issue(k, state="In Progress"))
    await client.patch(f"/tasks/{made['id']}", json={"status": "done"})
    for _ in range(3):
        await upsert(db_session, user, issue(k, state="In Progress"))
    assert (await fresh(db_session, made["id"])).status == "done"


# ─── 5 · 5a — finished, dropped, and sent back ──────────────────────────────

async def test_5_a_completed_stage_sets_done_and_dropped_archives(client, db_session):
    user = await the_user(db_session)
    k1, k2 = key(), key()
    [a] = await upsert(db_session, user, issue(k1))
    [b] = await upsert(db_session, user, issue(k2, source_ref="ENG-143"))

    await upsert(db_session, user, issue(k1, status="done", state="Testing"))
    row = await fresh(db_session, a["id"])
    assert row.status == "done" and row.done_by == "mcp" and row.done_at is not None
    assert row.awaiting_move is False, "finished there — nothing to remind"

    await upsert(db_session, user, issue(k2, status="dropped", state="Canceled",
                                         source_ref="ENG-143"))
    row = await fresh(db_session, b["id"])
    assert row.archived_at is not None and row.status == "open", "archived, not done"

    # Back on their plate: reassigned, or out of the backlog.
    await upsert(db_session, user, issue(k2, state="Todo", source_ref="ENG-143"))
    assert (await fresh(db_session, b["id"])).archived_at is None


async def test_5a_completed_back_to_started_reopens_but_started_to_started_does_not(
        client, db_session):
    user = await the_user(db_session)
    k1, k2 = key(), key()
    [a] = await upsert(db_session, user, issue(k1, state="In Progress"))
    await upsert(db_session, user, issue(k1, status="done", state="Testing"))
    [back] = await upsert(db_session, user, issue(k1, state="In Progress"))
    assert back["result"] == "updated"
    row = await fresh(db_session, a["id"])
    assert row.status == "open" and row.done_at is None, "a reviewer sent it back"

    # Two started stages look the same as a move forward: the tick stands.
    [b] = await upsert(db_session, user, issue(k2, state="Dev in progress"))
    await client.patch(f"/tasks/{b['id']}", json={"status": "done"})
    await upsert(db_session, user, issue(k2, state="Dev complete"))
    await upsert(db_session, user, issue(k2, state="Dev in progress"))
    row = await fresh(db_session, b["id"])
    assert row.status == "done" and row.source_state == "Dev in progress"


async def test_a_tracker_item_finished_before_spica_saw_it_is_not_created(
        client, db_session):
    user = await the_user(db_session)
    k = key()
    [done] = await upsert(db_session, user, issue(k, status="done", state="Done"))
    [gone] = await upsert(db_session, user, issue(key(), status="dropped", state="Canceled"))
    assert done["result"] == "skipped" and gone["result"] == "skipped"
    assert await db_session.scalar(select(Task.id).where(Task.source_key == k)) is None


# ─── 6 — refreshing fields moves neither clock ──────────────────────────────

async def test_6_a_refresh_of_title_or_due_moves_neither_status_at_nor_stage_at(
        client, db_session):
    user = await the_user(db_session)
    k = key()
    [made] = await upsert(db_session, user, issue(k, state="In Progress"))
    await client.patch(f"/tasks/{made['id']}", json={"status": "done"})
    row = await fresh(db_session, made["id"])
    ticked, staged = row.status_at, row.source_state_at

    [out] = await upsert(db_session, user, issue(k, state="In Progress",
                                                 title="Retry on 429 and 503", due="2026-10-02"))
    assert out["result"] == "updated"
    row = await fresh(db_session, made["id"])
    assert row.title == "Retry on 429 and 503" and str(row.due) == "2026-10-02"
    assert row.status_at == ticked and row.source_state_at == staged
    assert row.awaiting_move is True, "a refresh is not a move"


# ─── 7 — same_as is checked, and writes nothing ─────────────────────────────

async def test_7_same_as_must_name_one_of_their_tasks_and_writes_nothing(client, db_session):
    user = await the_user(db_session)
    [made] = await upsert(db_session, user, {
        "title": "Send the deck to the client", "source": "wispr", "source_ref": "m-" + key()})
    assert made["result"] == "created"
    before = await db_session.scalar(select(Task.updated_at).where(Task.id == made["id"]))

    [ok, bad] = await upsert(
        db_session, user,
        {"title": "Deck to client", "source": "wispr", "same_as": made["id"]},
        {"title": "Deck to client", "source": "wispr", "same_as": "01NOSUCHTASK00000000000000"})
    assert ok == {"index": 0, "result": "matched", "id": made["id"]}
    assert bad["result"] == "rejected" and "same_as" in bad["reason"]
    db_session.expire_all()
    assert await db_session.scalar(
        select(Task.updated_at).where(Task.id == made["id"])) == before


async def test_one_bad_item_does_not_sink_the_batch(client, db_session):
    user = await the_user(db_session)
    k = key()
    out = await upsert(
        db_session, user,
        issue(k),
        {"title": "x", "source": "linear", "source_key": key()},          # no source_status
        {"title": "x", "source": "wispr", "priority": 7},                  # out of range
        {"title": "x", "source": "wispr", "source_status": "open"},        # tracker field on a doc
        {"title": "x", "source": "linear", "source_key": key(), "source_status": "open",
         "same_as": "01X"},                                                # same_as on a tracker
        {"title": "x", "source": "wispr", "nonsense": 1},                  # unknown field
        {"title": "   ", "source": "wispr"},                               # empty title
    )
    assert out[0]["result"] == "created"
    assert [o["result"] for o in out[1:]] == ["rejected"] * 6
    assert all(o["reason"] for o in out[1:])


async def test_a_new_project_is_made_once_with_a_palette_colour(client, db_session):
    user = await the_user(db_session)
    pkey = "linear:T" + key()[:6]
    [a, b] = await upsert(
        db_session, user,
        issue(key(), new_project={"key": pkey, "name": "Test team"}),
        issue(key(), source_ref="ENG-9", new_project={"key": pkey, "name": "Test team"}))
    pa = (await fresh(db_session, a["id"])).project_id
    pb = (await fresh(db_session, b["id"])).project_id
    assert pa == pb is not None
    projects = {p["key"]: p for p in (await W.begin(db_session, user))["projects"]}
    assert projects[pkey]["name"] == "Test team"
    assert projects[pkey]["ref_prefixes"] == {"linear": ["ENG"]}
    color = (await client.get("/deck?to=2026-09-27")).json()["work"]["projects"]
    assert next(p for p in color if p["key"] == pkey)["color"] in W.PALETTE


# ─── 8 — documents are read once ────────────────────────────────────────────

async def test_8_a_recorded_document_is_never_unseen_until_its_row_is_deleted(
        client, db_session):
    user = await the_user(db_session)
    m1, m2, m3 = ("m-" + key() for _ in range(3))
    assert await W.sources_unseen(db_session, user, "wispr", [m1, m2, m1, m3]) == [m1, m2, m3]

    await W.finish(db_session, user, [
        {"source": "wispr", "ref": m1, "title": "Standup · 23 Sep", "tasks_created": 2},
        {"source": "wispr", "ref": m2, "title": "1:1 · 24 Sep", "tasks_created": 0},
    ], summary="2 meetings read", narrated=False)
    assert await W.sources_unseen(db_session, user, "wispr", [m1, m2, m3]) == [m3], \
        "a meeting that produced nothing is recorded too"
    assert await W.sources_unseen(db_session, user, "gmail", [m1]) == [m1], "per source"

    row = await db_session.scalar(select(SourceDocument).where(SourceDocument.ref == m2))
    row.deleted_at = datetime.now(UTC)
    await db_session.commit()
    assert await W.sources_unseen(db_session, user, "wispr", [m2]) == [m2], "read it again"


async def test_a_meeting_task_shows_the_meeting_title_on_the_deck(client, db_session):
    user = await the_user(db_session)
    ref = "m-" + key()
    [made] = await upsert(db_session, user, {
        "title": "Share the pricing sheet", "source": "wispr", "source_ref": ref})
    await W.finish(db_session, user, [{"source": "wispr", "ref": ref,
                                       "title": "Pricing sync · 25 Sep", "tasks_created": 1}],
                   summary="1 meeting", narrated=False)
    deck = (await client.get("/deck?to=2026-09-27")).json()["work"]["tasks"]
    assert next(t for t in deck if t["id"] == made["id"])["source_title"] == \
        "Pricing sync · 25 Sep"


# ─── 9 — one agent turn, no user message ────────────────────────────────────

async def test_9_finish_writes_one_agent_turn_and_names_what_waits(client, db_session, fake):
    from app.models.chat import Message
    from tests.helpers import _msg

    user = await the_user(db_session)
    k = key()
    [made] = await upsert(db_session, user, issue(k, state="In Progress",
                                                  source_ref="ENG-777"))
    await client.patch(f"/tasks/{made['id']}", json={"status": "done"})
    fake(_msg("Work sync: 1 new from Linear. ENG-777 is done here, still to move."))

    count = select(Message.id).where(Message.user_id == user)
    before = len((await db_session.scalars(count)).all())
    out = await W.finish(db_session, user, [], summary="1 task from Linear")
    db_session.expire_all()
    rows = (await db_session.scalars(
        select(Message).where(Message.user_id == user).order_by(Message.seq))).all()
    assert len(rows) == before + 1, "one turn, and no user message before it"
    turn = rows[-1]
    assert turn.role == "agent" and turn.model == W.MODEL
    assert "ENG-777 · In Progress" in turn.tool_trace[0]["still_to_move"], \
        "the reminder list comes from the rows, not the routine's words"
    assert out["still_to_move"] >= 1
    assert (await W.begin(db_session, user))["last_run"] is not None


# ─── 13 — the person's tick is stamped ──────────────────────────────────────

async def test_13_patching_a_status_stamps_status_at_and_a_title_does_not(client, db_session):
    from tests.helpers import ulid
    made = (await client.post("/tasks", json={"id": ulid(), "title": "Book the venue",
                                              "source": "self"})).json()
    row = await fresh(db_session, made["id"])
    created = row.status_at
    assert created is not None

    await client.patch(f"/tasks/{made['id']}", json={"title": "Book the hall"})
    assert (await fresh(db_session, made["id"])).status_at == created
    await client.patch(f"/tasks/{made['id']}", json={"status": "done"})
    row = await fresh(db_session, made["id"])
    assert row.status_at > created and row.done_by == "phone"


# ─── 14 — the instructions carry nothing about this person ──────────────────

async def test_14_the_static_instructions_hold_no_names_from_the_ledger(client, db_session):
    text = W.instructions()
    assert text.startswith("# You run Spica's work sync")
    assert "# Source: Linear" in text and "# Source: Wispr Flow" in text
    # The live Linear workspace and projects, and the person — never in the file.
    for name in ("ACM-", "Acme", "acme", "novacart", "kestrel", "Sonu"):
        assert name not in text, name
    begun = await W.begin(db_session, await the_user(db_session))
    assert begun["instructions"] == text and "today" in begun and "you" in begun


# ─── begin's shape ───────────────────────────────────────────────────────────

async def test_begin_lists_open_tasks_and_leaves_out_done_and_archived(client, db_session):
    user = await the_user(db_session)
    k1, k2, k3 = key(), key(), key()
    [a] = await upsert(db_session, user, issue(k1))
    [b] = await upsert(db_session, user, issue(k2, source_ref="ENG-2"))
    [c] = await upsert(db_session, user, issue(k3, source_ref="ENG-3"))
    await client.patch(f"/tasks/{b['id']}", json={"status": "done"})
    await client.patch(f"/tasks/{c['id']}", json={"archived": True})
    ids = {t["id"] for t in (await W.begin(db_session, user))["open_tasks"]}
    assert a["id"] in ids and b["id"] not in ids and c["id"] not in ids


async def test_a_task_ticked_before_its_first_pull_still_reminds(client, db_session):
    """Ticked here, then moved there before the routine ran: the reminder shows
    until the next pull sees the new stage, and clears then."""
    user = await the_user(db_session)
    k = key()
    [made] = await upsert(db_session, user, issue(k, state="In Progress"))
    await client.patch(f"/tasks/{made['id']}", json={"status": "done"})
    row = await fresh(db_session, made["id"])
    row.source_state_at = row.status_at - timedelta(seconds=1)
    await db_session.commit()
    assert (await fresh(db_session, made["id"])).awaiting_move is True
    await upsert(db_session, user, issue(k, state="Dev complete"))
    assert (await fresh(db_session, made["id"])).awaiting_move is False


# ═══ the same tools over /mcp, with an OAuth token ══════════════════════════

import base64  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import secrets  # noqa: E402
from contextlib import AsyncExitStack  # noqa: E402
from urllib.parse import parse_qs, urlparse  # noqa: E402

import pytest_asyncio  # noqa: E402

REDIRECT = "http://localhost:9999/callback"
BASE = "http://localhost:8001"
_running: AsyncExitStack | None = None


@pytest_asyncio.fixture(loop_scope="session")
async def mcp(client):
    """An unauthenticated client for the MCP server and the SDK's OAuth routes.

    The ASGI transport runs no lifespan, and the session manager can be started
    once per process — so it is started here, once, and left running. The base
    URL is the server's own public URL, which the DNS-rebinding check expects.
    """
    global _running
    from httpx import ASGITransport, AsyncClient

    from app import mcp_server
    from app.main import app
    if _running is None:
        _running = AsyncExitStack()
        await _running.enter_async_context(mcp_server.server.session_manager.run())
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        yield c


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


async def _register(mcp, name="Test routine") -> str:
    r = await mcp.post("/register", json={
        "client_name": name, "redirect_uris": [REDIRECT],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]})
    assert r.status_code == 201, r.text
    return r.json()["client_id"]


async def _authorize(mcp, client_id: str) -> tuple[str, str]:
    """The browser leg: /authorize parks the request and sends it to the app."""
    verifier, challenge = _pkce()
    r = await mcp.get("/authorize", params={
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
        "code_challenge": challenge, "code_challenge_method": "S256",
        "state": "st-1", "scope": "tasks", "resource": f"{BASE}/mcp"})
    assert r.status_code == 302, r.text
    where = urlparse(r.headers["location"])
    assert where.path == "/connect", "sent to the app to ask"
    return parse_qs(where.query)["request"][0], verifier


async def _grant(mcp, client) -> dict:
    """Register, ask, approve as the signed-in person, and swap the code."""
    client_id = await _register(mcp)
    request, verifier = await _authorize(mcp, client_id)
    shown = (await client.get(f"/oauth/requests/{request}")).json()
    assert shown["client_name"] == "Test routine" and shown["redirect_host"] == "localhost:9999"
    back = urlparse((await client.post(f"/oauth/requests/{request}/approve")).json()["redirect"])
    q = parse_qs(back.query)
    assert q["state"] == ["st-1"]
    r = await mcp.post("/token", data={
        "grant_type": "authorization_code", "code": q["code"][0], "redirect_uri": REDIRECT,
        "client_id": client_id, "code_verifier": verifier})
    assert r.status_code == 200, r.text
    return {**r.json(), "client_id": client_id, "code": q["code"][0], "verifier": verifier}


H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
     "MCP-Protocol-Version": "2025-06-18"}


async def rpc(mcp, token: str | None, method: str, params: dict | None = None):
    headers = dict(H)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return await mcp.post("/mcp", headers=headers, json={
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})


async def call(mcp, token: str, tool: str, **arguments) -> dict:
    r = await rpc(mcp, token, "tools/call", {"name": tool, "arguments": arguments})
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result["isError"] is False, result
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


# ─── 10 — four tools, and only four ─────────────────────────────────────────

async def test_10_tools_list_is_exactly_the_four(client, mcp):
    token = (await _grant(mcp, client))["access_token"]
    r = await rpc(mcp, token, "tools/list")
    names = sorted(t["name"] for t in r.json()["result"]["tools"])
    assert names == ["sources_unseen", "tasks_upsert", "work_sync_begin", "work_sync_finish"]


# ─── 11 — the OAuth dance ───────────────────────────────────────────────────

async def test_11_no_token_is_a_401_that_names_the_resource_metadata(client, mcp):
    r = await rpc(mcp, None, "tools/list")
    assert r.status_code == 401
    assert "/.well-known/oauth-protected-resource/mcp" in r.headers["www-authenticate"]

    meta = (await mcp.get("/.well-known/oauth-protected-resource/mcp")).json()
    assert meta["resource"] == f"{BASE}/mcp"
    assert meta["authorization_servers"] == [BASE]
    auth = (await mcp.get("/.well-known/oauth-authorization-server")).json()
    for k in ("authorization_endpoint", "token_endpoint", "registration_endpoint"):
        assert auth[k].startswith(BASE), k
    assert auth["code_challenge_methods_supported"] == ["S256"]


async def test_11_register_authorize_approve_token_call_and_refresh(client, mcp, db_session):
    grant = await _grant(mcp, client)
    begun = await call(mcp, grant["access_token"], "work_sync_begin")
    assert begun["instructions"].startswith("# You run Spica's work sync")

    # The code works once.
    again = await mcp.post("/token", data={
        "grant_type": "authorization_code", "code": grant["code"], "redirect_uri": REDIRECT,
        "client_id": grant["client_id"], "code_verifier": grant["verifier"]})
    assert again.status_code == 400 and again.json()["error"] == "invalid_grant"

    # Refresh rotates both; the old refresh token is spent.
    fresh = await mcp.post("/token", data={
        "grant_type": "refresh_token", "refresh_token": grant["refresh_token"],
        "client_id": grant["client_id"]})
    assert fresh.status_code == 200, fresh.text
    new = fresh.json()
    assert new["refresh_token"] != grant["refresh_token"]
    assert (await call(mcp, new["access_token"], "work_sync_begin"))["today"]
    spent = await mcp.post("/token", data={
        "grant_type": "refresh_token", "refresh_token": grant["refresh_token"],
        "client_id": grant["client_id"]})
    assert spent.status_code == 400

    # Secrets are stored as hashes only.
    from app.models.users import Session
    rows = (await db_session.scalars(select(Session.token_hash).where(
        Session.client_id == grant["client_id"]))).all()
    assert rows and new["access_token"] not in rows


async def test_11_a_wrong_pkce_verifier_gets_no_token(client, mcp):
    client_id = await _register(mcp)
    request, _ = await _authorize(mcp, client_id)
    back = (await client.post(f"/oauth/requests/{request}/approve")).json()["redirect"]
    code = parse_qs(urlparse(back).query)["code"][0]
    r = await mcp.post("/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
        "client_id": client_id, "code_verifier": secrets.token_urlsafe(48)})
    assert r.status_code == 400


async def test_denying_sends_access_denied_and_the_request_cannot_then_be_approved(
        client, mcp):
    client_id = await _register(mcp)
    request, _ = await _authorize(mcp, client_id)
    back = (await client.post(f"/oauth/requests/{request}/deny")).json()["redirect"]
    q = parse_qs(urlparse(back).query)
    assert q["error"] == ["access_denied"] and q["state"] == ["st-1"]
    assert (await client.post(f"/oauth/requests/{request}/approve")).status_code == 404
    assert (await client.get("/oauth/requests/not-a-real-request")).status_code == 404


async def test_approving_needs_the_signed_in_person(client, mcp, anon):
    client_id = await _register(mcp)
    request, _ = await _authorize(mcp, client_id)
    assert (await anon.get(f"/oauth/requests/{request}")).status_code == 401
    assert (await anon.post(f"/oauth/requests/{request}/approve")).status_code == 401


async def test_revoking_ends_access(client, mcp):
    grant = await _grant(mcp, client)
    # The SDK's revocation form wants the `client_secret` key even from a
    # public client, which has none — so it is sent empty.
    r = await mcp.post("/revoke", data={"token": grant["access_token"],
                                        "client_id": grant["client_id"], "client_secret": ""})
    assert r.status_code == 200, r.text
    assert (await rpc(mcp, grant["access_token"], "tools/list")).status_code == 401
    refreshed = await mcp.post("/token", data={
        "grant_type": "refresh_token", "refresh_token": grant["refresh_token"],
        "client_id": grant["client_id"]})
    assert refreshed.status_code == 400, "the pair goes together"


# ─── 12 — each door refuses the other's key ─────────────────────────────────

async def test_12_an_mcp_token_is_refused_by_rest_and_an_app_token_by_mcp(client, mcp, anon):
    from tests.conftest import TEST_TOKEN
    token = (await _grant(mcp, client))["access_token"]
    rest = await anon.get("/deck?to=2026-09-27", headers={"Authorization": f"Bearer {token}"})
    assert rest.status_code == 401, "a routine token must not read payments"
    assert (await rpc(mcp, TEST_TOKEN, "tools/list")).status_code == 401


# ─── the whole loop over the wire ───────────────────────────────────────────

async def test_a_run_over_mcp_writes_tasks_and_one_turn(client, mcp, db_session, fake):
    from tests.helpers import _msg
    token = (await _grant(mcp, client))["access_token"]
    k, ref = key(), "m-" + key()

    begun = await call(mcp, token, "work_sync_begin")
    assert set(begun) >= {"instructions", "you", "today", "open_tasks", "to_move", "projects"}
    assert (await call(mcp, token, "sources_unseen", source="wispr", refs=[ref])) == \
        {"unseen": [ref]}
    out = await call(mcp, token, "tasks_upsert", tasks=[
        issue(k, state="In Progress", source_ref="ENG-900"),
        {"title": "Share the notes", "source": "wispr", "source_ref": ref},
        {"title": "x", "source": "wispr", "priority": 9},
    ])
    assert [r["result"] for r in out["results"]] == ["created", "created", "rejected"]

    fake(_msg("Work sync: 1 from Linear, 1 from a meeting."))
    done = await call(mcp, token, "work_sync_finish", summary="1 from Linear, 1 from a meeting",
                      processed=[{"source": "wispr", "ref": ref, "title": "Sync · 27 Sep",
                                  "tasks_created": 1}])
    assert done["recorded"] == 1
    assert (await call(mcp, token, "sources_unseen", source="wispr", refs=[ref])) == \
        {"unseen": []}


async def test_a_confidential_client_with_a_secret_completes_the_flow(client, mcp):
    """claude.ai may register with a secret rather than as a public client;
    the SDK defaults an unstated method to `client_secret_post`."""
    r = await mcp.post("/register", json={"client_name": "Claude", "redirect_uris": [REDIRECT],
                                          "grant_types": ["authorization_code", "refresh_token"],
                                          "response_types": ["code"]})
    reg = r.json()
    assert reg["client_secret"] and reg["token_endpoint_auth_method"] == "client_secret_post"
    request, verifier = await _authorize(mcp, reg["client_id"])
    back = (await client.post(f"/oauth/requests/{request}/approve")).json()["redirect"]
    code = parse_qs(urlparse(back).query)["code"][0]
    base = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
            "client_id": reg["client_id"], "code_verifier": verifier}
    assert (await mcp.post("/token", data=base)).status_code == 401, "no secret, no token"
    ok = await mcp.post("/token", data={**base, "client_secret": reg["client_secret"]})
    assert ok.status_code == 200, ok.text
    assert (await call(mcp, ok.json()["access_token"], "work_sync_begin"))["you"]


async def test_a_deleted_project_is_not_brought_back_by_its_key(client, db_session):
    from app.models.work import Project
    user = await the_user(db_session)
    pkey = "linear:Gone" + key()[:6]
    [a] = await upsert(db_session, user, issue(key(), new_project={"key": pkey, "name": "Gone"}))
    pid = (await fresh(db_session, a["id"])).project_id
    row = await db_session.scalar(select(Project).where(Project.id == pid))
    row.deleted_at = datetime.now(UTC)
    await db_session.commit()
    [b] = await upsert(db_session, user, issue(key(), new_project={"key": pkey, "name": "Gone"}))
    assert b["result"] == "created"
    landed = (await fresh(db_session, b["id"])).project_id
    home = await db_session.scalar(select(Project.id).where(
        Project.user_id == user, Project.is_default.is_(True), Project.deleted_at.is_(None)))
    assert landed == home, "not brought back — the task goes to the default project"


# ─── edges ───────────────────────────────────────────────────────────────────

async def test_another_persons_tasks_and_keys_are_invisible(client, db_session):
    """The token's subject is the person; one person's tracker key is not
    another's, and one person's tasks never reach another's routine."""
    from app.models.base import new_id
    from app.models.users import User
    me = await the_user(db_session)
    other = User(id=new_id(), display_name="Someone else")
    db_session.add(other)
    await db_session.commit()
    k = key()
    [theirs] = await upsert(db_session, other.id, issue(k, title="Their task"))
    [mine] = await upsert(db_session, me, issue(k, title="My task"))
    assert mine["result"] == "created" and mine["id"] != theirs["id"], "same key, two people"
    ids = {t["id"] for t in (await W.begin(db_session, me))["open_tasks"]}
    assert theirs["id"] not in ids and mine["id"] in ids
    [cross] = await upsert(db_session, me, {"title": "x", "source": "wispr",
                                            "same_as": theirs["id"]})
    assert cross["result"] == "rejected"


async def test_an_expired_access_token_is_refused_and_removed(client, mcp, db_session):
    from app.auth import hash_token
    from app.models.users import Session
    token = (await _grant(mcp, client))["access_token"]
    row = await db_session.scalar(select(Session).where(Session.token_hash == hash_token(token)))
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    assert (await rpc(mcp, token, "tools/list")).status_code == 401
    db_session.expire_all()
    assert await db_session.scalar(
        select(Session.id).where(Session.token_hash == hash_token(token))) is None


async def test_an_expired_consent_request_is_gone(client, mcp, db_session):
    from app.auth import hash_token
    from app.models.oauth import OAuthCode
    request, _ = await _authorize(mcp, await _register(mcp))
    row = await db_session.scalar(select(OAuthCode).where(
        OAuthCode.request_hash == hash_token(request)))
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    assert (await client.get(f"/oauth/requests/{request}")).status_code == 404
    assert (await client.post(f"/oauth/requests/{request}/approve")).status_code == 404


async def test_a_malformed_call_is_an_error_the_routine_can_read(client, mcp):
    token = (await _grant(mcp, client))["access_token"]
    r = await rpc(mcp, token, "tools/call",
                  {"name": "tasks_upsert", "arguments": {"tasks": "not a list"}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["isError"] is True and result["content"][0]["text"]


async def test_a_due_date_removed_in_the_tracker_is_removed_here(client, db_session):
    """The tracker owns due, priority and blockers: absence is mirrored too."""
    user = await the_user(db_session)
    k = key()
    [made] = await upsert(db_session, user, issue(k, due="2026-10-05", priority=1,
                                                  blocked_by="ENG-1"))
    row = await fresh(db_session, made["id"])
    assert str(row.due) == "2026-10-05" and row.priority == 1
    [out] = await upsert(db_session, user, issue(k))
    assert out["result"] == "updated"
    row = await fresh(db_session, made["id"])
    assert row.due is None and row.priority is None and row.blocked_by is None
