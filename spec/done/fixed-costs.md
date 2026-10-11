# Fixed costs — fixed, and repeats

> **Superseded 2026-10-10 by `spec/done/commitments.md`:** the pool rule
> and the `fixed` / `repeats` flags are replaced by commitments the user owns.
> Kept as the reason the flags were the way they were.
>
> Shipped 2026-09-04. Replaces the money half of the archived commitments design
> with two flags on the row the ledger already has. No table, no form, no schedule.

## The problem, in the user's words

*"Salary aayi, aur ek-do din mein jo dena hota hai de deta hoon."* Rent, EMI,
money home, subscriptions: the same things every month, paid within days of
salary. Everybody knows they are going. The app does not — until each one is
paid it treats that money as spendable, so on the 1st the daily limit runs
about ₹2,000 a day high and slides down for two weeks as the payments land.

And the user decides what counts. A pizza is spending. Money to Papa is a gift,
but it is *committed* — the user wants to say so on that row, and to say
whether it happens again next month.

## Two flags on a payment

Every payment gets two switches in its ⋮ tray, in the chat table and the report
alike:

| Flag | Means | Effect |
|---|---|---|
| **Fixed** | this money was never spendable — committed, not a choice | the row leaves *spend* and joins *fixed*: the pale arc grows, the spent arc shrinks, the daily limit does not move (the money is gone either way) |
| **Repeat** | expect this again next month | next month, until a payment in this category lands, the amount is **locked** out of the pool, marked `· andaaza` |

Repeat needs Fixed; clearing Fixed clears Repeat. A row shows its state in its
sub-line: *fixed* · *fixed · repeats*. Nothing else on the row changes.

**Why columns and not the tag.** *Fixed* already existed as a tag — set by the
import, flipped by nobody. The word stays; the storage changes. A boolean column
is typed, indexable, and a contract the plugin and the agent can read and set
without parsing strings; `tags` stays for free text (`rakhi`, `trip`). And a
category cannot carry it: money to Papa is a gift one month and a fixed cost the
next, and only the person knows which.

## The rule

```
fixed(last)  = last month's rows with repeats = true, one line per category
paid(this)   = this month's rows with fixed = true
LOCKED       = Σ fixed(last) for the categories not yet paid this month      · andaaza
             + Σ open borrowings taken in earlier months (spec/done/udhaar-borrowed.md)
FIXED        = Σ paid(this)                                                  (measured)

pool         = income + repaid + borrowed − FIXED − spent − lent − paid back
limit        = (pool − LOCKED − goal) ÷ daysLeft
```

**A payment in a repeating category inherits the flags.** Rent said by voice in
September lands as Rent; because August's Rent row repeats, the new row is
fixed and repeats too — the user set the flags once. LOCKED drops by August's
amount, FIXED rises by September's real one. The limit moves only by the
difference. Unlock it and it is ordinary spending again, this month and next.

## The example, from the ledger

August's four repeating rows: Ghar ₹40,000 · EMI ₹10,000 · Subscriptions ₹3,000
· Rent ₹7,948 — ₹60,948.

| September | LOCKED | FIXED | limit |
|---|---|---|---|
| 1st, salary ₹1,03,000 lands, nothing paid | 60,948 · andaaza | 0 | (1,03,000 − 60,948 − 12,000) ÷ 30 = **₹1,002** |
| today's code, same day | 0 | 0 | ₹3,033 — ₹2,000 a day too generous |
| 3rd, *"papa ko 40000"* | 20,948 | 40,000 | ₹1,002, unchanged |
| 14th, rent came to ₹8,200 | 0 | 61,200 | ₹994 — the estimate gave way to the fact |
| 20th, *"gym 700"*, then ⋮ → Fixed → Repeat | 0 | 61,900 | unchanged now; October locks ₹700 from the 1st |

## Data

```sql
ALTER TABLE transactions ADD COLUMN fixed   BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE transactions ADD COLUMN repeats BOOLEAN NOT NULL DEFAULT false;
-- the import's four fixed-tagged rows become fixed + repeats; the tag is retired
UPDATE transactions SET fixed = true, repeats = true, tags = array_remove(tags, 'fixed')
 WHERE 'fixed' = ANY(tags);
```

`PATCH /transactions/{id}` takes `fixed` and `repeats`; the server clears
`repeats` when `fixed` goes false and sets `fixed` when `repeats` goes true. `POST /transactions` inherits both from
last month's repeating row in the same category when the body does not say.
`/deck` sends the two booleans on every transaction; the client stops reading
the `fixed` tag.

## Where it shows

- **⋮ on any payment:** *Fixed* / *Not fixed*, and *Repeat* / *Stop repeating*
  once fixed. Same tray as Edit and Delete, chat table and report.
- **The row's sub-line:** *fixed*, *fixed · repeats*.
- **Paisa ⋮:** *"Locked · ₹60,948 · andaaza"* under *Edit goal*, so the limit's
  third number is one tap away. Absent when LOCKED is zero.
- **The greeting, the day an income row lands:** *"Salary aayi. Repeat wale —
  Ghar ₹40,000, EMI ₹10,000, Rent ₹7,948, Subscriptions ₹3,000 — ₹60,948
  locked."* Once, that day. The assumption is read before it shapes a limit.

Nothing new on the card. The pale arc stays *fixed paid*, measured.

## Money in, and who agrees on it

Corrected 2026-09-13. The pool's inflow side is `income + repaid + borrowed`.
The month arc's denominator was a narrower, client-only sum — `kind ===
'income'` alone — so a friend returning ₹2,000 moved the agent's answer and
not the arc, and the two disagreed on screen in the same breath:

> agent: *"income ₹40,000 + Sunny ke ₹2,000 − expenses ₹651 = **₹41,349**"*
> arc: *Total ₹651 / **₹40,000***

`adapt()` in `frontend/src/data/api.ts` now mirrors the inflow side of the rule
above and cites it. Anything counted into the pool is money the user has, and
the arc it is measured against has to say the same.

## The audit, 2026-09-13

The card showed ₹1,33,000 in, ₹62,851 spent and a daily limit of ₹0, and the
user could not tell whether the app was broken or their month was. Five faults,
found by computing every figure from the raw ledger and comparing it against
each surface. The server's own arithmetic was right throughout; everything that
read it was wrong in a different way.

**1 · The agent invented the balance.** Asked *"kitna paisa bacha hai"* it
answered **₹1,29,149** against a true **₹59,149** — out by ₹70,000. It had
fetched `spent` and `income` and subtracted, and `spent` is *discretionary
expenses only*: fixed costs, lendings and repayments all dropped out of its
sum. A field whose exclusions are not in its name will be misread eventually.
There is now a `balance` field that answers the question whole — `left`,
`committed`, `free`, `came_in`, `went_out`, and what of it was fixed or lent —
and a prompt rule forbidding the subtraction.

**2 · The savings column printed a number nobody could reach.** The projection
strip's goal column showed the target verbatim, on the reasoning that the limit
is reverse-engineered from the goal so spending exactly the limit lands exactly
on it. True until `limit` is clamped at zero because commitments already exceed
the pool. Then the card promised ₹12,000 while the honest landing was ₹8,201.
It shows the real landing now and tags the column `max` instead of `goal` when
the target is out of reach.

**3 · A ring against a zero denominator.** *Today ₹200 / ₹0*. The month ring
already refused to draw against a zero total; the daily one did not. It reads
`nothing free` now, which is the actual state.

**4 · The number that explained everything was hidden.** `locked` — ₹50,948 of
last month's repeating costs not yet paid — is the whole reason the limit is
₹0, and it lived only inside the ⋮ menu. The card now carries a line under the
strip: *₹59,149 left · ₹50,948 already committed · ₹14,000 lent out*.

**5 · Lending changed nothing visible.** ₹10,000 to a friend leaves the pool
and moves the limit, but it is not spending, so it never reaches the Total
ring. It was correctly in People and in the pool, and invisible on the card
that the user was looking at. It is in the committed line now.

## Rules

- **Last month is the previous calendar month.** No rolling windows, no averages.
- **Category is the match** for inheritance and for "paid this month". Rent to a
  new landlord is still Rent.
- **A repeating category never paid this month stays locked all month.** A
  skipped EMI is the user's news to break — ⋮ → *Stop repeating* on last month's
  row, or just let the month end.
- **Fixed does not touch the amount, the category or the description.** It is a
  bit, not an edit.
- **Kinds other than expense are never fixed.** Income, lending, repayment have
  their own arithmetic.
- **Stopping a repeat that was set last month** needs last month's row, which
  the report cannot show yet (its ranges live inside the month). Until it can,
  the lock simply ends with the month. Not built around; noted.
- **On this dataset LOCKED is zero** until September rows exist under August.

## Decided against

| Option | Why not |
|---|---|
| A commitments table | Archived: one payment in two places, and forms nobody would fill |
| Keeping `fixed` as a tag | Set once by an import, flipped by nobody, and a string to parse. A column is a decision the user makes on the row, and a contract the agent can read |
| A new word, *lock* | *Fixed* already means this in the ledger and in the user's head. One word |
| Category decides what is fixed | Money to Papa is a gift one month and rent the next; only the user knows |
| Repeat without Fixed | Money that repeats but is a free choice is a subscription you have not admitted to. Fix it or let it be spending |
| Recurrence rules, periods, drift | `spec/notes.md` § Recurrence — one subtraction over last month's rows, not a schedule |
| Asking to confirm each lock in September | *"Ek-do din mein de deta hoon"* — the payment is the confirmation |

## Definition of done

The switches were verified in a cold browser tab on August's rows; the September
rows (LOCKED, the salary-day line, inheritance) were verified at the API and by
code review — the dataset has no month before August yet, so on the deck LOCKED
is zero until September's rows exist.

| Check | Expected |
|---|---|
| Migration | `fixed`, `repeats` columns; the four August fixed rows read true/true and lose the tag; the tag is read nowhere |
| ⋮ → Fixed on a ₹700 gym row | sub-line *fixed*; spent arc −700, pale arc +700; limit unchanged to the rupee |
| ⋮ → Repeat on it | sub-line *fixed · repeats*; *Not fixed* clears both |
| Anchor in September, August's four repeating rows, nothing paid | Paisa ⋮ *Locked · ₹60,948 · andaaza*; limit ₹1,002 with goal 12,000 |
| *"papa ko 40000"* logged in September | row lands fixed + repeats; LOCKED ₹20,948; limit unchanged |
| Rent logged at ₹8,200 | LOCKED −7,948, FIXED +8,200; limit moves by ₹252 ÷ daysLeft only |
| Anchor in August (current data) | LOCKED 0; no line in ⋮; limit as today |
| Salary-day greeting | the list and the total, once |
