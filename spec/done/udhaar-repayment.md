# Udhaar repayment — "wapas aaya", by hand

> Shipped 2026-09-04. A slice of `spec/udhaar.md`: §6 (repayment) and §7 (budget
> treatment), done as a manual action on the report. Detection of a lending
> from a payment's shape (§4) and auto-matching a notification credit wait for
> phase 3; reminders (§8) wait for Android push.

## The problem

Lendings are in the ledger and the *Pending* tab lists them, but there is no
way to say *it came back*. The June ₹4,000 to Dost 2 has been out for 72 days
and the only way to close it today is to delete the lending — which erases the
fact that it happened and the person's record with it.

The second half of the problem is arithmetic. The daily limit today treats
money that is out with a friend as if it were saved toward the goal. The moment
repayments become a thing people do, that has to be settled properly (see
*Budget treatment*).

## What it does

1. **Pending tab, ⋮ on a lending → Repaid · Gift**, next to Edit and Delete.
2. **Repaid** opens an inline editor under the row — the Profile page pattern —
   with the amount pre-filled to what is still out and the date set to today.
   Enter saves: a `repayment` credit with `settles_id` pointing at the lending,
   the same counterparty, description *"<name> se wapas aaya"*. A smaller
   amount is a **partial** repayment: the row stays, showing the remainder.
3. A settled lending moves to a **Settled** section below the pending ones,
   muted — *"Dost 1 · ₹7,000 · repaid 12 Aug"*. Its ⋮ has **Undo**, which
   soft-deletes the repayment and puts the row back. That is §6's undo without
   a 24-hour timer: it is a row, so it can be undone whenever.
4. **Gift** turns the lending into an expense in *Logon ko diya* (a category the
   ledger already has, four rows). It leaves Pending and joins spend. No new
   column; `kind` changes.
5. **Age on every pending row**: *"72 days"*, from full dates. The card's
   `PendingItem` carries only a day-of-month today; it gains the date.
6. **Server-side:** the first repayment from a counterparty flips its
   `is_peer` to true — the model's own rule, *"flips the first time money comes
   back, and never flips back"*.

## Budget treatment — the arithmetic, decided

**Money that left is gone; money that came is here.** A lending is cash out in
the month it happens, so the limit drops then. A repayment is cash in, in the
month it arrives — next week or three months later — so the limit rises then.
What is pending never counts toward the goal: a friend's promise is not savings,
and nothing guarantees it lands this month.

```
pool     = income + repayments − fixed − spent − lent     (this month)
reserve  = goal                                           (pending does not reduce it)
limit    = (pool − LOCKED − reserve) ÷ daysLeft
```

Real numbers: pool ₹19,264 (August's ₹10,000 lent came back inside August, so
the two legs cancel) · goal ₹12,000 · 4 days left → limit **₹1,816**.

That is ₹1,000 a day *lower* than the deck shows today. The current code lets
June's ₹4,000 count toward the goal as if it were already saved. It is with
Dost 2, so it is not. The number the deck shows is the flattering one; this is
the honest one, and it is the one worth showing plainly.

| Event | pool | limit |
|---|---|---|
| lend ₹4,000 this month | −4,000 | −₹1,000/day — the money left |
| it comes back this month | +4,000 | back where it was |
| June's ₹4,000 comes back in September | +4,000 in September's pool | +₹4,000 ÷ September's days left |
| gift it instead | 0 — lent becomes spent | unchanged; it left when it was lent, pending just stops expecting it |

This supersedes `spec/udhaar.md` §7 ("daily limit par asar NAHI") and its
track-record nuance: nothing pending is ever counted, so there is no track
record to judge for the limit. Per-person history stays useful for reminders
and for the agent's detection, not for arithmetic.

`projectedSavings` in the report computes `remaining` with its own variant
(`+ pending`). After this it uses the same pool — one function, both places.

## Data

No schema change. `kind='repayment'`, `direction='credit'`, `settles_id`,
`is_peer` and the *Logon ko diya* category all exist; the import already wrote
three real repayments this way (12 Aug: ₹7,000 · ₹1,000 · ₹2,000, three
people, three exact matches — §6's test case, already in the ledger).

Client: `PendingItem` gains `date` (ISO) and a settled list; the pool moves into
one function shared by the limit and the projection.

## Rules and edge cases

- **Pool is the month; pending is all time.** A June lending is pending in
  September; June's expenses are not September's pool.
- **More than what is out is refused** with a hint — *"more than the ₹4,000
  out; log the extra as income"*. §6's "close and treat the extra as a new
  credit" is for auto-matched notifications, where nobody typed the number.
- **Partial** keeps the row pending with the remainder; the Settled section
  lists each partial with its amount and date.
- **Gift after a partial:** the lending row becomes an expense of its full
  amount while the repayment credit stays — net spend is the remainder, pending
  is zero. No special case needed; it falls out of the arithmetic.
- **Deleting a lending that has repayments is refused** (409, *"undo its
  repayments first"*). A cascade would be convenient and invisible; a refusal
  is one tap more and never surprises.
- **Borrowed (udhaar liya)** is not in scope. The Pending tab's negative branch
  stays unused until it is.
- **Reminders** are phase 6 push. The age label is all of §8 for now.

## Decided against

| Option | Why not |
|---|---|
| *"wapas aaya 4000"* in the composer | The agent's job (phase 3); and a quick action through the agent bar was rejected on sight in the Profile work |
| Auto-close from a notification credit (§6) | Needs notification capture (Android) and the matching logic; the manual action is the thing it will later automate |
| A 24-hour undo window | A repayment is a row; deleting it is the undo, at any time |
| Editing the lending's amount to 0 | Destroys the record that money was lent and the person's history (§7 per-person stats) |
| Cascading repayments on delete | Refusal is explicit; a cascade removes rows nobody looked at |

## Definition of done

Verified in a cold browser tab against the running API on the deck's anchor day
(28 Aug, the last data day). Gift and the partial-repayment path were verified
by code review and the server guards, not clicked through.

| Check | Expected |
|---|---|
| Pending → ⋮ → Repaid → Enter, ₹4,000 pre-filled | a repayment credit with `settles_id`, counterparty inherited from the lending; Dost 2 moves to Settled *"repaid 28 Aug"*; pending ₹4,000 → ₹0 |
| Deck today, once the pool counts lent and repaid | limit ₹1,783 (was ₹2,783 with June's ₹4,000 posing as savings) |
| Limit after Dost 2 repays ₹4,000 | ₹2,783 — up ₹1,000/day, the month the money arrives |
| Undo on the settled row | repayment soft-deleted; row back in Pending as *24 Jun · 65 days*; limit back to ₹1,783 |
| Repaid with 1,000 | Pending shows ₹3,000 remaining; Settled shows ₹1,000 |
| Repaid with 5,000 | refused with the hint; nothing written |
| Gift | leaves Pending; appears in *All* as a *Logon ko diya* expense; limit unchanged |
| Age label | *"65 days"* on the June row on the 28 Aug anchor, from dates not day numbers |
| Counterparty | Dost 2's `is_peer` flips true on the first repayment |
| DELETE a lending with repayments | 409, message says to undo them first |
