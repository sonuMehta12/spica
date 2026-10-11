"""spec/agent.md and spec/agent-tools.md — the agent.

The model is mocked throughout. What is worth testing is *ours*: that the tool
registry is well formed, that the ladder resolves and refuses honestly, that
the runner runs what the model asked for and persists the turn, and that the
window and the rolling summary behave. Whether the model picks the right tool
is a question for a live eval, not a unit test.
"""

import pytest

from tests.helpers import _msg, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ─── the registry ────────────────────────────────────────────────────────────

async def test_every_tool_has_a_name_a_purpose_and_a_schema(client):
    from app.agent import tools as T
    assert len(T.TOOLS) == len({t["name"] for t in T.TOOLS}), "duplicate tool name"
    for t in T.TOOLS:
        assert t["description"].strip(), f"{t['name']} has no purpose line"
        s = t["schema"]
        assert s["type"] == "object" and "properties" in s
        assert set(s["required"]) <= set(s["properties"]), f"{t['name']}: required not in props"
    # Fewer tools are chosen more reliably. The ceiling is a decision, not a
    # law: 25 from spec/agent-tools.md, raised to 26 on 2026-09-27 for
    # work_report — the agent could not read a task at all. Raise it the same
    # way: on purpose, with the reason recorded there.
    assert len(T.TOOLS) <= 27


async def test_an_unknown_tool_is_data_not_a_crash(client, db_session):
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)
    assert "error" in await T.run(db_session, user, "drop_everything", {})


async def test_a_route_refusal_comes_back_as_data(client, db_session):
    """The model reads the reason and tells the user; it never sees a 500."""
    from app.agent import tools as T
    from tests.helpers import the_user
    user = await the_user(db_session)
    out = await T.run(db_session, user, "log_payment", {
        "amount_paise": 100, "direction": "debit", "kind": "lent",
        "category": "Udhaar", "description": "kisko?", "local_day": "2026-08-20"})
    assert "counterparty" in out["error"] and out["status"] == 422


# ─── the ladder ──────────────────────────────────────────────────────────────

async def _resolve(db_session, said):
    from app.agent.ladder import resolve
    from tests.helpers import the_user
    return await resolve(db_session, await the_user(db_session), said)


async def test_the_ladder_climbs_exact_then_alias(client, db_session, library):
    lines = await _resolve(db_session, "Whey shake aur protein shake")
    assert [x["rung"] for x in lines] == ["exact", "alias"]
    assert all(x["dish_id"] == "t-dish-whey" for x in lines)


async def test_a_typo_still_matches_by_similarity(client, db_session, library):
    """The trigram rung: "whey shakee" is the same drink."""
    line = (await _resolve(db_session, "whey shakee"))[0]
    assert line["matched"] and line["rung"] == "similar"


async def test_an_unmatched_item_stays_unresolved(client, db_session, library):
    """Matching never creates a dish, and never guesses one either."""
    lines = await _resolve(db_session, f"zzq{ulid()[-6:]} khaya")
    assert lines and not lines[0]["matched"] and lines[0]["dish_id"] is None


async def test_a_spoken_measure_becomes_grams(client, db_session, library):
    """`measures` exists because "1 katori dal" is a food and a unit."""
    line = (await _resolve(db_session, "2 katori dal"))[0]
    assert line["food_id"] == "t-food-dal" and line["quantity"] == 300   # 2 × 150g


async def test_a_food_sold_in_pieces_takes_the_count(client, db_session, library):
    line = (await _resolve(db_session, "3 ande"))[0]
    assert line["food_id"] == "t-food-egg" and line["quantity"] == 3


async def test_a_count_on_a_gram_food_refuses_to_invent_a_weight(client, db_session, library):
    """"2 roti" is not two grams of atta, and forty would be a number the user
    never said. The line asks instead."""
    line = (await _resolve(db_session, "2 roti"))[0]
    assert line["matched"] and line["quantity"] is None and line["needs_quantity"]


# ─── the turn ────────────────────────────────────────────────────────────────

async def test_a_read_turn_runs_the_tool_and_answers(client, fake):
    fake(_msg(calls=[("paisa_report", {"to": "2026-08-20", "fields": ["spent"]})]),
         _msg("₹0 kharcha hua"))
    r = await client.post("/chat", json={"message": "kitna kharcha?",
                                         "local_day": "2026-08-20"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "₹0 kharcha hua"
    assert body["cards"][0]["kind"] == "agent"


async def test_the_prompt_carries_the_memories_and_the_rules(client, fake):
    llm = fake(_msg("ok"))
    await client.post("/chat", json={"message": "hi", "local_day": "2026-08-20"})
    system = llm.sent[0]["instructions"]
    assert "## Who they are" in system and "## Rules" in system
    # today() is not a tool — it would be a round-trip for a fact that cannot
    # change mid-turn.
    assert "today" not in {t["name"] for t in llm.sent[0]["tools"]}


async def test_nothing_that_changes_per_turn_sits_in_the_cached_prefix(client, fake):
    """The layout rule, as a test. A provider's cache matches a prefix and
    stops at the first difference, so a date near the front of the system
    prompt re-bills every static token behind it — and the tool schemas are
    the biggest of those. spec/done/prompt-layout.md."""
    llm = fake(_msg("ok"))
    await client.post("/chat", json={"message": "hi", "local_day": "2026-08-20",
                                     "local_time": "18:42:00"})
    system = llm.sent[0]["instructions"]
    for volatile in ("2026-08-20", "Thursday", "18:42", "days left", "[now]"):
        assert volatile not in system, f"{volatile!r} must not be in the cached prefix"

    # It rides on the turn instead, after everything fixed.
    last = llm.sent[0]["input"][-1]
    assert last["role"] == "user"
    assert "2026-08-20" in last["content"] and "Thursday" in last["content"]
    assert "18:42" in last["content"] and last["content"].endswith("hi")


async def test_the_now_block_is_never_stored_or_replayed(client, fake):
    """Replayed three turns later it would be a stale number — the same reason
    tool results are not replayed."""
    fake(_msg("one"))
    await client.post("/chat", json={"message": "pehla", "local_day": "2026-08-20",
                                     "local_time": "09:00:00"})
    said = [m["text"] for m in (await client.get("/chat")).json()["messages"]
            if m["role"] == "user"]
    assert said[-1] == "pehla", "the stored turn must be what they said, nothing prepended"

    llm = fake(_msg("two"))
    await client.post("/chat", json={"message": "doosra", "local_day": "2026-08-21",
                                     "local_time": "21:00:00"})
    replayed = [m["content"] for m in llm.sent[0]["input"][:-1]
                if isinstance(m, dict) and "content" in m]
    assert not [c for c in replayed if "[now]" in c], "an old turn carried a stale now block"


async def test_a_write_with_no_stated_time_takes_the_turns_clock(client, fake):
    """Every row the agent wrote used to land at 12:00, whatever hour it was."""
    fake(_msg(calls=[("log_payment", {
             "amount_paise": 4400, "direction": "debit", "kind": "expense",
             "category": "Other", "description": "raat ki chai",
             "local_day": "2026-08-20"})]),
         _msg("log kar diya"))
    body = (await client.post("/chat", json={"message": "44 ki chai",
                                             "local_day": "2026-08-20",
                                             "local_time": "23:10:00"})).json()
    row_id = next(c["row_id"] for c in body["cards"] if c["kind"] == "confirm")
    row = (await client.get("/transactions", params={"ids": row_id})).json()[0]
    assert "17:40" in row["occurred_at"], row["occurred_at"]  # 23:10 IST, stored UTC


async def test_a_time_the_model_states_beats_the_turns_clock(client, fake):
    fake(_msg(calls=[("log_payment", {
             "amount_paise": 4400, "direction": "debit", "kind": "expense",
             "category": "Other", "description": "subah ki chai",
             "local_day": "2026-08-20", "time": "07:15:00"})]),
         _msg("log kar diya"))
    body = (await client.post("/chat", json={"message": "subah 44 ki chai thi",
                                             "local_day": "2026-08-20",
                                             "local_time": "23:10:00"})).json()
    row_id = next(c["row_id"] for c in body["cards"] if c["kind"] == "confirm")
    row = (await client.get("/transactions", params={"ids": row_id})).json()[0]
    assert "01:45" in row["occurred_at"], row["occurred_at"]  # 07:15 IST, stored UTC


async def test_a_write_turn_produces_a_confirm_card(client, fake):
    fake(_msg(calls=[("log_payment", {
             "amount_paise": 4400, "direction": "debit", "kind": "expense",
             "category": "Other", "description": "chai", "local_day": "2026-08-20"})]),
         _msg("₹44 log kar diya"))
    body = (await client.post("/chat", json={"message": "44 ki chai",
                                             "local_day": "2026-08-20"})).json()
    confirm = next(c for c in body["cards"] if c["kind"] == "confirm")
    assert confirm["source"] == "paisa" and confirm["row_id"]
    # The category was the agent's guess, so the card marks it.
    assert next(f for f in confirm["fields"] if f["key"] == "category")["guessed"]


async def test_a_meal_card_leads_with_what_is_left(client, fake):
    fake(_msg(calls=[("log_meal", {"text_said": "Whey shake", "meal_type": "Snack",
                                   "local_day": "2026-08-20"})]),
         _msg("logged"))
    body = (await client.post("/chat", json={"message": "whey liya",
                                             "local_day": "2026-08-20"})).json()
    confirm = next(c for c in body["cards"] if c["kind"] == "confirm")
    # English, and the number first: "24 g protein left" / "Logged · macros unknown".
    assert "protein left" in confirm["lede"] or "unknown" in confirm["lede"]


async def test_the_same_write_twice_in_one_turn_happens_once(client, fake):
    """A model repeating itself is not the user asking twice. Ids are minted
    server-side, so nothing else would catch it."""
    call = ("log_payment", {"amount_paise": 100, "direction": "debit", "kind": "expense",
                            "category": "Other", "description": "dup",
                            "local_day": "2026-08-21"})
    fake(_msg(calls=[call, call]), _msg("done"))
    body = (await client.post("/chat", json={"message": "log it",
                                             "local_day": "2026-08-21"})).json()
    assert len([c for c in body["cards"] if c["kind"] == "confirm"]) == 1
    rows = (await client.get("/paisa/summary", params={
        "from": "2026-08-21", "to": "2026-08-21", "fields": "rows"})).json()["rows"]
    assert len([r for r in rows if r["description"] == "dup"]) == 1


async def test_a_tool_error_reaches_the_model_rather_than_the_user(client, fake):
    llm = fake(_msg(calls=[("log_payment", {
                   "amount_paise": 100, "direction": "debit", "kind": "lent",
                   "category": "Udhaar", "description": "x",
                   "local_day": "2026-08-20"})]),
               _msg("kisko diya?"))
    body = (await client.post("/chat", json={"message": "100 udhaar",
                                             "local_day": "2026-08-20"})).json()
    tool_msg = next(m for m in llm.sent[1]["input"]
                    if isinstance(m, dict) and m.get("type") == "function_call_output")
    assert "counterparty" in tool_msg["output"]
    assert body["reply"] == "kisko diya?"
    assert not [c for c in body["cards"] if c["kind"] == "confirm"]


async def test_a_runaway_loop_stops(client, fake):
    from app.agent.runner import MAX_ROUNDS
    call = ("paisa_report", {"to": "2026-08-20", "fields": ["spent"]})
    fake(*[_msg(calls=[call]) for _ in range(MAX_ROUNDS + 3)])
    body = (await client.post("/chat", json={"message": "loop",
                                             "local_day": "2026-08-20"})).json()
    assert "too many steps" in body["reply"]


# ─── the thread ──────────────────────────────────────────────────────────────

async def test_the_thread_is_one_and_grows(client, fake):
    fake(_msg("one"), _msg("two"))
    await client.post("/chat", json={"message": "first", "local_day": "2026-08-20"})
    await client.post("/chat", json={"message": "second", "local_day": "2026-08-20"})
    h = (await client.get("/chat")).json()["messages"]
    said = [m["text"] for m in h]
    assert said[-4:] == ["first", "one", "second", "two"]
    assert [m["seq"] for m in h] == sorted(m["seq"] for m in h)


async def test_the_model_sees_the_window_not_the_whole_thread(client, fake):
    from app.agent.runner import FOLD_AT
    for i in range(FOLD_AT):
        fake(_msg(f"r{i}"))
        await client.post("/chat", json={"message": f"m{i}", "local_day": "2026-08-20"})
    llm = fake(_msg("last"))
    await client.post("/chat", json={"message": "now", "local_day": "2026-08-20"})
    turns = [m for m in llm.sent[0]["input"]
             if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    everything = (await client.get("/chat")).json()["messages"]
    # A bounded tail, not the thread…
    assert len(turns) <= FOLD_AT + 1
    # …and the user still has all of it.
    assert len(everything) > len(turns)


async def test_no_message_falls_between_the_summary_and_the_window(client, fake, db_session):
    """The hole that batched folding opened. `_window` took the newest WINDOW
    while the un-summarised tail was allowed to grow to FOLD_AT, so the middle
    of the conversation was in neither, and the model could not see it."""
    from sqlalchemy import select

    from app.agent.runner import FOLD_AT, _thread, _window
    from app.models.chat import Message
    from tests.helpers import the_user

    user = await the_user(db_session)
    # Land somewhere between two folds, where the tail is at its longest.
    for i in range(FOLD_AT + 6):
        fake(_msg(f"reply {i}"))
        await client.post("/chat", json={"message": f"gap {i}", "local_day": "2026-08-20"})

    db_session.expire_all()
    convo = await _thread(db_session, user)
    shown = {m.seq for m in await _window(db_session, convo)}
    unsummarised = set((await db_session.scalars(
        select(Message.seq).where(Message.conversation_id == convo.id,
                                  Message.deleted_at.is_(None),
                                  Message.seq > convo.summary_through_seq))).all())
    assert unsummarised, "precondition: something is past the summary"
    invisible = unsummarised - shown
    assert not invisible, f"{len(invisible)} messages in neither the summary nor the window"


async def test_what_falls_out_of_the_window_becomes_a_summary(client, fake, monkeypatch):
    from app.agent.runner import FOLD_AT
    for i in range(FOLD_AT):
        fake(_msg(f"reply {i}"))
        await client.post("/chat", json={"message": f"turn {i}", "local_day": "2026-08-20"})
    summary = (await client.get("/chat")).json()["summary"]
    assert summary and "done" in summary or summary   # the fake writes something


async def test_the_summariser_reissues_and_stays_out_of_the_conversation(client, fake):
    """Two rules, both found by measuring against the real model.

    *Reissue it in full* carries the old note where *merge* and *do not drop*
    did not: four of four seed topics survived eight folds instead of one.
    And the summariser must be told it is not in the conversation — handed a
    transcript ending on a question it answered the question, in the agent's
    second-person voice with markdown and stale numbers, and threw the note
    away. spec/done/prompt-layout.md."""
    from app.agent.runner import FOLD_AT
    from app.config import settings

    # One fake for the whole run, so every call it was sent is on one record.
    llm = fake(*[_msg(f"r{i}") for i in range(FOLD_AT + 4)])
    for i in range(FOLD_AT + 2):
        await client.post("/chat", json={"message": f"merge {i}", "local_day": "2026-08-20"})

    folds = [c for c in llm.sent if "tools" not in c]
    assert folds, "no fold call was made"
    system = folds[-1]["instructions"]
    assert "Reissue it in full" in system
    assert "NOT part of that conversation" in system
    assert "never address the person" in system
    assert "third person" in system
    assert str(settings().chat_summary_words) in system, "word budget is not the configured one"
    # And it is handed the note so far, not just the new slice.
    said = folds[-1]["input"][0]["content"]
    assert "Your note so far:" in said and "<transcript>" in said


async def test_the_window_and_the_fold_come_from_config(client):
    from app.agent import runner as R
    from app.config import settings
    assert R.WINDOW == settings().chat_window
    assert R.FOLD_AT == max(settings().chat_fold_at, R.WINDOW + 2)
    # A fold has to have something to fold.
    assert R.FOLD_AT > R.WINDOW


async def test_a_failed_summariser_never_costs_the_turn(client, fake, monkeypatch):
    """Compaction used to run before the turn's commit, so a summariser that
    errored took the turn with it — while any tool that had already written
    stayed written, because the routes commit for themselves. The user retried
    and paid twice."""
    from app.agent import runner as R
    from app.agent.runner import FOLD_AT

    for i in range(FOLD_AT - 1):
        fake(_msg(f"w{i}"))
        await client.post("/chat", json={"message": f"warm {i}", "local_day": "2026-08-20"})
    async def boom(*a, **kw):
        raise TimeoutError("summariser is down")

    monkeypatch.setattr(R, "_fold", boom)
    fake(_msg(calls=[("log_payment", {
             "amount_paise": 4400, "direction": "debit", "kind": "expense",
             "category": "Other", "description": "chai", "local_day": "2026-08-20"})]),
         _msg("log kar diya"))
    r = await client.post("/chat", json={"message": "44 ki chai",
                                         "local_day": "2026-08-20"})
    assert r.status_code == 200, "a broken summariser must not fail the turn"
    row_id = next(c["row_id"] for c in r.json()["cards"] if c["kind"] == "confirm")

    # Both halves of the turn are durable — the history endpoint caps its page,
    # so check the tail rather than the count.
    tail = [(m["role"], m["text"]) for m in (await client.get("/chat")).json()["messages"][-2:]]
    assert tail == [("user", "44 ki chai"), ("agent", "log kar diya")], tail
    assert (await client.get("/transactions", params={"ids": row_id})).json()[0]["id"] == row_id


async def test_the_summarisers_own_call_is_counted(client, fake, db_session):
    """It runs a model call of its own. Leaving it out of the turn's totals
    understated every long thread's usage."""
    from sqlalchemy import select

    from app.agent.runner import FOLD_AT, _thread
    from app.models.chat import Conversation
    from tests.helpers import the_user

    user = await the_user(db_session)

    async def pointer():
        db_session.expire_all()
        c = await db_session.scalar(select(Conversation).where(
            Conversation.user_id == user, Conversation.deleted_at.is_(None)))
        return c.summary_through_seq

    await _thread(db_session, user)
    plain, with_fold = [], []
    # Drive past one whole batch so at least one turn is guaranteed to fold,
    # and label each turn by whether the summary pointer moved on it.
    for i in range(FOLD_AT + 2):
        was = await pointer()
        fake(_msg(f"c{i}"))
        out = (await client.post("/chat", json={"message": f"count {i}",
                                                "local_day": "2026-08-20"})).json()
        (with_fold if await pointer() > was else plain).append(out["tokens_in"])

    assert plain, "no plain turn to compare against"
    assert with_fold, "never folded across a full batch"
    assert min(with_fold) > max(plain), (plain[:3], with_fold)

async def test_the_thread_folds_in_batches_not_every_turn(client, fake, db_session):
    """Folding on every turn rewrote the summary and slid the window on every
    turn: a second model call each time, and a message list whose prefix never
    matched the last one. spec/done/prompt-layout.md."""
    from sqlalchemy import func, select

    from app.agent.runner import FOLD_AT, WINDOW
    from app.models.chat import Conversation, Message

    async def pointer():
        db_session.expire_all()
        c = await db_session.scalar(select(Conversation).where(
            Conversation.deleted_at.is_(None)))
        return c.summary_through_seq

    start = await pointer()
    # Well short of the batch: nothing folds, so the prefix keeps growing.
    for i in range(3):
        fake(_msg(f"r{i}"))
        await client.post("/chat", json={"message": f"m{i}", "local_day": "2026-08-20"})
    assert await pointer() == start, "folded before the batch was full"

    # Past it, and it folds back down to WINDOW in one go.
    for i in range(FOLD_AT):
        fake(_msg(f"s{i}"))
        await client.post("/chat", json={"message": f"n{i}", "local_day": "2026-08-20"})
    after = await pointer()
    assert after > start, "never folded"
    left = await db_session.scalar(select(func.count()).select_from(Message).where(
        Message.seq > after))
    assert left <= FOLD_AT, f"{left} un-summarised messages, batch is {FOLD_AT}"
    assert left >= WINDOW, "folded away more than the window"
