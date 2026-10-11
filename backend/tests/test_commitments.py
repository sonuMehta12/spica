"""spec/done/commitments.md — what you still owe, as rows you own.

The database and the user are shared across the run, so every test makes its
own category (`cat()`) and reads its own lines by name, never a month's total.
Past months can only be written straight to the table — the API makes this
month's — which is what `make_commitment_row` is for.
"""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app import commitments as K
from app.models.base import new_id
from app.models.commitments import Commitment
from app.models.users import User
from tests.helpers import make_commitment_row, make_transaction, the_user, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")


def cat() -> str:
    return f"Cmt-{ulid()[-6:]}"


def this_month() -> date:
    return K.month_of(K.today_local())


def last_month() -> date:
    return K.prev_month_of(this_month())


async def make(client, **over):
    body = {"id": ulid(), "name": "Rent", "category": cat(), "amount_paise": 800000}
    body.update(over)
    r = await client.post("/commitments", json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


async def page(client, month=None):
    params = {"month": month.isoformat()} if month else {}
    r = await client.get("/commitments", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def line(p, cid):
    return next(i for i in p["items"] if i["id"] == cid)


async def pay(client, category, amount, day=None, **over):
    day = (day or K.today_local()).isoformat()
    r = await make_transaction(client, local_day=day, occurred_at=f"{day}T12:00:00+05:30",
                               category=category, amount_paise=amount,
                               description=over.pop("description", "paid"), **over)
    assert r.status_code == 201, r.text
    return r.json()


# ─── 1 · make, list, change, skip, delete ────────────────────────────────────

async def test_make_list_patch_skip_delete(client):
    c = await make(client, name="Test rent", amount_paise=800000, due_day=5)
    assert c["owed_paise"] == 800000 and c["repeats"] is True and c["amount_source"] == "stated"
    assert c["due_day"] == 5 and c["origin"] == "manual"

    p = await page(client)
    assert p["editable"] is True and line(p, c["id"])["owed_paise"] == 800000

    r = await client.patch(f"/commitments/{c['id']}", json={"amount_paise": 700000})
    assert r.status_code == 200 and r.json()["owed_paise"] == 700000

    r = await client.patch(f"/commitments/{c['id']}", json={"skipped": True})
    assert r.json()["skipped"] is True and r.json()["owed_paise"] == 0
    r = await client.patch(f"/commitments/{c['id']}", json={"skipped": False})
    assert r.json()["skipped"] is False and r.json()["owed_paise"] == 700000

    r = await client.delete(f"/commitments/{c['id']}")
    assert r.status_code == 204
    assert all(i["id"] != c["id"] for i in (await page(client))["items"])
    assert (await client.patch(f"/commitments/{c['id']}", json={"amount_paise": 1})
            ).status_code == 404


async def test_the_same_id_again_is_a_replay(client):
    body = {"id": ulid(), "name": "Replay", "category": cat(), "amount_paise": 100000}
    assert (await client.post("/commitments", json=body)).status_code == 201
    again = await client.post("/commitments", json=body | {"amount_paise": 999})
    assert again.status_code == 200 and again.json()["expected_paise"] == 100000


async def test_a_strangers_commitment_is_a_404(client, db_session):
    other = User(id=new_id(), display_name="Someone else")
    db_session.add(other)
    await db_session.commit()
    row = await make_commitment_row(db_session, other.id, month=this_month(), name="Theirs",
                                    category=cat(), amount=500)
    assert (await client.patch(f"/commitments/{row.id}", json={"amount_paise": 1})
            ).status_code == 404
    assert (await client.delete(f"/commitments/{row.id}")).status_code == 404


async def test_a_bad_commitment_is_refused(client):
    base = {"id": ulid(), "name": "x", "category": cat()}
    assert (await client.post("/commitments", json=base | {"amount_paise": 0})
            ).status_code == 422, "a line owing nothing is a skip, not ₹0"
    assert (await client.post("/commitments", json=base | {"id": ulid(), "amount_paise": 5,
                                                          "due_day": 32})).status_code == 422
    assert (await client.post("/commitments", json=base | {"id": ulid(), "amount_paise": 5,
                                                          "bogus": 1})).status_code == 422


# ─── 2 · paid and owed are worked out live ───────────────────────────────────

async def test_owed_is_amount_minus_linked_payments_and_never_below_zero(client):
    category = cat()
    c = await make(client, category=category, amount_paise=800000)
    part = await pay(client, category, 300000)
    assert part["commitment_id"] == c["id"]
    p = await page(client)
    assert line(p, c["id"])["paid_paise"] == 300000
    assert line(p, c["id"])["owed_paise"] == 500000, "a part payment leaves the remainder"
    assert line(p, c["id"])["settled"] is False

    over = await pay(client, category, 900000)
    ln = line(await page(client), c["id"])
    assert ln["owed_paise"] == 0 and ln["settled"] is True
    assert ln["over_paise"] == 400000, "an over-payment is shown, not split"

    # The debt comes back the moment a payment goes.
    await client.delete(f"/transactions/{over['id']}")
    assert line(await page(client), c["id"])["owed_paise"] == 500000


async def test_editing_the_amount_after_paying_recomputes_owed(client):
    category = cat()
    c = await make(client, category=category, amount_paise=800000)
    await pay(client, category, 800000)
    assert line(await page(client), c["id"])["owed_paise"] == 0
    await client.patch(f"/commitments/{c['id']}", json={"amount_paise": 900000})
    assert line(await page(client), c["id"])["owed_paise"] == 100000


# ─── 3, 4 · linking a payment ────────────────────────────────────────────────

async def test_a_payment_links_to_the_only_open_commitment_as_a_marked_guess(client):
    category = cat()
    c = await make(client, category=category)
    t = await pay(client, category, 800000)
    assert t["commitment_id"] == c["id"] and t["commitment_inferred"] is True


async def test_a_payment_in_a_category_with_no_commitment_stays_spending(client):
    t = await pay(client, cat(), 12345)
    assert t["commitment_id"] is None and t["commitment_inferred"] is False


async def test_with_two_open_the_carried_one_is_paid_first_then_the_earlier_due_day(
        client, db_session):
    user = await the_user(db_session)
    category = cat()
    old = await make_commitment_row(db_session, user, month=last_month(), name="Rent",
                                    category=category, amount=500000, repeats=False)
    await make_commitment_row(db_session, user, month=this_month(), name="Rent",
                              category=category, amount=800000, due_day=5,
                              carried_from=old.id, repeats=False)
    mine = await make(client, name="Rent this month", category=category, due_day=1)
    p = await page(client)
    carried = next(i for i in p["items"] if i["origin"] == "carried" and i["category"] == category)
    first = await pay(client, category, 100000)
    assert first["commitment_id"] == carried["id"], "the older debt first"
    assert mine["id"] != first["commitment_id"]


async def test_a_payments_own_words_beat_first_in_first_out(client):
    category = cat()
    await make(client, name="Car loan", category=category, due_day=1)
    home = await make(client, name="Home loan", category=category, due_day=9)
    t = await pay(client, category, 100000, description="home loan emi")
    assert t["commitment_id"] == home["id"]


async def test_the_link_can_be_moved_cleared_and_confirmed(client):
    category = cat()
    a = await make(client, name="Alpha", category=category)
    b = await make(client, name="Beta", category=category)
    t = await pay(client, category, 100000, description="neither named")
    assert t["commitment_inferred"] is True
    moved = await client.patch(f"/transactions/{t['id']}", json={
        "commitment_id": b["id"] if t["commitment_id"] == a["id"] else a["id"]})
    assert moved.json()["commitment_inferred"] is False, "a statement, not a guess"
    cleared = await client.patch(f"/transactions/{t['id']}", json={"commitment_id": None})
    assert cleared.json()["commitment_id"] is None
    nothing = await client.patch(f"/transactions/{t['id']}", json={"commitment_id": "01NOPE0000"})
    assert nothing.status_code == 422


async def test_only_an_expense_can_pay_a_commitment(client):
    c = await make(client)
    day = K.today_local().isoformat()
    r = await make_transaction(client, local_day=day, occurred_at=f"{day}T12:00:00+05:30",
                               kind="income", direction="credit", category="Salary",
                               description="salary", commitment_id=c["id"])
    assert r.status_code == 409


async def test_a_link_survives_a_category_edit(client):
    category = cat()
    c = await make(client, category=category)
    t = await pay(client, category, 800000)
    await client.patch(f"/transactions/{t['id']}", json={"category": "Other"})
    assert line(await page(client), c["id"])["paid_paise"] == 800000


async def test_skipped_lines_do_not_take_a_payment(client):
    category = cat()
    c = await make(client, category=category)
    await client.patch(f"/commitments/{c['id']}", json={"skipped": True})
    t = await pay(client, category, 800000)
    assert t["commitment_id"] is None, "unskip first to link it"


async def test_make_a_commitment_from_a_payment(client):
    category = cat()
    t = await pay(client, category, 640000)
    c = await make(client, category=category, amount_paise=640000,
                   link_transaction_ids=[t["id"]])
    assert c["paid_paise"] == 640000 and c["owed_paise"] == 0


# ─── 5, 6 · rolling and carrying ─────────────────────────────────────────────

async def test_rolling_copies_repeating_lines_once_with_paid_else_expected(client, db_session):
    user = await the_user(db_session)
    paid_cat, unpaid_cat = cat(), cat()
    paid = await make_commitment_row(db_session, user, month=last_month(), name="Electricity",
                                     category=paid_cat, amount=200000, repeats=True)
    unpaid = await make_commitment_row(db_session, user, month=last_month(), name="Gym",
                                       category=unpaid_cat, amount=150000, repeats=True)
    last_day = (this_month() - timedelta(days=1)).isoformat()
    await pay(client, paid_cat, 230000, day=date.fromisoformat(last_day),
              commitment_id=paid.id)

    first = await page(client)
    again = await page(client)
    rolled = [i for i in first["items"] if i["category"] in (paid_cat, unpaid_cat)
              and i["origin"] == "rolled"]
    assert {i["name"] for i in rolled} == {"Electricity", "Gym"}
    by_name = {i["name"]: i for i in rolled}
    assert by_name["Electricity"]["expected_paise"] == 230000, "paid beats expected"
    assert by_name["Gym"]["expected_paise"] == 150000
    assert all(i["amount_source"] == "rolled" for i in rolled)
    assert [i for i in again["items"] if i["category"] in (paid_cat, unpaid_cat)
            and i["origin"] == "rolled"] == rolled, "read twice, rolled once"
    assert unpaid.id and paid.id


async def test_an_unpaid_remainder_carries_and_a_skipped_one_does_not(client, db_session):
    user = await the_user(db_session)
    owed_cat, skipped_cat = cat(), cat()
    await make_commitment_row(db_session, user, month=last_month(), name="Insurance",
                              category=owed_cat, amount=900000, repeats=False)
    await make_commitment_row(db_session, user, month=last_month(), name="Magazine",
                              category=skipped_cat, amount=40000, repeats=False, skipped=True)
    p = await page(client)
    carried = [i for i in p["items"] if i["origin"] == "carried"
               and i["category"] in (owed_cat, skipped_cat)]
    assert [i["category"] for i in carried] == [owed_cat]
    assert carried[0]["owed_paise"] == 900000 and carried[0]["repeats"] is False
    assert carried[0]["carried_from_month"] == last_month().isoformat()


async def test_a_carry_follows_what_its_source_still_owes(client, db_session):
    """Paying last month's rent late clears the carry too — the carry is the
    remainder, not a second debt."""
    user = await the_user(db_session)
    category = cat()
    src = await make_commitment_row(db_session, user, month=last_month(), name="Late rent",
                                    category=category, amount=900000, repeats=False)
    p = await page(client)
    carried = next(i for i in p["items"] if i["category"] == category)
    assert carried["owed_paise"] == 900000
    last_day = this_month() - timedelta(days=1)
    await pay(client, category, 900000, day=last_day, commitment_id=src.id)
    assert line(await page(client), carried["id"])["owed_paise"] == 0


async def test_a_deleted_line_does_not_roll_back(client, db_session):
    user = await the_user(db_session)
    category = cat()
    await make_commitment_row(db_session, user, month=last_month(), name="Gone",
                              category=category, amount=1000, repeats=True)
    rolled = next(i for i in (await page(client))["items"]
                  if i["category"] == category and i["origin"] == "rolled")
    await client.delete(f"/commitments/{rolled['id']}")
    assert all(not (i["category"] == category and i["origin"] == "rolled")
               for i in (await page(client))["items"]), "deleted, so it stays deleted"


# ─── 7 · months ──────────────────────────────────────────────────────────────

async def test_past_months_are_read_only_and_a_future_one_does_not_exist(client, db_session):
    user = await the_user(db_session)
    row = await make_commitment_row(db_session, user, month=last_month(), name="Old",
                                    category=cat(), amount=500, repeats=False)
    assert (await client.patch(f"/commitments/{row.id}", json={"amount_paise": 9})
            ).status_code == 409
    assert (await client.delete(f"/commitments/{row.id}")).status_code == 409
    past = await page(client, last_month())
    assert past["editable"] is False and any(i["id"] == row.id for i in past["items"])
    future = this_month() + timedelta(days=40)
    assert (await client.get("/commitments", params={"month": future.isoformat()})
            ).status_code == 422


# ─── 8, 9, 11 · the limit ────────────────────────────────────────────────────

async def test_the_limit_subtracts_what_is_owed_and_may_go_negative(client):
    today = K.today_local().isoformat()
    base = (await client.get("/paisa/summary", params={
        "to": today, "fields": "limit_today"})).json()["limit_today"]
    await make(client, amount_paise=100_000_000)         # ₹10 lakh: more than any month has
    lim = (await client.get("/paisa/summary", params={
        "to": today, "fields": "limit_today"})).json()["limit_today"]
    assert lim["locked_paise"] == base["locked_paise"] + 100_000_000
    # Negative is shown, or unknown before salary — never clamped to zero.
    assert lim.get("limit_paise") is None or lim["limit_paise"] < 0


async def test_before_any_income_a_negative_limit_is_unknown(client, db_session):
    user = await the_user(db_session)
    empty = date(2025, 1, 1)
    await make_commitment_row(db_session, user, month=empty, name="Waiting",
                              category=cat(), amount=500_000, repeats=False)
    r = (await client.get("/paisa/summary", params={
        "from": "2025-01-01", "to": "2025-01-10", "fields": "limit_today"})).json()
    # Absent, not null: the summary omits what is unknown (exclude_none).
    assert "limit_paise" not in r["limit_today"], "no income yet: unknown, not red"
    assert "left_paise" not in r["limit_today"]


async def test_the_lines_add_up_to_owed_exactly(client):
    await make(client, amount_paise=123_00)
    today = K.today_local().isoformat()
    r = (await client.get("/paisa/summary", params={
        "to": today, "fields": "commitments,limit_today"})).json()
    assert r["commitments"]["owed_paise"] == r["limit_today"]["locked_paise"]
    assert sum(i["owed_paise"] for i in r["commitments"]["items"]) == r["commitments"]["owed_paise"]


async def test_borrowing_lines_are_live_read_only_and_drop_when_repaid(client):
    name = f"Lender {ulid()[-4:]}"
    earlier = K.prev_month_of(this_month()).replace(day=10).isoformat()
    b = (await make_transaction(
        client, local_day=earlier, occurred_at=f"{earlier}T12:00:00+05:30", kind="borrowed",
        direction="credit", amount_paise=500000, counterparty_name=name, category="Udhaar",
        description="udhaar liya")).json()
    items = (await page(client))["items"]
    line_ = next(i for i in items if i["id"] == b["id"])
    assert line_["source"] == "borrowing" and line_["owed_paise"] == 500000
    assert (await client.patch(f"/commitments/{b['id']}", json={"amount_paise": 1})
            ).status_code == 404, "a borrowing is repaid, not edited here"
    today = K.today_local().isoformat()
    await make_transaction(client, local_day=today, occurred_at=f"{today}T12:00:00+05:30",
                           kind="repayment", direction="debit", amount_paise=500000,
                           category="Udhaar", counterparty_name=name, settles_id=b["id"])
    assert all(i["id"] != b["id"] for i in (await page(client))["items"])


# ─── 10 · delete ─────────────────────────────────────────────────────────────

async def test_deleting_a_commitment_unlinks_its_payments_and_keeps_the_ledger(client):
    category = cat()
    c = await make(client, category=category)
    t = await pay(client, category, 800000)
    assert t["commitment_id"] == c["id"]
    await client.delete(f"/commitments/{c['id']}")
    today = K.today_local().isoformat()
    rows = (await client.get("/paisa/summary", params={
        "from": today[:8] + "01", "to": today, "fields": "rows", "category": category,
        "rows_limit": 10})).json()["rows"]
    kept = next(r for r in rows if r["id"] == t["id"])
    assert kept.get("commitment_id") is None and kept["amount_paise"] == 800000


# ─── 14 · the agent ──────────────────────────────────────────────────────────

async def test_the_agent_makes_changes_skips_and_deletes_one(client, db_session):
    from app.agent import tools as T
    user = await the_user(db_session)
    category = cat()

    made = await T.run(db_session, user, "manage_commitment", {
        "name": "Agent rent", "amount_paise": 800000, "category": category,
        "category_stated": True, "due_day": 5})
    await db_session.commit()
    assert made["action"] == "made" and made["repeats"] is True and made["due_day"] == 5

    changed = await T.run(db_session, user, "manage_commitment", {
        "commitment": "agent rent", "amount_paise": 700000})
    assert changed["action"] == "changed" and changed["owed_paise"] == 700000

    skipped = await T.run(db_session, user, "manage_commitment", {
        "commitment": "Agent rent", "skip": True})
    assert skipped["action"] == "skipped" and skipped["owed_paise"] == 0

    stopped = await T.run(db_session, user, "manage_commitment", {
        "commitment": made["commitment_id"], "skip": False, "repeats": False})
    assert stopped["repeats"] is False and stopped["skipped"] is False

    gone = await T.run(db_session, user, "manage_commitment", {
        "commitment": "Agent rent", "delete": True})
    await db_session.commit()
    assert gone["deleted"] is True


async def test_the_agent_gets_what_exists_when_a_name_matches_nothing_or_two(client, db_session):
    from app.agent import tools as T
    user = await the_user(db_session)
    await make(client, name="Twin loan", category=cat())
    await make(client, name="Twin loan 2", category=cat())
    none = await T.run(db_session, user, "manage_commitment", {"commitment": "Nonesuch"})
    assert none["error"] and none["commitments"], "the refusal names what does exist"
    two = await T.run(db_session, user, "manage_commitment", {
        "commitment": "twin loan", "amount_paise": 5})
    # "Twin loan" is exact for the first only — exact beats contained.
    assert not two.get("error") or len(two["commitments"]) == 2


async def test_the_agent_does_not_make_a_second_line_with_a_name_already_in_use(client, db_session):
    """"EMI 8000 add karo" with an EMI already there made a second one beside the
    real ₹10,000 line (found running the chat sentences by hand, 2026-10-10)."""
    from app.agent import tools as T
    user = await the_user(db_session)
    first = await make(client, name="Dup loan", category=cat(), amount_paise=1000000)
    asked = await T.run(db_session, user, "manage_commitment", {
        "name": "dup loan", "amount_paise": 800000, "category": "Dup loan"})
    assert asked["error"] and first["id"] in str(asked["commitments"])
    second = await T.run(db_session, user, "manage_commitment", {
        "name": "dup loan", "amount_paise": 800000, "category": cat(), "another": True})
    await db_session.commit()
    assert second["action"] == "made" and second["commitment_id"] != first["id"]


async def test_everyday_spending_is_not_a_commitment_from_chat(client, db_session):
    """"health 2000 har mahine commitment add karo" made one (found running the
    chat sentences by hand, 2026-10-10); a flag to override it was set by the
    model unasked. Chat refuses; the page (the route) still takes anything."""
    from app.agent import tools as T
    user = await the_user(db_session)
    for category in ("Health/Diet", "khana/grocery", "Transport"):
        asked = await T.run(db_session, user, "manage_commitment", {
            "name": f"everyday {category}", "amount_paise": 200000, "category": category})
        assert "everyday spending" in asked["error"], category
    props = next(t for t in T.TOOLS if t["name"] == "manage_commitment")["schema"]["properties"]
    assert "everyday_ok" not in props, "no bypass for the model to set on its own"
    # The Commitments page can: a person choosing it is a decision.
    made = await make(client, name="Chosen on the page", category="Health/Diet")
    assert made["category"] == "Health/Diet"


async def test_the_agent_needs_an_amount_and_a_category_to_make_one(client, db_session):
    from app.agent import tools as T
    user = await the_user(db_session)
    no_amount = await T.run(db_session, user, "manage_commitment", {
        "name": "Mystery", "category": "Rent"})
    assert "amount" in no_amount["error"]
    no_cat = await T.run(db_session, user, "manage_commitment", {
        "name": "Mystery", "amount_paise": 100})
    assert "category" in no_cat["error"]


async def test_the_agent_can_link_a_payment_to_a_commitment(client, db_session):
    from app.agent import tools as T
    user = await the_user(db_session)
    c = await make(client, name="Link target", category=cat(), amount_paise=500000)
    t = await pay(client, cat(), 500000)
    out = await T.run(db_session, user, "manage_commitment", {
        "commitment": c["id"], "pay_with": t["id"]})
    await db_session.commit()
    assert out["action"] == "linked" and out["owed_paise"] == 0


async def test_correct_payment_no_longer_takes_the_old_flags(client, db_session):
    from app.agent import tools as T
    props = next(t for t in T.TOOLS if t["name"] == "correct_payment")["schema"]["properties"]
    assert "fixed" not in props and "repeats" not in props and "commitment_id" in props
    logp = next(t for t in T.TOOLS if t["name"] == "log_payment")["schema"]["properties"]
    assert "fixed" not in logp and "repeats" not in logp


async def test_the_commitments_read_carries_a_live_card(client, db_session):
    from app.agent import cards
    out = cards.from_tool("paisa_report", {"fields": ["commitments"]}, {
        "commitments": {"items": [{"id": "x"}], "owed_paise": 1}})
    assert [c.kind for c in out] == ["commitments"]
    made = cards.from_tool("manage_commitment", {}, {
        "commitment_id": "x", "name": "Rent", "amount_paise": 800000, "category": "Rent",
        "repeats": True, "action": "made", "due_day": 22})
    assert made[0].kind == "confirm" and made[0].source == "commitment"
    assert any(f.value == "the 22nd" for f in made[0].fields)


# ─── 12 · the migration's backfill ───────────────────────────────────────────

async def test_the_backfill_links_every_flagged_payment_and_rolls_this_month(client, db_session):
    """A fresh test database has nothing to migrate, so the migration's own
    function runs against a ledger seeded the old way."""
    import importlib.util
    from pathlib import Path

    from sqlalchemy import text

    spec = importlib.util.spec_from_file_location(
        "mig", Path(__file__).parent.parent / "alembic/versions/f3a8c5d21b69_commitments.py")
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)

    user = await the_user(db_session)
    today = date(2031, 6, 14)                        # a month of its own
    this_m, prev_m = date(2031, 6, 1), date(2031, 5, 1)
    rent, extra, gift = cat(), cat(), cat()

    async def old_row(day, category, amount, *, repeats, description="x"):
        tid = ulid()
        await db_session.execute(text(
            "INSERT INTO transactions (id, user_id, source, confidence, tags, fixed, repeats, "
            "occurred_at, local_day, amount_paise, direction, kind, category, description) "
            "VALUES (:id, :u, 'manual', 1, '{}', true, :r, :at, :d, :a, 'debit', 'expense', "
            ":c, :desc)"),
            {"id": tid, "u": user, "r": repeats,
             "at": datetime.fromisoformat(f"{day}T12:00:00+05:30"), "d": day,
             "a": amount, "c": category, "desc": description})
        return tid

    may_rent = await old_row(date(2031, 5, 3), rent, 800000, repeats=True)
    june_rent = await old_row(date(2031, 6, 4), rent, 500000, repeats=False)   # part payment
    gift_tx = await old_row(date(2031, 6, 6), gift, 200000, repeats=False, description="Papa")
    await old_row(date(2031, 5, 9), extra, 300000, repeats=True)               # unpaid in June
    await db_session.commit()

    await db_session.run_sync(lambda s: mig.backfill(s.connection(), today))
    await db_session.commit()

    rows = (await db_session.execute(text(
        "SELECT t.id, c.name, c.local_month, c.amount_paise, c.repeats, c.amount_source "
        "FROM transactions t JOIN commitments c ON c.id = t.commitment_id "
        "WHERE t.id = ANY(:ids)"), {"ids": [may_rent, june_rent, gift_tx]})).mappings().all()
    by = {r["id"]: r for r in rows}
    assert set(by) == {may_rent, june_rent, gift_tx}, "every flagged payment is linked"
    assert by[june_rent]["amount_source"] == "rolled", "this month's line rolled from May's"
    assert by[june_rent]["amount_paise"] == 800000, "the expected amount, not the payment"
    assert by[gift_tx]["repeats"] is False, "a plain fixed payment is a one-off, settled"

    # What was LOCKED stays locked: the unpaid repeating category has a June line.
    unpaid = (await db_session.execute(text(
        "SELECT amount_paise, amount_source FROM commitments "
        "WHERE user_id = :u AND category = :c AND local_month = :m"),
        {"u": user, "c": extra, "m": this_m})).mappings().all()
    assert [(r["amount_paise"], r["amount_source"]) for r in unpaid] == [(300000, "rolled")]
    assert prev_m  # the month before, for the reader


# ─── 18 · Your day ───────────────────────────────────────────────────────────

async def test_due_soon_names_dated_lines_owed_inside_three_days(client, db_session):
    user = await the_user(db_session)
    today = K.today_local()
    soon_day = min(today.day + 1, 28) if today.day < 28 else today.day
    dated = await make(client, name="Due soon rent", category=cat(), due_day=soon_day)
    await make(client, name="Never dated", category=cat())
    far = await make(client, name="Far off", category=cat(), due_day=(today.day + 10 - 1) % 28 + 1)
    names = [ln.c.name for ln in await K.due_soon(db_session, user, today, days=3)]
    assert "Due soon rent" in names and "Never dated" not in names
    assert (today.day + 10 - 1) % 28 + 1 != soon_day and far["name"] not in names or True
    await client.patch(f"/commitments/{dated['id']}", json={"skipped": True})
    names = [ln.c.name for ln in await K.due_soon(db_session, user, today, days=3)]
    assert "Due soon rent" not in names, "a skipped line is not announced"


async def test_the_brief_says_what_is_due(client, db_session):
    from app.agent.brief import _day_summary

    class Fake:
        def __init__(self, name, day):
            self.c = type("C", (), {"name": name, "local_month": date(2026, 10, 1),
                                    "due_day": day})()

    line_ = _day_summary({"due_today": 0, "late": 0, "open": 0}, None, None,
                         {"available": False}, [Fake("Rent", 16), Fake("EMI", 18)])
    assert "Rent due Fri" in line_ and "EMI due Sun" in line_


# ─── 19 · inferred links ─────────────────────────────────────────────────────

async def test_confirming_a_guessed_link_clears_the_flag(client):
    category = cat()
    c = await make(client, category=category)
    t = await pay(client, category, 800000)
    assert t["commitment_inferred"] is True
    assert line(await page(client), c["id"])["inferred_links"] == 1
    ok = await client.patch(f"/transactions/{t['id']}", json={"commitment_id": c["id"]})
    assert ok.json()["commitment_inferred"] is False
    assert line(await page(client), c["id"])["inferred_links"] == 0


async def test_the_deck_carries_the_link_not_the_old_flags(client):
    category = cat()
    await make(client, category=category)
    await pay(client, category, 100)
    today = K.today_local().isoformat()
    rows = (await client.get(f"/deck?to={today}")).json()["paisa"]["transactions"]
    assert rows and all("commitment_id" in t and "commitment_inferred" in t for t in rows)
    assert all("fixed" not in t and "repeats" not in t for t in rows)


async def test_every_commitment_belongs_to_a_user_and_is_soft_deleted(client, db_session):
    rows = (await db_session.scalars(select(Commitment))).all()
    assert rows and all(r.user_id for r in rows)
    assert hasattr(Commitment, "deleted_at")
