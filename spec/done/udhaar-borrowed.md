# Udhaar borrowed — the other leg, and two tabs instead of Pending

> Shipped 2026-09-04. Completes `spec/done/udhaar-repayment.md`: money the
> user *took* from a person and owes back. Same table, same repayment row,
> opposite direction.

## The problem

The ledger has `kind = 'borrowed'` and nothing reads it. A friend's ₹2,000 you
still owe is invisible: not on the report, not in the arithmetic, no way to say
*"wapas de diya"*. And the report's *Pending* tab only ever meant lendings.

## What it does

**Two tabs, no Pending.** The Paisa report's tabs become *All · Lent · Borrowed ·
categories*. *Lent* is today's Pending tab. *Borrowed* is its mirror: what you
owe, oldest first, then what you paid back, each with Undo.

```
BORROWED     Amit se liya     2 Sep · 2 days        ₹2,000     ⋮ Paid back · Edit · Delete
             Amit             paid back 30 Aug      ₹500       ⋮ Undo
```

**Paid back** opens the one-field prompt, the amount you still owe pre-filled;
Enter saves a `repayment` **debit** with `settles_id` on the borrowing. Partial
allowed; more than owed refused. There is no *Gift* on this side — if a lender
forgives a debt, that is their news and rare enough to be an edit.

**A way in without the agent.** Each tab ends with an inline *+ Lent* / *+
Borrowed* row: who, and how much. Save writes the row with `counterparty_name`;
the server finds or creates that person. Two fields, because nothing else can
create a lending or a borrowing today — the same allowance the Profile and
Pantry pages have. When the agent lands, *"Amit se 2000 liye"* replaces it.

## The pool: borrowed money is cash now and a fixed cost later

The first cut said borrowed money should never touch the pool. The user's own
situations showed why that is wrong: *"I had ₹200 left and five days to go, so I
borrowed ₹5,000 — my limit has to go up, that is why I borrowed."* And the debt
does not vanish; it becomes a known cost of the month it is due — *"generally
next month"* — exactly what `spec/done/fixed-costs.md` calls locked.

**Decided:** money that came is here, money that left is gone, and what you know
is going is locked. Borrowing is no exception.

| | pool | LOCKED | limit |
|---|---|---|---|
| borrow ₹5,000 on the 25th | +5,000 | – | **up** ₹5,000 ÷ days left — that is the point of borrowing |
| spend it (or ₹15,000 incl. your own ₹10,000) | −15,000 | – | down by the spend, as any spend |
| 1st of next month, still owed | – | **+5,000** | held out until paid — the debt is a fixed cost of this month |
| pay it back | −5,000 | −5,000 | **unchanged** — the same neutrality as rent |
| pay it back inside the month it was borrowed | −5,000 | – | back where it was before the borrowing |

So the ₹15,000 purchase in the first situation reads exactly as it happened:
₹10,000 of your money and ₹5,000 of Amit's went, and next month Amit's
₹5,000 is spoken for before the month starts.

**Due month.** No date is asked. An open borrowing is locked in every month
after the one it was taken in, until paid. Returned inside the same month,
it never locks at all. A due date on the row is a later decision, if a
borrowing ever runs long enough to want one.

## Data and API

No schema change: `kind = 'borrowed'`, direction `credit`; its repayment is
kind `repayment`, direction `debit`, `settles_id` → the borrowing.

Server rules (extend the repayment guard):

- a repayment must point at a live `lent` **or** `borrowed` row; its direction
  must be the opposite of that row's (`credit` pays a lending, `debit` pays a
  borrowing); more than what is out is refused with the amount;
- deleting a lending **or** borrowing that has repayments is refused;
- `counterparty_name` on a POST is resolved to the user's counterparty row,
  created if new; a person who lent you money is a peer (`is_peer`).

Client: the open list carries a `leg`, `lent | borrowed`; each repayment
carries the leg of the row it settles, so the two tabs split one list.

## Where it shows

- **Report → Lent / Borrowed** tabs, as above; the tile becomes *Udhaar*:
  *out ₹4,000 · owe ₹2,000*.
- **Paisa ⋮ Locked line and the salary-day greeting** include open borrowings from earlier months, by name: *Amit ko wapas ₹5,000*.

## Decided against

| Option | Why not |
|---|---|
| Borrowed money never touching the pool (the first cut) | Built for an afternoon: it lowered the limit exactly when the user had borrowed to raise it. Cash is cash; the debt is a locked cost of the month it is due |
| Keeping one *Pending* tab with signs | Two directions in one list, told apart by a minus sign, is the reading error the tab exists to prevent |
| *Forgiven* on a borrowing | Rare, and someone else's decision; an edit covers it |
| Waiting for the agent to create rows | The tabs would sit empty for a phase; two fields is the price of a working feature now |

## Definition of done

Verified in a cold browser tab: + Borrowed → Paid back → Undo → Delete on a test
row, the limit rising on the borrowing and returning on the pay-back; the server created the counterparty as a peer and
soft-deleted both rows. Refusals (over-payment, wrong direction, delete with
repayments) verified at the API.

| Check | Expected |
|---|---|
| Report tabs | All · Lent · Borrowed · categories; no Pending |
| + Borrowed → *Amit* · 2000 | a `borrowed` credit row; Borrowed tab shows it with age; the limit rises by 2,000 ÷ days left |
| ⋮ → Paid back → Enter, same month | a `repayment` debit with `settles_id`; row moves to paid back; limit back where it was before the borrowing |
| Anchor in the next month, still owed | Paisa ⋮ Locked includes *Amit ko wapas ₹2,000*; limit holds it out |
| Undo | repayment soft-deleted; row owed again |
| Paid back with more than owed | refused, amount named |
| + Lent → *Amit* · 500 | a `lent` debit row; Lent tab shows it; limit drops by 500 ÷ daysLeft |
| Tile | *Udhaar* — out ₹4,000 · owe ₹2,000 |
| Delete a borrowing with a repayment | 409, undo first |
