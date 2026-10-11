# Commitments

> Status: **archived** 2026-09-04 — see `spec/notes.md` § Commitments. Kept as the design
> in case it comes back; nothing here is owed.
> Surface: backend + frontend (no new mode)

## The problem

Everything Cortex knows is in the past tense or today. It can say what was spent
and what is due today, and nothing at all about the fourteenth of next month.

So the app is silent on exactly the things that hurt when missed: PUC expiring,
bike insurance lapsing, ITR on 31 July, an EMI, a friend's ₹4,000. These are not
hard to remember individually. They are hard to remember *all of*, which is what
makes them a management problem rather than a memory problem.

## The idea

**A commitment is anything with a future date and a consequence.**

The Substrate note introduced this entity as a money thing — EMI, rent, gym fees.
That was too narrow. Money is one shape of it:

| Shape | Examples |
| --- | --- |
| Documents | PUC, vehicle insurance, DL renewal, passport, rent agreement |
| Money | EMI, premium, ITR, advance tax, FD maturity, udhaar |
| Health | Prescription running out, a test due again, an insurance claim window |
| Things | Laptop warranty, bike service, AC service |
| People | Something you said you would do |

One entity, one schedule, one reminder path. **No fourth mode** — a document
expiring in eight months has no daily rhythm, so it fails the deck's own test.
It lives in **Your data**, and speaks up when the date gets close.

## Where a commitment comes from

The good path is not a form. It is **a follow-up on something already captured**.

When a payment lands that looks like it creates an obligation, the agent asks one
question — at capture time, when the context is still in your head:

```
you    bike insurance 6400 hua
agent  Bike insurance ₹6,400 log kiya · Vehicle
       Kitne saal ka hai?                    [1 saal]  [2 saal]  [3 saal]

you    [1 saal]
agent  Theek hai — 22 Aug 2027 se pehle yaad dila dunga.
```

Two things make this work and both are worth stating:

- **One question, not a form.** If it takes four fields, it will not be answered.
  Anything else the agent needs, it infers or does without.
- **It only asks when it would matter.** Insurance, tax, a subscription, a
  renewal — categories where a date exists. A chai does not get asked about.

The other entry points are the plain ones: saying it outright (*"papa ki dawai 5
tarikh ko khatam"*), and later, a document scan.

## What it looks like

```ts
interface Commitment {
  id: string;
  title: string;              // "Bike insurance"
  kind: 'document' | 'money' | 'health' | 'thing' | 'person';
  dueOn: string;              // the date it lands
  amount?: number;            // money shapes only
  repeat?: 'yearly' | 'monthly' | 'half-yearly' | null;
  remindAt: string[];         // computed, not entered
  sourceId?: string;          // the transaction it was born from
  closedAt?: string;
}
```

`remindAt` is **derived from the kind, never asked**. A legal renewal wants
warning far ahead; a friend's loan wants a nudge the week of. Asking the user to
choose reminder offsets is asking them to do the app's job.

| Kind | Reminders before |
| --- | --- |
| Document / legal | 30 days, 7 days, on the day |
| Money | 7 days, on the day |
| Health | 5 days, on the day |
| Thing / person | 3 days |

## How the user hears about it

Three channels, in order of how intrusive they are:

1. **In conversation.** The greeting already adapts to the day. A commitment
   inside its reminder window belongs there — *"PUC 12 din mein khatam."* Free,
   and it fits the premise.
2. **In Your data.** A section, sorted by date. The place you go to look rather
   than the place that tells you.
3. **Push notification.** Only for the on-the-day and 7-day marks, and only for
   `document` and `money`. This is the one channel that can annoy, so it gets the
   smallest surface.

## Rules and edge cases

- **A missed commitment does not disappear.** It stays, marked overdue, until
  closed. Silently dropping the thing you failed at is the worst behaviour a
  manager can have.
- **Repeating commitments roll forward on close**, not on the due date — closing
  is the signal it actually happened.
- **Never two reminders for the same thing in one day**, however many rules fire.
- **A commitment with no date is not a commitment.** It is a task, and it belongs
  in Kaam.
- The reminder question is **skippable**, and skipping never asks again for that
  transaction. An unanswered question that comes back is worse than no question.

## Scope — deliberately small

This is not a subscription manager, a document vault or a legal-compliance
product. It is one entity that gives the app a future tense.

The thing to resist: once commitments exist, it is very easy to slide into
"manage all your subscriptions", "store all your documents", "track all your
policies". Each is a product of its own and none of them is this one. **If a
feature needs a screen of its own, it has left the scope.**

## Testing

- A capture in a dated category asks its one question; a chai does not
- Skipping the question logs the payment cleanly and never re-asks
- Reminder offsets are derived correctly per kind
- A commitment inside its window appears in the greeting, once per day
- A missed one shows as overdue rather than vanishing
- A yearly commitment rolls forward on close, not on its due date
- Two rules firing on one day produce one reminder

## Definition of done

1. Commitments can be created from a capture follow-up, and by saying one out
   loud.
2. Reminder dates derive from kind — the user is never asked to set an offset.
3. The greeting surfaces anything inside its window, at most once a day.
4. Your data has a Commitments section, sorted by date, with overdue at the top.
5. Overdue commitments persist visibly until closed.
6. Repeating ones roll forward on close and only on close.
7. Push fires only for `document` and `money`, only at 7 days and on the day.
8. No new mode, no new screen beyond the Your data section.

## Decided against

| Option | Why not |
| --- | --- |
| A fourth mode | No daily rhythm. Fails the deck's own test |
| A form to add one | Forms are the thing this product exists to avoid |
| Asking the user to pick reminder offsets | That is the app's job. Nobody knows how many days' warning they want for a PUC |
| Reminding for every kind by push | Push is the one channel that can make someone uninstall. Reserve it |
| Auto-detecting renewals from statements | Guessing wrong about a legal deadline is worse than staying quiet |

## Open

- Does the capture follow-up interrupt the flow too much? It costs one tap at a
  moment the user came to do something else. Worth watching once it is real.
- Document scanning — genuinely useful for expiry dates, and a much bigger
  feature. Deliberately out of v1.
- The **Work** side of the same idea: calendar, email and Linear as inbound
  sources so Kaam knows about meetings and assigned issues without being told.
  Same "app gets a future tense" theme, but a different spec.
