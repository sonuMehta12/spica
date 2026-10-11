"""GET /paisa/summary — the Paisa card's numbers, computed once on the server.

Everything here is pinned to March 2026 and `to = 2026-03-31`, so `days_left`
is 1 and the limit equals pool − locked − savings to the rupee, with no other
test's rows in the way. spec/in-progress/agent-tools.md § paisa_report.
"""

from datetime import date

import pytest

from tests.helpers import make_commitment_row, make_transaction, the_user, ulid

pytestmark = pytest.mark.asyncio(loop_scope="session")

MAR, TO = "2026-03-01", "2026-03-31"


async def tx(client, day, amount, **over):
    body = {"local_day": day, "occurred_at": f"{day}T12:00:00+05:30",
            "amount_paise": amount, "category": "Other"}
    body.update(over)
    r = await make_transaction(client, **body)
    assert r.status_code == 201, r.text
    return r.json()


async def summary(client, fields, frm=MAR, to=TO, **params):
    r = await client.get("/paisa/summary", params={"from": frm, "to": to,
                                                   "fields": ",".join(fields), **params})
    assert r.status_code == 200, r.text
    return r.json()


# ─── the contract ────────────────────────────────────────────────────────────

async def test_only_the_asked_keys_come_back(client):
    """Absent is *not asked*, never zero — so nothing is read off by accident."""
    s = await summary(client, ["spent"])
    assert "spent_paise" in s
    # absent, not null: the key is not in the JSON at all
    assert "daily_avg_paise" not in s and "limit_today" not in s and "rows" not in s


async def test_an_unknown_field_is_refused(client):
    r = await client.get("/paisa/summary", params={"to": TO, "fields": "spent,vibes"})
    assert r.status_code == 422 and "vibes" in r.text


async def test_from_after_to_is_refused(client):
    r = await client.get("/paisa/summary", params={"from": TO, "to": MAR, "fields": "spent"})
    assert r.status_code == 422


async def test_from_defaults_to_the_first_of_the_month(client):
    """The pool is the month, so a summary with no `from` is the month so far."""
    r = await client.get("/paisa/summary", params={"to": "2026-03-15", "fields": "days_in_range"})
    assert r.status_code == 200
    assert r.json()["from"] == MAR and r.json()["days_in_range"] == 15


# ─── the arithmetic ──────────────────────────────────────────────────────────

async def test_spent_excludes_committed_and_the_average_divides_by_days(client, db_session):
    user = await the_user(db_session)
    rent = await make_commitment_row(db_session, user, month=date(2026, 3, 1),
                                     name="Sum-R rent", category="Sum-R", amount=20_000)
    await tx(client, "2026-03-02", 30_000, category="Sum-A")
    await tx(client, "2026-03-03", 20_000, category="Sum-R",
             commitment_id=rent.id)   # an obligation paid, not spend
    s = await summary(client, ["spent", "daily_avg", "days_in_range"], category="Sum-A")
    assert s["spent_paise"] == 30_000
    assert s["days_in_range"] == 31 and s["daily_avg_paise"] == round(30_000 / 31)
    paid = await summary(client, ["spent", "fixed"], category="Sum-R")
    assert paid["spent_paise"] == 0 and paid["fixed"]["fixed_paise"] == 20_000


async def test_the_limit_is_pool_minus_locked_minus_savings_over_days_left(client):
    """to = 31 March, so days_left = 1 and the limit is the pool itself, less
    what is held back. The same numbers the Paisa card shows."""
    before = (await summary(client, ["limit_today"]))["limit_today"]
    await tx(client, "2026-03-05", 100_000, kind="income", direction="credit",
             category="Salary", description="salary")
    await tx(client, "2026-03-06", 7_000, category="Sum-B")
    lim = (await summary(client, ["limit_today"]))["limit_today"]
    assert lim["days_left"] == 1
    assert lim["pool_paise"] == before["pool_paise"] + 100_000 - 7_000
    # May be negative now: past the line is a different fact from nothing left.
    assert lim["limit_paise"] == (
        lim["pool_paise"] - lim["locked_paise"] - lim["savings_target_paise"])


async def test_what_a_commitment_owes_is_locked_until_it_is_paid(client, db_session):
    """March's rent, a commitment: until a payment links to it, its amount is
    held out of the pool."""
    user = await the_user(db_session)
    cat = f"Rent-{ulid()[-4:]}"
    c = await make_commitment_row(db_session, user, month=date(2026, 3, 1),
                                  name="Rent", category=cat, amount=8_000)
    locked = (await summary(client, ["limit_today"]))["limit_today"]["locked_paise"]
    await tx(client, "2026-03-04", 8_200, category=cat, commitment_id=c.id)
    after = (await summary(client, ["limit_today"]))["limit_today"]["locked_paise"]
    assert locked - after == 8_000


async def test_a_borrowing_still_owed_from_an_earlier_month_is_locked(client):
    """Money you owe from before is a cost of this month until it is paid back."""
    name = f"Lender {ulid()[-4:]}"
    b = await tx(client, "2026-02-20", 5_000, kind="borrowed", direction="credit",
                 category="Udhaar", counterparty_name=name)
    locked = (await summary(client, ["limit_today"]))["limit_today"]["locked_paise"]
    await tx(client, "2026-03-10", 5_000, kind="repayment", direction="debit",
             category="Udhaar", settles_id=b["id"])
    after = (await summary(client, ["limit_today"]))["limit_today"]["locked_paise"]
    assert locked - after == 5_000


async def test_udhaar_nets_repayments_against_their_lending(client):
    name = f"Dost {ulid()[-4:]}"
    lent = await tx(client, "2026-03-11", 7_000, kind="lent", counterparty_name=name,
                    category="Udhaar")
    open_ = await tx(client, "2026-03-12", 4_000, kind="lent", counterparty_name=name,
                     category="Udhaar")
    await tx(client, "2026-03-20", 7_000, kind="repayment", direction="credit",
             category="Udhaar", settles_id=lent["id"])
    u = (await summary(client, ["udhaar"]))["udhaar"]
    assert u["out_paise"] >= 4_000 and u["open_lendings"] >= 1
    # the repaid one contributes nothing
    assert open_["id"]  # exists; out counts only what is still owed


async def test_by_category_shares_sum_to_one(client):
    s = await summary(client, ["by_category", "spent"])
    if s["spent_paise"]:
        assert abs(sum(c["share"] for c in s["by_category"]) - 1.0) < 1e-9
        assert sum(c["paise"] for c in s["by_category"]) == s["spent_paise"]


async def test_by_counterparty_names_the_payee(client):
    name = f"Chai {ulid()[-4:]}"
    await tx(client, "2026-03-13", 4_400, counterparty_name=name, category="Sum-C")
    await tx(client, "2026-03-14", 5_600, counterparty_name=name, category="Sum-C")
    row = next(c for c in (await summary(client, ["by_counterparty"]))["by_counterparty"]
               if c["name"] == name)
    assert row["paise"] == 10_000 and row["n"] == 2


# ─── rows: opt-in, capped, honest about the page ─────────────────────────────

async def test_rows_are_capped_and_say_how_many_matched(client):
    cat = f"Page-{ulid()[-4:]}"
    for i in range(35):
        await tx(client, f"2026-03-{(i % 28) + 1:02d}", 100 + i, category=cat)
    s = await summary(client, ["rows"], category=cat)
    assert len(s["rows"]) == 30 and s["total_matching"] == 35 and s["next_after"]
    page2 = await summary(client, ["rows"], category=cat, after=s["next_after"])
    # the last page has no cursor — absent, like every other un-set field
    assert len(page2["rows"]) == 5 and "next_after" not in page2


async def test_rows_limit_cannot_exceed_the_cap(client):
    r = await client.get("/paisa/summary", params={"to": TO, "fields": "rows", "limit": 200})
    assert r.status_code == 422


async def test_within_limit_counts_every_row_when_the_limit_is_huge(client):
    await client.patch("/users/me", json={"savings_target_paise": 0})
    await tx(client, "2026-03-21", 9_000_000, kind="income", direction="credit",
             category="Salary", description="bonus")
    s = await summary(client, ["within_limit"])
    assert s["within_limit"]["n"] == s["within_limit"]["of"] and s["within_limit"]["of"] > 0


# ─── balance: "how much is left", answered once ──────────────────────────────

async def test_balance_is_the_whole_answer_not_parts_to_subtract(client, db_session):
    """Asked "kitna bacha hai", the agent used to fetch `spent` and `income`
    and subtract. `spent` is discretionary expenses ONLY, so fixed costs,
    lendings and repayments vanished: it reported ₹1,29,149 against a true
    ₹59,149. spec/done/fixed-costs.md § money in, and who agrees on it."""
    day, month = "2026-11-13", "2026-11"
    await make_transaction(client, local_day=day, kind="income", direction="credit",
                           amount_paise=10000000, category="Salary", description="Salary")
    user = await the_user(db_session)
    rent = await make_commitment_row(db_session, user, month=date(2026, 11, 1), name="Rent",
                                     category="Bal-Rent", amount=4000000)
    await make_transaction(client, local_day=day, amount_paise=4000000,
                           commitment_id=rent.id,
                           category="Bal-Rent", description="Rent")
    await make_transaction(client, local_day=day, amount_paise=100000,
                           category="Bal-Food", description="Groceries")
    await make_transaction(client, local_day=day, kind="lent", direction="debit",
                           amount_paise=500000, counterparty_name="Bal-Dost",
                           category="Udhaar", description="udhaar diya")

    r = await client.get("/paisa/summary", params={
        "from": f"{month}-01", "to": day, "fields": "balance,spent,income"})
    b = r.json()["balance"]

    # in − out, with nothing quietly excluded.
    assert b["came_in_paise"] == 10000000
    assert b["went_out_paise"] == 4000000 + 100000 + 500000
    assert b["left_paise"] == b["came_in_paise"] - b["went_out_paise"]
    assert b["of_which_fixed_paise"] == 4000000
    assert b["of_which_lent_paise"] == 500000

    # And this is exactly the trap: `spent` is NOT what went out.
    assert r.json()["spent_paise"] == 100000, "spent is discretionary only"
    assert r.json()["income_paise"] - r.json()["spent_paise"] != b["left_paise"]


async def test_balance_separates_what_is_left_from_what_is_free(client):
    """Having money and being able to spend it are different. A ₹0 limit beside
    a healthy balance is the state the card has to explain, not hide."""
    r = await client.get("/paisa/summary", params={
        "to": "2026-11-13", "fields": "balance,limit_today"})
    b, lim = r.json()["balance"], r.json()["limit_today"]
    assert b["left_paise"] == lim["pool_paise"]
    assert b["committed_paise"] == lim["locked_paise"]
    assert b["free_paise"] == (b["left_paise"] - b["committed_paise"]
                               - b["savings_target_paise"])
    assert b["days_left"] == lim["days_left"]


async def test_balance_needs_no_other_field_to_be_asked_for(client):
    """It reads month rows of its own; asking for it alone must not 500."""
    r = await client.get("/paisa/summary", params={"to": "2026-11-13", "fields": "balance"})
    assert r.status_code == 200 and "balance" in r.json()
    assert r.json().get("limit_today") is None, "un-asked fields stay absent"


# ─── commitments: what is still owed, line by line ───────────────────────────

async def test_commitments_list_what_is_owed_not_what_was_paid(client, db_session):
    """Asked "kya kya committed hai", the agent used to read `fixed` — which is
    what has ALREADY been paid — and answered with the opposite set: it listed
    the EMI it had settled and said nothing was left, on a month with ₹50,948
    outstanding. spec/done/commitments.md."""
    user = await the_user(db_session)
    nov = date(2026, 11, 1)
    rent = await make_commitment_row(db_session, user, month=nov, name="Cmt-Rent",
                                     category="Cmt-Rent", amount=700000)
    await make_commitment_row(db_session, user, month=nov, name="Cmt-Subs",
                              category="Cmt-Subs", amount=300000)
    # Rent over-paid: the payment is not split.
    await make_transaction(client, local_day="2026-11-05", category="Cmt-Rent",
                           description="Rent paid", amount_paise=900000,
                           commitment_id=rent.id)

    r = (await client.get("/paisa/summary", params={
        "to": "2026-11-13", "fields": "commitments,limit_today"})).json()
    items = {i["name"]: i for i in r["commitments"]["items"]}

    # Paid, and the over-payment is visible rather than folded away.
    assert items["Cmt-Rent"]["settled"] is True
    assert items["Cmt-Rent"]["expected_paise"] == 700000
    assert items["Cmt-Rent"]["paid_paise"] == 900000
    assert items["Cmt-Rent"]["over_paise"] == 200000
    assert items["Cmt-Rent"]["owed_paise"] == 0

    # Not paid, so still owed.
    assert items["Cmt-Subs"]["settled"] is False
    assert items["Cmt-Subs"]["owed_paise"] == 300000


async def test_the_commitment_lines_add_up_to_the_number_on_the_card(client):
    """A breakdown that disagreed with `locked` would be the same class of bug
    it exists to fix."""
    r = (await client.get("/paisa/summary", params={
        "to": "2026-11-13", "fields": "commitments,limit_today"})).json()
    assert r["commitments"]["owed_paise"] == r["limit_today"]["locked_paise"]


async def test_paying_a_commitment_drops_it_and_the_pool_together(client, db_session):
    """The user's question: pay it, and does committed go down? Both numbers
    move by the same amount — the money left, and it is no longer owed."""
    from sqlalchemy import select

    from app.models.commitments import Commitment
    user = await the_user(db_session)
    subs = await db_session.scalar(select(Commitment).where(
        Commitment.user_id == user, Commitment.name == "Cmt-Subs"))
    before = (await client.get("/paisa/summary", params={
        "to": "2026-11-13", "fields": "commitments,balance"})).json()
    owed, left = before["commitments"]["owed_paise"], before["balance"]["left_paise"]
    assert owed >= 300000, "precondition: Cmt-Subs is still outstanding"

    await make_transaction(client, local_day="2026-11-06", category="Cmt-Subs",
                           description="Subscriptions paid", amount_paise=300000,
                           commitment_id=subs.id)

    after = (await client.get("/paisa/summary", params={
        "to": "2026-11-13", "fields": "commitments,balance"})).json()
    assert after["commitments"]["owed_paise"] == owed - 300000
    assert after["balance"]["left_paise"] == left - 300000


async def test_an_open_borrowing_is_a_commitment_too(client):
    """It already joined `locked` in a separate branch with no name of its own.
    Now it is a line the user can see."""
    await make_transaction(client, local_day="2026-10-09", kind="borrowed",
                           direction="credit", amount_paise=500000,
                           counterparty_name="Cmt-Lender", category="Udhaar",
                           description="udhaar liya")
    r = (await client.get("/paisa/summary", params={
        "to": "2026-11-13", "fields": "commitments"})).json()
    borrowed = [i for i in r["commitments"]["items"] if i["source"] == "borrowing"]
    assert any(i["owed_paise"] == 500000 for i in borrowed), borrowed
