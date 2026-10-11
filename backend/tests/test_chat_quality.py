"""spec/done/chat-quality.md — what the model is given, and what it may write.

The model is mocked. Whether it now chooses well is n2n_eval's question; these
assert the server's half of each fix the eval's review asked for: money reaches
the model in rupees and debts by who owes whom, a meal's estimate says it is
whole, a report names its period and says when nothing was recorded, a write
with nothing to write is refused with the next step, every past turn carries
the ids of the rows it wrote, and the tracked habits ride every turn.
"""

import pytest

from tests.helpers import _msg, the_user, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _keys(v) -> set[str]:
    if isinstance(v, dict):
        return set(v) | {k for x in v.values() for k in _keys(x)}
    if isinstance(v, list):
        return {k for x in v for k in _keys(x)}
    return set()


# ─── what the model reads ────────────────────────────────────────────────────

async def test_money_reaches_the_model_in_rupees(client):
    """₹21,252 for 212,522 paise was the model converting it itself."""
    from app.agent.tools import for_model
    out = for_model("paisa_report", {"spent_paise": 212522, "limit_paise": -5000,
                                     "unknown_paise": None})
    assert out == {"spent": "₹2,125", "limit": "-₹50", "unknown": "no data"}
    assert not any(k.endswith("_paise") for k in _keys(out))


async def test_a_debt_is_named_by_who_owes_whom(client):
    """`still_out` was read both ways: "Amit ko ₹4,000 dene baaki hain"."""
    from app.agent.tools import for_model
    report = for_model("paisa_report", {"udhaar": {
        "out_paise": 400000, "owe_paise": 0,
        "open": [{"kind": "lent", "name": "Amit", "amount_paise": 400000,
                  "remaining_paise": 250000}]}})
    u = report["udhaar"]
    assert (u["others_owe_you"], u["you_owe_others"]) == ("₹4,000", "₹0")
    assert u["open"][0]["still_to_settle"] == "₹2,500"
    assert u["open"][0]["who_owes"] == "they owe you"
    people = for_model("people", {"people": [{"name": "Amit", "still_out_paise": 400000,
                                              "you_owe_paise": 0, "sent_paise": 400000}]})
    p = people["people"][0]
    assert (p["they_owe_you"], p["you_owe_them"], p["sent"]) == ("₹4,000", "₹0", "₹4,000")
    # Outside udhaar and people the names are left alone: `balance` is not a debt.
    assert "out" in for_model("paisa_report", {"balance": {"out_paise": 100}})["balance"]


async def test_a_meal_estimate_says_it_is_whole(client):
    """`unresolved` meant "not in the library" and was read as "not in the total"."""
    from app.agent.tools import for_model
    estimated = for_model("log_meal", {"meal": {"estimated_kcal": 490},
                                       "unresolved": ["achaar"], "needs_quantity": ["roti"]})
    assert "not partial" in estimated["total_is"]
    assert estimated["not_in_library"] == ["achaar"] and "needs_quantity" not in estimated
    # From the library alone, nothing is said that is not true.
    library = for_model("log_meal", {"meal": {"estimated_kcal": None},
                                     "unresolved": ["achaar"], "needs_quantity": []})
    assert "total_is" not in library and library["unresolved"] == ["achaar"]


async def test_a_report_names_its_period_and_an_empty_one_is_no_data(client, db_session):
    """Left out, `from` is the 1st of the month; before the ledger, not ₹0."""
    from app.agent import tools as T
    user = await the_user(db_session)
    out = await T.run(db_session, user, "paisa_report",
                      {"from": "2019-01-01", "to": "2019-01-31", "fields": ["spent"]})
    assert out["period"] == {"from": "2019-01-01", "to": "2019-01-31"}
    assert "never ₹0" in out["no_records"]
    month = await T.run(db_session, user, "paisa_report", {"to": "2026-08-20",
                                                           "fields": ["spent"]})
    assert month["period"]["from"] == "2026-08-01"


# ─── what it may write ───────────────────────────────────────────────────────

async def test_a_write_with_nothing_to_write_is_refused(client, db_session):
    """Each refusal names the next step, so the model recovers rather than retries."""
    from app.agent import tools as T
    user = await the_user(db_session)
    tick = await T.run(db_session, user, "log_day", {"local_day": "2026-08-20"})
    assert "nothing to write" in tick["error"] and "context" in tick["error"]
    zero = await T.run(db_session, user, "log_payment", {
        "amount_paise": 0, "direction": "debit", "kind": "expense",
        "category": "Khana/Grocery", "description": "grocery", "local_day": "2026-08-20"})
    assert "ask how much" in zero["error"]
    ex = ulid()
    r = await client.post("/exercises", json={"id": ex, "name": f"Squat {ex[-4:]}",
                                              "kind": "strength"})
    assert r.status_code == 201
    look = await T.run(db_session, user, "log_exercise", {"exercise_id": ex, "did": False})
    assert "already in the library" in look["error"]


# ─── what every turn carries ─────────────────────────────────────────────────

async def test_the_rows_written_ride_the_context_not_the_replies(client):
    """Under the replies, the model copied the line into its own answers."""
    from types import SimpleNamespace

    from app.agent.runner import _written
    window = [
        SimpleNamespace(role="user", cards=None),
        SimpleNamespace(role="agent", cards=[
            {"kind": "agent", "text": "x"},
            {"kind": "confirm", "source": "paisa", "row_id": "01TX", "lede": "₹20 · chai"},
            {"kind": "table", "source": "paisa", "ids": ["01OTHER"]}]),
        SimpleNamespace(role="agent", cards=[
            {"kind": "confirm", "source": "diet", "row_id": "01MEAL", "state": "deleted"}]),
    ]
    line = _written(window)
    assert line.startswith("\n[rows written in this conversation, newest first")
    assert line.index("diet 01MEAL (deleted)") < line.index("paisa 01TX — ₹20 · chai")
    assert "01OTHER" not in line and _written([]) == ""


async def test_the_next_turn_sees_the_row_just_written(client, fake):
    """"dal ek katori thi" went out as meal_id PLACEHOLDER: the id was nowhere."""
    llm = fake(
        _msg(calls=[("log_payment", {
            "amount_paise": 2000, "direction": "debit", "kind": "expense",
            "category": "Khana/Grocery", "description": "chai", "local_day": "2026-08-20"})]),
        _msg("₹20 ki chai log kar di."),
        _msg("Theek hai. [rows written in this conversation: paisa 01X]"),
    )
    await client.post("/chat", json={"message": "chai 20", "local_day": "2026-08-20"})
    r = await client.post("/chat", json={"message": "chai 25 ki thi",
                                         "local_day": "2026-08-20"})
    items = [m for m in llm.sent[-1]["input"] if isinstance(m, dict)]
    assert "[rows written" in items[-1]["content"] and "chai" in items[-1]["content"]
    assert not any("[rows written" in (m.get("content") or "")
                   for m in items if m.get("role") == "assistant")
    # And an echo of it never reaches the person.
    assert r.json()["reply"] == "Theek hai."


async def test_every_turn_lists_the_tracked_habits(client, db_session):
    from datetime import date

    from app.agent import prompt as P
    user = await the_user(db_session)
    name = f"Yoga {ulid()[-5:]}"
    h = await client.post("/habits", json={"id": ulid(), "name": name, "direction": "build"})
    assert h.status_code == 201
    r = await client.post("/habit-logs", json={
        "id": ulid(), "habit_id": h.json()["id"], "occurred_at": "2026-08-21T07:00:00+05:30",
        "local_day": "2026-08-21", "source": "manual"})
    assert r.status_code < 300
    block = await P.now_block(db_session, user, date(2026, 8, 21))
    line = next(x for x in block.splitlines() if x.startswith("[habits]"))
    assert f"{name} (to build) 1 today" in line


# ─── round 2: what reading round 1's replies found ───────────────────────────

async def test_a_write_that_fails_on_commit_is_data_not_a_crash(client, db_session):
    """A null protein on a correction ended the whole turn as a 500."""
    from app.agent import tools as T
    user = await the_user(db_session)
    from tests.helpers import make_meal
    r = await make_meal(client, local_day="2026-08-22", dish=f"Dal {ulid()[-4:]}")
    meal = r.json()["meal"]["id"]
    out = await T.run(db_session, user, "correct_meal",
                      {"meal_id": meal, "protein_g": None, "kcal": None, "note": "ek katori"})
    assert "error" not in out, out


async def test_a_miscopied_id_finds_its_row_and_a_wild_one_does_not(client, db_session):
    from app.agent import tools as T
    from tests.helpers import make_meal
    user = await the_user(db_session)
    from app.models.base import new_id
    # A real ULID: the helper's sequential test ids sit within two edits of each
    # other, where the guard rightly refuses to pick one.
    r = await make_meal(client, id=new_id(), local_day="2026-08-22", dish="Rajma")
    meal = r.json()["meal"]["id"]
    short = meal[:10] + meal[11:]          # one character dropped
    ok = await T.run(db_session, user, "correct_meal", {"meal_id": short, "note": "ek katori"})
    assert "error" not in ok, ok
    wild = await T.run(db_session, user, "correct_meal", {"meal_id": "PLACEHOLDER"})
    assert wild["status"] == 404


async def test_a_payment_takes_the_category_they_used_before(client, db_session):
    """A cigarette went to Health/Diet once and Other the next; the ledger says Other."""
    from app.agent import tools as T
    user = await the_user(db_session)
    thing = f"Cigarette {ulid()[-4:]}"
    base = {"amount_paise": 2500, "direction": "debit", "kind": "expense",
            "description": thing, "local_day": "2026-08-22"}
    await T.run(db_session, user, "log_payment", {**base, "category": "Other",
                                                  "category_stated": True})
    second = await T.run(db_session, user, "log_payment", {**base, "category": "Health/Diet"})
    assert second["category"] == "Other" and second["confidence"] < 1


async def test_a_habit_change_that_changes_nothing_is_refused(client, db_session):
    from app.agent import tools as T
    user = await the_user(db_session)
    name = f"Walk {ulid()[-5:]}"
    await client.post("/habits", json={"id": ulid(), "name": name, "direction": "build"})
    out = await T.run(db_session, user, "manage_habit", {"habit_id": name, "delete": False})
    assert "nothing to change" in out["error"]


async def test_a_project_icon_named_bare_is_the_sets_own(client, db_session):
    from app.agent import tools as T
    user = await the_user(db_session)
    out = await T.run(db_session, user, "manage_project",
                      {"name": f"Garden {ulid()[-5:]}", "icon": "leaf"})
    assert out.get("icon") == "icon:leaf", out


async def test_the_habits_line_says_what_one_usually_costs(client, db_session):
    from datetime import date

    from app.agent import prompt as P
    from app.agent import tools as T
    user = await the_user(db_session)
    name = f"Gutka{ulid()[-4:].lower()}"
    await client.post("/habits", json={"id": ulid(), "name": name, "direction": "break"})
    for _ in range(2):
        await T.run(db_session, user, "log_payment", {
            "amount_paise": 1500, "direction": "debit", "kind": "expense", "category": "Other",
            "description": name, "local_day": "2026-08-23", "category_stated": True})
    block = await P.now_block(db_session, user, date(2026, 8, 23))
    assert f"{name} (to cut) 0 today, usually bought one at ₹15" in block


# ─── round 3 ─────────────────────────────────────────────────────────────────

async def test_an_amount_under_a_bare_paise_key_is_in_rupees(client):
    """by_category sends `paise`; the model converted ₹17,200 itself."""
    from app.agent.tools import for_model
    out = for_model("paisa_report", {"by_category": [{"category": "Shopping",
                                                      "paise": 1720000, "share": 0.8}]})
    assert out["by_category"][0] == {"category": "Shopping", "amount": "₹17,200",
                                     "share": 0.8}


async def test_a_repayment_finds_the_one_open_loan_it_pays(client, db_session):
    """"needs settles_id" made the agent give up on a repayment it could place."""
    from app.agent import tools as T
    user = await the_user(db_session)
    who = f"Amit {ulid()[-5:]}"
    base = {"direction": "debit", "kind": "lent", "category": "Udhaar",
            "description": "udhaar", "local_day": "2026-08-24", "counterparty_name": who}
    lent = await T.run(db_session, user, "log_payment", {**base, "amount_paise": 400000})
    back = await T.run(db_session, user, "log_payment", {
        **base, "kind": "repayment", "direction": "credit", "amount_paise": 150000,
        "description": "wapas"})
    assert back.get("settles_id") == lent["id"], back
    # Two open loans with them: which one is a question, not a guess.
    await T.run(db_session, user, "log_payment", {**base, "amount_paise": 100000})
    unsure = await T.run(db_session, user, "log_payment", {
        **base, "kind": "repayment", "direction": "credit", "amount_paise": 50000,
        "description": "wapas"})
    assert "settles_id" in unsure["error"]


# ─── round 5 ─────────────────────────────────────────────────────────────────

async def test_a_result_says_whether_a_card_will_show_it(client):
    """"2 tasks complete kiye; list card mein hai" — with no card under it."""
    from app.agent.tools import for_model
    shown = for_model("work_report", {"count": 2, "tasks": []}, {"status": "open", "show": True})
    assert "To-do card" in shown["card"]
    read = for_model("work_report", {"count": 2, "tasks": []}, {"status": "open"})
    assert read["card"].startswith("no card")
    rows = for_model("paisa_report", {"rows": []},
                     {"fields": ["rows"], "to": "2026-08-20", "show": True})
    assert "table" in rows["card"]
    looked = for_model("paisa_report", {"rows": []}, {"fields": ["rows"], "to": "2026-08-20"})
    assert looked["card"].startswith("no card")
    assert "card" not in for_model("paisa_report", {"spent_paise": 1}, {"fields": ["spent"]})


async def test_rows_show_as_a_table_only_when_the_agent_says_so(client):
    """"Blue Tokai pe kitna kharcha hua?" read the month's rows for one number,
    and the table came back under the reply. Whether rows are shown is the
    agent's call, made with `show` — not a word list over the sentence."""
    from app.agent import cards as C
    rows = {"rows": [{"id": "r1", "amount_paise": 2500, "direction": "debit",
                      "kind": "expense"}], "days_in_range": 1}
    shown = C.from_tool("paisa_report", {"to": "2026-08-20", "fields": ["rows"], "show": True},
                        rows)
    assert [c.kind for c in shown] == ["table"]
    assert C.from_tool("paisa_report", {"to": "2026-08-20", "fields": ["rows"]}, rows) == []
    assert C.from_tool("diet_report", {"to": "2026-08-20", "fields": ["rows"]},
                       {"rows": []}) == []


def test_every_schema_field_is_one_its_handler_takes():
    """`show` went onto work_report's schema but not its signature, so
    "mere saare tasks dikhao" ran work_report(show=true), got a TypeError back,
    and the agent said the tool refused (2026-10-10). Whatever a schema offers
    the model, the handler must accept."""
    import inspect

    from app.agent import tools as T
    for tool in T.TOOLS:
        params = inspect.signature(tool["fn"]).parameters
        if any(p.kind is p.VAR_KEYWORD for p in params.values()):
            continue
        offered = set(tool["schema"].get("properties", {}))
        assert offered <= set(params), (tool["name"], offered - set(params))

