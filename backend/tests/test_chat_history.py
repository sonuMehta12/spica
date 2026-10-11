"""spec/done/chat-history.md — paging the thread, and clearing the view.

The thread is deliberately permanent, so the client cannot keep rendering all
of it: 172 messages and ~50 KB after two weeks. These assert the `seq` cursor,
and that *clear* hides and compacts without deleting anything.
"""

import pytest
import pytest_asyncio

from tests.helpers import _msg

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def restore_marker(db_session):
    """Clearing is sticky by design. Put it back so the files that run after
    this one still see the thread they wrote."""
    from sqlalchemy import select

    from app.models.chat import Conversation
    yield
    db_session.expire_all()
    convo = await db_session.scalar(select(Conversation).where(
        Conversation.deleted_at.is_(None)))
    if convo:
        convo.cleared_through_seq = 0
        await db_session.commit()


async def turns(client, fake, n, prefix="page"):
    llm = fake(*[_msg(f"a{i}") for i in range(n + 2)])
    for i in range(n):
        await client.post("/chat", json={"message": f"{prefix} {i}",
                                         "local_day": "2026-08-20"})
    return llm


# ─── paging ──────────────────────────────────────────────────────────────────

async def test_a_page_is_the_newest_n_and_says_whether_more_sits_behind(client, fake):
    await turns(client, fake, 6)
    body = (await client.get("/chat", params={"limit": 4})).json()
    assert len(body["messages"]) == 4
    assert body["has_more"] is True
    # Oldest last is wrong for a chat: the page reads top to bottom.
    seqs = [m["seq"] for m in body["messages"]]
    assert seqs == sorted(seqs), "a page must come back oldest first"


async def test_the_cursor_walks_back_without_gap_or_overlap(client, fake):
    await turns(client, fake, 6, "walk")
    first = (await client.get("/chat", params={"limit": 4})).json()
    oldest = first["messages"][0]["seq"]
    second = (await client.get("/chat", params={"limit": 4, "before": oldest})).json()
    a = [m["seq"] for m in first["messages"]]
    b = [m["seq"] for m in second["messages"]]
    assert not set(a) & set(b), "pages overlap"
    assert max(b) == min(a) - 1, "a message fell between two pages"


async def test_a_page_that_covers_its_scope_says_there_is_no_more(client, fake):
    """Bounded to the first two messages ever written, so the assertion does
    not depend on how long the shared thread has grown."""
    await turns(client, fake, 2, "tail")
    body = (await client.get("/chat", params={"limit": 500, "before": 3,
                                              "include_cleared": True})).json()
    assert [m["seq"] for m in body["messages"]] == [1, 2]
    assert body["has_more"] is False


async def test_a_page_is_capped_server_side(client):
    assert (await client.get("/chat", params={"limit": 501})).status_code == 422
    assert (await client.get("/chat", params={"limit": 0})).status_code == 422


# ─── clear ───────────────────────────────────────────────────────────────────

async def test_clear_hides_everything_but_the_last_message(client, fake, restore_marker):
    await turns(client, fake, 4, "clearme")
    before = (await client.get("/chat", params={"limit": 500})).json()["messages"]
    assert len(before) > 1

    out = (await client.post("/chat/clear")).json()
    assert len(out["messages"]) == 1
    assert out["messages"][0]["seq"] == before[-1]["seq"], "the newest must survive"
    assert out["cleared_through_seq"] == before[-2]["seq"]
    # And the default read agrees.
    assert len((await client.get("/chat", params={"limit": 500})).json()["messages"]) == 1


async def test_clear_deletes_nothing_and_show_brings_it_back(client, fake, restore_marker):
    await turns(client, fake, 4, "keepme")
    everything = (await client.get("/chat", params={"limit": 500})).json()["messages"]
    await client.post("/chat/clear")

    back = (await client.get("/chat", params={"limit": 500,
                                              "include_cleared": True})).json()
    assert len(back["messages"]) == len(everything), "clear must not delete"
    assert [m["seq"] for m in back["messages"]] == [m["seq"] for m in everything]


async def test_clear_compacts_so_the_agent_keeps_the_gist(client, fake, restore_marker):
    """A clean screen beside an agent still quoting what you cleared reads as
    broken. Clearing folds; the words go, the gist stays."""
    from sqlalchemy import select

    from app.models.chat import Conversation, Message
    await turns(client, fake, 4, "gist")
    out = (await client.post("/chat/clear")).json()
    assert out["summary"], "clearing must leave a summary behind"

    # The model's own window is now empty: everything is in the summary.
    from app.db import SessionLocal
    async with SessionLocal() as s:
        convo = await s.scalar(select(Conversation).where(
            Conversation.deleted_at.is_(None)))
        left = list((await s.scalars(select(Message.seq).where(
            Message.conversation_id == convo.id,
            Message.deleted_at.is_(None),
            Message.seq > convo.summary_through_seq))).all())
    assert len(left) <= 1, f"{len(left)} messages still verbatim in the window"


async def test_a_turn_after_a_clear_is_visible(client, fake, restore_marker):
    await turns(client, fake, 4, "after")
    await client.post("/chat/clear")
    fake(_msg("naya jawab"))
    await client.post("/chat", json={"message": "naya sawaal", "local_day": "2026-08-20"})
    shown = (await client.get("/chat", params={"limit": 500})).json()["messages"]
    assert [m["text"] for m in shown][-2:] == ["naya sawaal", "naya jawab"]


async def test_clearing_a_one_message_thread_does_nothing(client, fake, restore_marker):
    await turns(client, fake, 4, "noop")
    await client.post("/chat/clear")
    marker = (await client.get("/chat")).json()["cleared_through_seq"]
    again = (await client.post("/chat/clear")).json()
    assert again["cleared_through_seq"] == marker, "clearing twice moved the marker"
    assert len(again["messages"]) == 1


async def test_a_failed_summariser_still_clears_the_screen(client, fake, monkeypatch,
                                                           restore_marker):
    """Hiding is the user's request. It must not depend on a model being up."""
    from app.agent import runner as R
    await turns(client, fake, 4, "broken")

    async def boom(*a, **kw):
        raise TimeoutError("summariser is down")

    monkeypatch.setattr(R, "_summarise", boom)
    out = (await client.post("/chat/clear")).json()
    assert len(out["messages"]) == 1
    assert out["cleared_through_seq"] > 0
