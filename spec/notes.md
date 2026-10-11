# Notes — deferred decisions

Things decided **not to build yet**, with the reason and what would trigger
building them. Not a backlog: `feature.json` is the backlog. This is the smaller,
easier-to-lose set — the "we thought about this and chose to wait" list.

Without it, a deferred decision looks identical to an overlooked one, and someone
either rebuilds the argument from scratch or quietly does the thing we decided
against.

**Format:** what, why deferred, what would change our mind, and where the
argument lives.

---

## `places` — created, but not yet populated

**Built.** The table exists and `transactions.place_id` points at it. Nothing
writes to it yet: capture has no location source, and the workbook had no
coordinates.

**Why the table came first.** A place is *where you were*, a counterparty is
*who you paid* — Mohan Lal's shop is both, Rapido is a counterparty with no
place, a food court is one place with many counterparties. Folding them into one
table would have needed unpicking later.

**Raw coordinates do not live on the transaction.** ~~They go in
`predictions.signals`~~ — **reversed 2026-09-07**, see
`spec/in-progress/places.md`: `predictions` is the agent's guess-log, so a
payment it never guessed about has no row and its fix has nowhere to live. Those
are exactly the fixes that discover a new place by repeating. The fix goes on
the transaction, which is where *what happened* belongs; a wrong match is still
redoable because `place_id` can be cleared and recomputed from it. Resolution is gated on GPS accuracy — see `ACCURACY_LIMIT_M`
in `backend/app/models/paisa.py`: a 500m fix covers a whole market, so inferring
a shop from it would be inventing data.

**Shipped 2026-09-07** — `spec/done/places.md`. The user-facing map and list
exist and pins are dropped by hand; `transactions.lat/lng/fix_accuracy_m` is
where a captured fix will land. **Clustering points into named places is still
missing** and waits for a real location source: three separate days inside one
radius is the rule, recorded but not built.

**Where:** `spec/done/paisa-data-model.md`, `spec/substrate.md` §5.

---

*Two tables, two sections:* the 2026-09-06 idea of showing them together under
**People & Places** was dropped on the 07th. A map and a list are different
interactions, and the shared add-and-approve rule is a policy they can both
follow without sharing a screen.

## Cash-spend nudge from dwell time

**Deferred to the places feature.**

Cash payments produce no notification, so they are invisible unless typed in. But
if the phone knows you were at a known counterparty's location for more than
~30 minutes and no digital payment landed, the agent can ask once:
*"Mohan Lal pe kuch kharch hua?"*

**Why deferred.** It needs place identity (not just raw points), dwell-time
detection, and a known-counterparty-to-location mapping — none of which exist.

**What would change it.** Enough coordinate history to cluster into real places —
which is the argument for storing points, precisely, from day one.

**Where:** this file; the places feature has no spec yet.

---

## Event log for sync

**Deferred.** Incremental sync uses `updated_at` plus soft deletes for now.

**Why.** An event log's advantage is one monotonic cursor across every table and
a sequence the database assigns rather than the application. With one user, a
handful of tables and no offline client yet, `WHERE updated_at > cursor` on each
table does the same job with less machinery — and soft deletes mean deletions are
visible to that query, which is the failure mode the log is usually there to fix.

The earlier argument for building it early — "every write handler must emit an
event, so retrofitting means touching all of them" — was weaker than it sounded.
SQLAlchemy's `after_insert` / `after_update` mapper events can emit them from one
place, so no handler changes when it does arrive.

**What would change it.** The Android app holding local SQLite, or a second
device. At that point one cursor beats five.

**Where:** `spec/api.md` (`/events`), `spec/substrate.md` §9.

---

## Background location, and what distribution would cost

**Building with precise location, for one user.** The developer and the user are
the same person, so permissions are granted freely and `lat` / `lng` are captured
at payment time.

**The problem if this is ever distributed.** A payment notification arrives while
the app is not open, so capturing location at that moment is
`ACCESS_BACKGROUND_LOCATION` — the hardest permission Google grants. It needs a
separate declaration, a written justification that the *core* feature cannot work
without it, and a demo video. Rejections are common, and "guess which shop this
was" is a weaker justification than Uber's "show the driver coming to you".

Two further constraints that apply even when granted: Android 12+ lets a user
downgrade any precise request to approximate, and prominent in-app disclosure is
required before the system dialog.

**Why this is not a blocker now.** The app needs a *single fix at the moment of a
payment*, not continuous tracking — a much narrower ask, far cheaper on battery,
and easier to justify than a location trail. And the data model does not change
either way: `lat` / `lng` are nullable, so without the permission the columns stay
empty and everything that depends on them degrades rather than breaks.

**What to do about it.** Keep location capture behind one capability check, so
turning it off is configuration rather than redesign. Decide distribution before
building the places feature on top of it.

**Where:** `spec/done/paisa-data-model.md`, `spec/paisa-categorise.md` §5.8.

---

## Recurrence for fixed costs

**Not building.** Rent, EMI, subscriptions and money sent home are ordinary
transactions with a category. No schedule, no recurrence rules, no generated
"expected" rows.

**Why.** Recurrence does not model them honestly — rent covers a period from one
date to another, EMI likewise, and a subscription's renewal date moves. Encoding
that costs recurrence rules, period boundaries and drift handling, for a total
that is one `SUM ... WHERE category IN (...)` away.

**Decided: the Paisa card's pale arc becomes a measured number.** It currently
draws money already committed from a hardcoded constant — a forecast. It now
means *"fixed costs already paid this month"*, computed from real rows.

The visible consequence: on the 1st the pale arc is empty, where the constant
made it full from day one. That is the honest reading, and it matches the app's
existing rule against showing figures it cannot support.

**Amended 2026-09-04.** Still no recurrence rules — but *what was fixed last month
is locked this month until paid*, one subtraction over real rows, shown
`· andaaza`. The user's own habit made the case: salary lands, the fixed costs go
within days, and everyone knows they are going. `spec/in-progress/fixed-costs.md`.

**Where:** `spec/archive/commitments.md`, `spec/done/paisa-data-model.md`.

---

## Sets, reps and workout plans

**Deferred.** `exercises` is a library for suggestion; a logged session stays
free text with an optional duration.

**Why.** The tracker recorded movement on 8 days out of 24, as prose —
`Gym — Workout B (back)`, `Rest — office din`. No set, no rep, no weight appears
anywhere in it. Building a sets/reps schema now means designing against an
imagined user rather than the real one, and the same argument killed the
`meal_slot` enum.

The named routines (`Workout A`, `Workout B`) are the natural middle level
between an exercise and a session, and a `workout_plans` table is the obvious
shape. Two named plans across 24 days is not enough to design one.

**What would change it.** Sessions actually being logged exercise by exercise —
which is itself the signal that progressive overload is being tracked, and that
is when sets, reps and weight start meaning something. Until then a session is
*did it, this long*, which is what the streak strip reads.

**Where:** `spec/done/diet-data-model.md`.

---

## Recovering a day that was not logged

**Decided, not yet built.** `days.log_complete` records the answer; this is how
the answer is obtained. Written down now because the workbook's most serious
finding has no mechanism behind it yet — *"adhoore din ka koi recovery mechanism
nahi hai"*, marked CRITICAL, after 7 Aug logged breakfast and nothing else.

**Two cases, and they need different questions.**

*Partly logged.* 7 Aug: breakfast at 580 kcal and nothing after. The app asks
to confirm rather than to complete — **it may genuinely have been that day's
food.** If the user says that was all, `log_complete = TRUE` and 580 kcal is a
fact, not a gap. Treating a light day as a failed log would be the app deciding
it knows better than the person who ate.

*Not logged at all.* 16 Aug: no rows. Two possibilities, and only the user can
separate them — nothing was eaten, or nothing was written down. If it was a
fast, that is a `fasting` habit log, and the day is then complete with no meals
and no macros. The NULL day is correct; it just needed a row to say so.

**How it gets asked.** One or two notifications, then the agent raises it inside
ordinary conversation — *"aapne 16 ko kuch log nahi kiya tha"* — whenever the
user next talks about something else. This is the advantage of the premise: the
conversation is always open, so a missed day does not need its own screen, its
own inbox or a badge. It needs a sentence, at a moment the user is already there.

So this is prompt design, not schema. The column exists; what to do with a NULL
belongs in the agent's instructions.

**What would change it.** Missed days piling up faster than conversation can
clear them, which would mean the nudge is too quiet — not that the app needs a
recovery screen.

**Where:** `spec/done/diet-data-model.md` (`days.log_complete`).

---

## Auth and the `users` table

**Deferred until after kaam, designed together with `profile`.** Until then
`user_id` is a plain TEXT column filled with the constant `'me'`, and requests
are trusted — there is no login and no token per user.

**Why.** The profile decision already made applies here word for word: designing
the user model one mode at a time guesses at what it must hold. Auth is the same
table plus the question *how does a request prove which user it is* — password,
OTP, device key — and none of that changes any schema built so far. Every
personal table already carries `user_id`, so auth arrives by giving that column
a real foreign key and a login flow, not by touching data.

**What would change it.** A second real user, or distributing the APK to
friends — whichever comes first.

**Being closed now (2026-09-15).** Sending it to friends is the next thing, so
the trigger has fired. `spec/in-progress/sign-in.md` is the draft: Google as the
one door, an opaque session token on the existing seam, an invite list. The
table half of this entry shipped a while ago — `'me'` is gone and `user_id` is a
real foreign key everywhere — so only the lock was ever still owed.

**Where:** `spec/done/diet-data-model.md` § Whose row is this / § Targets;
`spec/in-progress/sign-in.md`.

---

## A second door — email, password, magic link

**Not building.** Sign-in is Google only (`spec/in-progress/sign-in.md`).

**Why.** Every user of this app is on Android, where a Google account is a
given, and Credential Manager makes the same token flow one call there. A
password costs a hash, a reset flow and therefore a mail sender — three pieces
of infrastructure for a door nobody would prefer.

**What would change our mind.** An invited person who will not use Google. The
answer then is a **magic link**, not a password: it needs the mail sender but no
hash and no reset flow, and it reuses the sessions table exactly as it is. A
password is the last resort, not the second option.

**Where:** `spec/in-progress/sign-in.md` § Decided against.

---

## Row-level security

**Deferred to the auth work (after kaam, with the users table).** Until then the
`user_id` filter lives in queries, filled with a constant.

**Why.** RLS only binds when the connecting role is not the table's owner — the
owner bypasses policies. The app currently connects as `cortex`, which owns
everything, so enabling RLS today would be decoration. A dedicated low-privilege
app role is part of the auth work, and RLS lands with it.

**What would change it.** A second real user, or auth landing.

**Where:** `spec/done/diet-data-model.md` § Whose row is this.

---

## The daily limit is ledger arithmetic; balance checks are for the gap

**Decided, after two failed detours.** The limit derives from transactions
alone — `(income − fixed − spent − goal shortfall) ÷ days left` — trusting the
ledger as the complete story. The stated bank balance never feeds the limit:
a stored constant went stale silently, and a ledger roll-forward produced
₹1,984 against a real balance above ₹10,000, because the ledger cannot know
which rows were cash (`method` blank on 49 of 73).

`balance_checks` keeps its original job from the data-model spec: **the
reconciliation gap is measured against it** — plan from the ledger, audit
against the bank. The gap lives in the report, marked `andaaza`, never in the
limit.

**Still deferred to the chat agent (phase 3):** when the latest check ages
past ~5 days, the agent asks once, in conversation — *"bank balance check
karke bata do?"* — and the answer becomes a new row. Same shape as the
missed-day recovery: a sentence, never a screen.

**Where:** `spec/done/paisa-data-model.md` (`balance_checks`), `frontend/src/state/usePersonaOS.ts` (`dailySpendLimit`).

---

## Local-first vs the agent knowing your data

**Current decision: the server holds the data, full stop.** No device database,
no sync, no offline queue — the app talks to Postgres and that is the whole
story until the Android app exists. Recorded so it is a decision rather than an
omission.

**What device-local would mean, when it arrives.** SQLite on the phone as the
source of truth for reads (`spec/substrate.md` §9), so a glance never waits on
the network; writes queue locally and drain when the connection returns, which
is also what makes a retry safe. The write endpoints being built now are
exactly what that queue would POST to, so nothing is wasted either way.

**The tension, named now because it will decide an architecture later.**
`spec/agent-everywhere.md` wants the Claude app to answer *"aaj ka limit kya
hai"*. If the phone is the only place the data lives, the server has nothing to
answer with, and that feature needs the phone awake and reachable. If the
server holds a readable copy so the agent can answer, the trust argument for
local-first is weakened — the data is on someone's machine after all.

Options, none free, none chosen:

| | |
|---|---|
| **Phone only** | Strongest trust. Agent-everywhere works on the phone and nowhere else |
| **Phone is truth, server holds a readable mirror** | Agent works everywhere; the mirror is the thing a breach would take |
| **Phone is truth, server mirror is encrypted with a device key** | Server cannot read it — but then neither can the agent, so it buys backup, not answers |
| **Answers computed on the phone, sent as answers** | The server sees `limit = ₹2,978`, never the rows. Narrow, and probably the honest middle |

That last row is worth thinking hardest about: the agent does not need the
ledger, it needs *today's numbers*. A phone that pushes a small daily digest
gives the Claude app something true to say while the rows stay home.

**Why the prototype still uses a server database.** The web prototype is
throwaway by design (`CLAUDE.md`), and browser SQLite is real machinery for
something we plan to discard. The write endpoints built now are not wasted
either way — they are exactly what the phone will POST to when it syncs.

**What would decide it.** Building agent-everywhere for real. Until then the
schema is identical in both worlds, so nothing is being locked in.

**Where:** `spec/substrate.md` §9, `spec/agent-everywhere.md`,
`spec/done/ledger-writes.md`.

---

## Pantry — quantity ledger, with status derived from it

**Decided, reconciling two specs.** `spec/diet-logging.md` §5 argues for
status-stepping (`full · ok · soon · out`) and against quantities — *"nobody
knows they have 340 g of rice"*. `spec/done/diet-data-model.md` then built a
quantity **ledger** (`pantry_moves`). They are not in conflict once the words
line up:

- The ledger never asks for a quantity. It sums what arrived and what recipes
  spent — the very inference §5 asks for. Nobody types 340 g.
- Foods with **no inbound move** are exactly §5's honest case: present, amount
  unknowable (the family's atta). They get no arithmetic and no status.
- **Status is derived, not stored:** `out` at ≤ 0, `soon` at ≤ `reorder_at_g`,
  `ok` above it, `unknown` with no moves. The step labels the user reads are
  the same; the storage under them can say *why*.

So the pantry UI shows §5's four words, computed from the ledger. `PantryItem`
as a stored status is not built.

**Where:** `spec/diet-logging.md` §5, `spec/done/diet-data-model.md` § pantry.

---

## Shared memory — archived

**Archived 2026-09-26.** The design is in `spec/archive/shared-memory.md`.
Spica's own memory — the `memories` table, `/memories`, the agent's
`remember` tool — is unaffected; what is parked is *sharing* it with Claude
Code, the Claude app, ChatGPT and Gemini.

**Why parked:** to keep the first MCP server to one job, work sync. Nothing in
work sync depends on it, and the design had already been cut down to a small
thing — read-only, a `SessionStart` hook reading live, no reconcile routine —
so parking it loses little.

**What stays true from the earlier note:** no hosted assistant exposes an API
for writing into its own memory, and pushing personal data into one would be
the export leak the product refuses. Pull-by-tool remains the only shape for
them.

**What would change our mind:** retyping the same facts to Claude often enough
to be annoying; or Spica becoming a claude.ai connector for another reason
(OAuth on `/mcp`), which makes the Claude-app half nearly free. The Claude Code
half is one hook on a plugin that work sync builds anyway.

---

## Repo checkboxes as a task source — archived

**Archived 2026-09-27.** The design is in `spec/archive/repo-task-scanner.md`
(formerly `task-sync.md`): scan repositories for `- [ ]` lines, write an
invisible `<!--cx:a7f2-->` marker into each so a task survives rewording, and
reconcile ticks between the file and the phone.

**Why:** the user's work tasks arrive in Linear and in meetings, not in repo
checkboxes — `spec/done/work-data-model.md` found two real checkbox tasks in
this repo and none in the office repo. And this was the most complicated part
of the old design: a tool writing into source files, and a conflict table for
when a file and the phone disagree. `spec/work-sync.md` needs neither.

**What would change our mind:** a repo where tasks genuinely live as
checkboxes. It would come back as a read-only **document** source in
`work-sync.md`'s terms — read, extract, never write the file — with no markers.

---

## Gmail as a work source — deferred

**Deferred 2026-09-27.** `spec/work-sync.md` starts with Linear and Wispr Flow
only. Email is a **document** source in that spec's terms, so adding it is one
instructions file and a connector on the routine — no server change.

**Why:** email is where false positives come from. Most mail asks nothing of
the person, and the mail that does is phrased as anything but a task. Two
sources the user trusts come first, so a bad run is easy to attribute.

**What would change our mind:** Linear and Wispr running clean for a few weeks,
or a task the user missed because it only existed in an email.

---

## Slack as a work source — deferred

**Deferred 2026-09-27.** The landing page's work pipeline shows Slack beside
Gmail as a source that is next — dashed, carrying nothing. Neither is built.
Slack would be a **document** source like a meeting: a channel's messages
read, the asks addressed to the person extracted, the message ids stored.

**Why:** the same as Gmail — most of a channel asks nothing of anyone, and the
asks that exist are phrased as conversation. Linear and Wispr Flow come first.

**What would change our mind:** the Gmail source running clean, since it is
the same shape; or a claude.ai Slack connector the routine can already read.

---

## A card for the work-sync turn — deferred

**Deferred 2026-09-27.** `work_sync_finish` writes the run's turn as text,
narrated like a scheduled job's. It does not yet carry a card listing the tasks
it created.

**Why:** Kaam already shows the tasks, and no task card exists in the thread
yet (`spec/agent.md`). The turn's `tool_trace` stores the created and updated
task ids, so a card can be added later from live ids, with nothing to migrate.

**What would change our mind:** wanting to tick or open a new task straight
from the morning's line in the thread.

---

## Moving Linear issues from Spica — deferred

**Deferred 2026-09-27.** In `spec/work-sync.md` v1, ticking a Linear task in
Spica only reminds the person to move it in Linear; nothing is written to
Linear.

**The next step, when it comes:** Spica shows the team's stages and the
person picks where ACM-119 goes; the next run moves it there — one stage,
never straight to the team's *Done*, because *done for me* is rarely done for
the team. The person picks because Linear's connector gives stage names and
types but **not their order** (checked 2026-09-27), so Spica cannot know
which stage is *next*.

**Why deferred:** a team's workflow is shared and has its own custom stages. A
wrong move tells teammates something false, and a reminder costs one tap in
Linear.

**What would change our mind:** the reminders piling up because moving by hand
is the step that gets skipped.

---

## Deleting a task from chat — deferred

**Deferred 2026-09-27.** `save_task` can archive a task — off every view, the
row kept — but not delete one. A delete in chat would take the shape of
`spec/done/agent-deletes.md`: soft, with a card that says it happened.

**Why:** the agent is at the ceiling of twenty-five tools
(`spec/agent-tools.md`), and archiving already answers *"ye task hata do"* for
a task that is simply no longer wanted. Kaam's own delete stays the way to
remove one for good.

**What would change our mind:** people asking to delete from chat and being
told to archive instead — or a second tool freed under the ceiling.

---

## Call recording — archived

**Archived 2026-09-27.** The scope and the research are in
`spec/archive/call-recorder.md`: a recorder the user intends to build, taking
the microphone and system audio as two tracks the way Wispr Flow and Granola
do, manual first and detecting calls later.

**Why:** work sync (`spec/work-sync.md`) comes first, and the recorder is a
build of its own — a native macOS app, a new surface. Recording on the phone
itself is closed to ordinary apps on both Android and iOS, so the first version
records calls taken on the laptop.

**What would change our mind:** work sync running, and tasks still being lost
because they were agreed on calls. The first step is written in the archive:
a manual Mac recorder for one WhatsApp Desktop call.

---

## Commitments — parked

> **Unparked 2026-10-10.** The early-month chafing this note waited for arrived as
> the opposite: a limit of ₹0 on a month with ₹61,421 of unseen, uneditable
> commitments. Designed in `spec/done/commitments.md`.

**Parked 2026-09-04.** `spec/archive/commitments.md` proposed one table for anything
with a future date and a consequence. The user's call, keeping the app simple:

- **Money commitments duplicate the ledger.** EMI, rent, gym, money home are
  already transactions tagged `fixed`. A second table would write one payment
  in two places.
- **Documents, things, people** are facts the user would *say*, not forms they
  would fill. A said fact is a `memories` row; the agent (phase 3) reads memory
  and can remind. No table for a user this user is not.

**The money half went elsewhere:** the early-month limit ran high because fixed
costs counted only once paid. That is now `spec/in-progress/fixed-costs.md` —
last month's fixed rows, locked until paid, derived from the ledger with no new
entity.

**What would bring it back:** that early-month limit chafing, or the agent
needing dated reminders it cannot get from memory text.

**Where:** `spec/archive/commitments.md`, `spec/done/udhaar-repayment.md` (udhaar
stays on the ledger either way).

## Contacts access — decided yes, but Android only

`counterparties.in_contacts` has been a column since the schema and has never
been anything but `false`: the web prototype has no phone book to read. The
decision recorded in `spec/in-progress/people.md` is that `READ_CONTACTS` is
**wanted** — it is the strongest signal for whether a payee is a person, and an
Indian contact list carries the relation in the saved name itself (*Mummy*,
*Sunny bhaiya*, *Landlord*), which no model can beat.

It is not in the settled *no* list with SMS and call logs; Play Store permits it
with a prominent disclosure and a privacy policy.

**The match is on the phone number, never the name.** UPI shows `MANORAMA
DEVI`; the phone book says `Didi`. Those strings have nothing in common, and
fuzzy-matching them would pair the wrong people. A UPI ID is often the number
itself (`9810012345@ybl`), and that is the exact join; where it is a handle
instead, the row stays unguessed. Whether the VPA reaches us at all is a capture
question — notifications often omit it, the Account Aggregator feed carries it —
and it is answered when capture is built. It implies one more column,
`counterparties.vpa`, which also retires `UNIQUE (user_id, raw_name)`.

**What would change our mind:** nothing about the value — it is the timing that
defers it. It cannot be built or tested before the Android app, so the People
spec is designed to work without it (a tap files a row; the agent may later
propose `kind` from the amount and direction, marked `· andaaza`) and to absorb
it when it arrives (`source = 'contacts'` outranks `source = 'agent'`, and
nothing moves).

**The rules, fixed now so the implementation cannot drift:** the contact list is
never stored and never leaves the device; only payees are matched, never the
whole book; permission is asked at a payment with the reason on screen, not at
install; refusing it costs a guess and nothing else.


## Report scorecard — the headline, then the rest

Settled 2026-09-06, replacing the four equal quadrants.

Four tiles of one size said all four numbers mattered the same, and they do
not: *what did I spend* is the question and *daily average* is a footnote to
it. So the first tile — or two — is the headline, and the rest are rows.

**Per mode:** Paisa leads with total spend, Work with open tasks, **Diet with
two** — protein and calories are one question asked twice for this user, and
demoting either would misstate how he eats. That is the `lead` prop, and it is
the only thing that varies.

**The comparison says `73% more`, not `73% more than the previous 7 days`.** The
range picker sits directly above the card and already names the span. It is
built from the tile's own `deltaLabel` rather than a re-derived percentage, so
a tile measured in grams says `19g more`.

**Each row carries one piece of context, never two:** the delta when there is
one, otherwise whatever the tile holds instead — a target, a limit, how many
lendings are open. Both would say the same thing twice, and a second line per
row would rebuild the equal weight the change removed.

**The range opens on Month — the month so far**, not a rolling week: on the 7th
that is seven days, on the 29th it is twenty-nine. A report answers *how am I
doing*, and that question resets with the month, because the salary, the daily
limit and the saving target all do. `Today` joins the picker for the other
question — *how is today going* — and compares against yesterday.

A one-day span changes what some tiles mean, so they say something else:
Paisa's *Daily average* row **disappears** (over one day it is the headline
again, to the rupee, and a row that restates the number above it is noise), and
*Protein a day* becomes *Protein today*.

**Two things the row layout exposed**, both fixed with it: `Within limit` /
`31/38` counts *payments*, not days, and was read as days by the one person who
uses it — it now says `Payments within limit` / `31 of 38`. And the Work card's
`Nipte` tile is `Done`; CLAUDE.md keeps three Hindi words, and that is not one
of them.

## Articles and Videos — removed, not deferred

Deleted 2026-09-06. Your data had five kinds; it has three — Dishes, Places,
Workouts — plus Pantry and People, which are real tables.

**The argument:** a thing is what it *is*, never the medium it arrived in. A
reel showing soya keema is a **dish that arrived as a reel**, and `dishes` has
carried a `source_url` column since it was built. `spec/capture.md` had already
half-reached this — it calls `video`-as-a-type a bug and proposes `medium` to
fix it — and following the same argument one step further retires `article`
too. What is worth keeping is the link; the thing it points at owns it.

**What is left over.** The `SavedItem` library is now eight seeded rows: five
places and three workouts, both of which have specs in progress that replace
them with real tables. When those ship the library has nothing in it, and
*Where it came from* — the panel counting capture sources — goes with it. It is
not removed yet because it is still the only picture of what the Chrome
extension is for.

**What would change our mind:** nothing about the removal. If a genuine
read-later need appears it is a different app, or at most a `link` kind with no
section of its own.

*Postscript, 2026-09-07:* the rest of the seeded library went the same way when
Places shipped. Every section now counts a real table, `LIBRARY` is empty, and
*Where it came from* is hidden until the capture extension saves something.

## A workout session ledger — built, then removed

Built 2026-09-06 as `workout_logs` + `workout_items`, removed 2026-09-07.

**Why it was wrong.** The user logs *that* he trained, not *what* he trained: a
workout is a habit tick, yes or no, alongside cigarettes and alcohol. A table of
exercise-lines per session had nothing to put in it, and getting there meant
retiring a habit that was working perfectly.

The reasoning that produced it is worth naming, because it looks sound: *he
trains a five-day split, so the question must be "did I do legs this week"*.
That is a question a person could have; it is not one this person asks.
**Dishes has both halves — a library and a ledger — because meals are actually
logged. Workouts have one, because they are not.**

**What survived** is the half that was wanted: `exercises` as a library to
suggest from. The star went too — `tried` on the row carries the only
distinction it was making, bookmarked versus actually done, and it is the one
stored count in Spica precisely because there is no ledger to derive it from.

**What would change our mind:** the user logging a specific exercise even once,
in conversation or a note or anywhere. Until then a session table is a schema
designed against an imagined user, the same failure as the `meal_slot` enum. If
it returns it gets a fresh migration and a fresh argument — `f6c94d2e8a13`
deliberately has no downgrade.

## Screen time — removed, not deferred

Deleted 2026-09-07. It was a fourth deck card on 98 hardcoded lines
(`data/screenTime.ts`) with no table, no API and no write path — a preview so
the domain could be judged before being built. It was judged: **Spica is three
domains — money, health, work.**

Gone with it: the `screen` mode and glyph, `screenHero`, `AppChart`, the `apps`
field on `HeroView`, and phase 7 of the roadmap. `spec/screen-time.md` moved to
`spec/archive/`.

**Why it is worth recording.** It was the last card in the app rendering numbers
that could not change, and it survived seven phases precisely because a
hardcoded array renders exactly like a real one. The cheap check it suggests:
for every card on screen, name the table behind it. Every one of them can now.

**What would change our mind:** a decision that attention belongs in this app —
not a missing feature. UsageStats and the ledger mapping were never the hard
part.



## Tool search — decided, not built

Written 2026-09-13 at 21 tools. Every tool's full schema is sent on every
request: 3,538 tokens, of which 2,117 are the parameter schemas alone — the
largest block in the prompt, bigger than the system prompt itself.

**Deferred**, because the schemas sit in the cached prefix, so they are paid
for once and hit thereafter. Hiding them saves the cache-miss price, not the
per-turn price, and a search costs a round trip plus a miss of its own. The
real risk of many tools is the model picking the wrong one, and that has not
been measured.

**What would change our mind:** a live eval showing wrong-tool selection on
turns where the right tool exists. `messages.tool_trace` already records every
call with its arguments, so the measurement needs no new plumbing.

The design is settled and written up in `spec/tool-search.md`: keep every tool
NAME in a one-line catalogue (291 tokens for all of them) and bucket only the
parameter schemas, behind a `find_tools(need)` call. Names stay because five
bugs in one afternoon came from the model failing to find the right thing while
it was fully visible — hiding a tool outright is how it stops being used.

## Payee names go to the categoriser in the clear

**Not hashing.** `spec/api.md` § /categorise sends `payeeHash` and keeps the
name→hash map on the device. The nightly batch (`spec/in-progress/categorise.md`)
sends `MOHAN LAL` as written.

**Why.** One user, their own API key, their own database — there is no third
party the hash would hide the name from. And the name is the only strong signal
a *new* payee carries: SWEETS, TRADERS, a first-and-last name, an all-caps
two-word UPI handle each say something a hash says nothing about. Hashing costs
the model exactly the rows it is most needed for.

**What would change our mind.** The categoriser running on a server that is not
the user's — a hosted Spica, or a shared key. Then the map lives on the device
as `api.md` drew it, and the skill file's learned-payee table carries hashes
with the labels resolved client-side.

**Where:** `spec/in-progress/categorise.md` § Decided against, `spec/api.md`.

## AI life companion — placed in Spica, not scoped

**Written 2026-09-18.** A concept doc for an always-on AI companion that plans
the day, adapts it as life breaks the plan, parks stray thoughts, and reaches
the user through a Wear OS watch and earbuds instead of a screen. Persistent
identity/goals model, proactive when useful and silent when not, no 24/7
recording, no dedicated hardware before the software proves it is needed.

**Placed, not built.** It is Spica, decided 2026-09-18 — and **not a fourth
mode**. The deck stays three. It is a layer across them: Paisa, Diet and Work
record *what happened*; this is the agent getting a sense of *now* and *next*
from what they already hold. Spica measuring the whole person is the expensive
part and is already done; a second app would rebuild the substrate for a year
before saying anything a stranger could not.

**Deferred anyway**, until Spica is in friends' hands — see
`spec/in-progress/README.md` § Queue. Four gaps stand between here and there,
and each is its own spec when its turn comes: **direction** (goals as identity,
not just targets), **now** (nothing knows what the user is doing at 3:40pm),
**park and return** (capture handles the outside world, not a stray thought
mid-task), and the **proactive loop** (`schedules.md` is its spine — built, but
the crontab line is still not installed).

**The decision that is still owed** is proactivity: everything Spica does today
is user-initiated, and the first unprompted sentence it ever says is a product
call that has never been made. Get it wrong and the companion is a notification
machine — `spec/archive/screen-time.md` is the precedent for cutting a surface
that nags.

**Where:** `spec/reference/life-companion-concept.md` — the full doc, unedited,
with the placement argument in its header.

## Android local-first storage — deferred past v1

**Written 2026-09-27.** Phase 6 of the roadmap describes the Android app as
"local-first SQLite, the same API". The first Android build is not local-first:
it is the web prototype, native — online, with the same optimistic writes that
mark a row unsaved when the server refuses (`android/README.md`).

**Why not now.** Local-first is a sync design — conflict rules, a durable
outbox, a migration story for the on-device schema — and none of it exists on
the web to port. Building it alongside the port would mean two unknowns at
once, and the port's job is to prove the flow survives the move to a phone.

**What would change our mind.** The first day the app is used somewhere the
network is not — a metro ride, a flight — and a spend said offline is lost or
refused. Then the outbox comes first: queue the write, replay it with the same
client-made ULID, which the API already treats as a replay rather than a duplicate.

## Quick chips group by the name as said — deferred

**Written 2026-09-30.** The greeting's chips count repeats by the row's name,
case and spacing aside (`THEME.md`). One habit said two ways
becomes two chips: on the scaffold account the Paisa chips are *Rapido ride
₹65* and *Rapido ₹260* — the same ride, named twice.

**Why not now.** Grouping better needs something to group by. A counterparty
or place id would do it for spends, and a dish id for meals, but most rows do
not carry one yet, and fuzzy matching on names would merge things that are
different ("Chai" and "Chai patti").

**What would change our mind.** Chips that repeat one thing, week after week,
on a real account — or the categorise pass starting to attach counterparties
to rides, which would give the grouping a key for free.

## Cards no turn produces yet — deferred

**Written 2026-10-06**, when the card redesign shipped
(`spec/done/card-redesign.md`). Both apps draw every card; these never reach
them, because nothing on the server or in the prompt produces them:

- **The ask card.** Defined on the wire and drawn by both apps; the agent
  never sends one, so "kal Rohit ko 500 diye" is logged as a guess rather than
  asked about. `n2n_eval` carries it as a known gap.
- **The morning brief.** The `morning_brief` schedule is not built.
- **The Linear sync turn** carries prose only; a receipt needs the sync's
  trace on the wire.
- **A number answer** ("kitna kharcha hua?") is a sentence; leading with the
  figure is the prompt's.
- **The reply repeating its card** ("Chai ₹20 log ho gayi" above the receipt)
  is the prompt's too.
- **"Last time N days ago" on an exercise receipt** needs the previous date,
  which only the server has once the new one is logged.
- **A weight said in chat** is stored apart from `/weigh-ins`, so the day
  card's "since <day>" can miss the latest one.

**Why not now.** Each is server or prompt work with its own design question —
when to interrupt with a question, what a brief says, what a sync turn
carries — and the redesign was render only. The prompt work is the user's,
done separately (`TODO.md` § Agent).

**What would change our mind.** The prompt pass, which takes the ask card and
the two prompt items with it; a morning that wants a brief; or the sync
running daily and its turns going unread because they are a paragraph.


---

## Chat quality — what the 95% left

**Shipped 2026-10-10** — `spec/done/chat-quality.md`: 96.3% of cases and 98.7%
of turns on Luna at medium, without glue. Four things were not done, on
purpose.

- **A task with no project named.** *"db migration"* was filed under Personal
  once and Novacart twice in three runs, each marked as a guess. The choice —
  keep guessing by the task's nature, or file it in the default project until
  one is named — was never made, because the guess is marked and a move is
  one sentence.
- **Shrinking the rules.** The prompt's rules grew one fix at a time; some may
  now overlap or bury the ones that matter. Not cut, because every round still
  went up.
- **The tool count** — past the guideline of twenty-five
  (`spec/agent-tools.md`). A wrong tool choice was not among the failures that
  remained.
- **A check at runtime** — comparing the reply's numbers with the turn's tool
  results before it is sent. Every number flagged in the last round was real
  (arithmetic on a result, or a target from the profile), so a check would
  have cost latency on every turn to catch nothing.

**What would change our mind.** A wrong project filed in real use, not just
the eval; a round that goes down after a rule is added (the rules are then
fighting each other); a wrong tool choice appearing in the failures; a number
in a real reply that nothing produced.

---

## Onboarding nudges in the chat

**Not built, by decision (2026-10-10; reason restated 2026-10-11).** The first
onboarding draft had the agent add one line after a related first write —
after the first meal, *"Want a protein target? The ring needs a
denominator."* It was never built, and it is dropped. It was first dropped
because the Getting started card listed every open step; that card is gone
(`spec/done/onboarding-goals.md`), and the reason now rests on two things. The
first run asks once, up front, for what Spica needs — the body, the place and
diet, the picked goals — and a skipped question stays skipped. And a nudge is
an unprompted agent turn, which is the proactivity decision still owed
(§ *AI life companion*): the first sentence Spica says unasked is a product
call, not an onboarding detail. "Never twice for the same step" would also
need a stored record of which nudges were said.

**What would change our mind.** People skipping the first run and leaving
the facts it asks for unset weeks later, while asking things a fact would
answer better. Then the agent's line, at the moment it is relevant, is the
better place — once the proactivity decision is made — and the record of what
was said is worth its column.

---

## Rent and EMIs during onboarding

**Not asked, for now (2026-10-11).** The goal-first onboarding
(`spec/done/onboarding-goals.md`) retires the Getting started card, and with it the
one nudge toward commitments — *"Add what you pay every month"*. The money
question asks only the monthly saving. Rent and EMIs are what make *Left to
spend today* honest (`spec/done/commitments.md`), so until a person adds them,
the daily limit counts only what they spend.

**Why not now.** The owner kept the first run short: each question asks for
the details of a goal the person picked, and rent is not a goal.

**What would change our mind.** People with a savings target whose daily limit
reads high for weeks because no commitment was ever added — then question d
asks *"and what goes out every month?"*, or the money widget asks once.

---

## Back — what the stack left out

**Deferred, 2026-10-11.** Screens over Home became one back stack on both
surfaces (THEME.md § *Back*). Six things were left out on purpose.

- **Restoring the stack after process death (phone).** The stack lives in the
  view model, so it survives rotation; when the OS kills the app, it starts on
  Home. Restoring it means the stack in a `SavedStateHandle` and every
  opener's loads run again on restore. Inline editors still reset on
  rotation. *Would change our mind:* the OS killing the app often on a real
  phone, so people come back to Home in the middle of a page.
- **The Health Connect rationale page (phone).** Health Connect's rationale
  intents need a privacy-rationale screen, which its policy requires before a
  launch anyway. That is product copy and a Play Store job, not stack work.
  *Would change our mind:* the Play submission (`spec/launch.md`) — it is due
  then, not later.
- **Asking before a commitment draft is thrown away (both).** Back, the scrim,
  X and Cancel discard the sheet's draft without asking; Escape inside a field
  on the web no longer does. A commitment is four fields, so a confirm on every
  dismissal costs more than retyping. *Would change our mind:* the sheet
  growing, or a draft lost in real use.
- **The predictive-back preview (phone).** `BackHandler` acts only when the
  gesture commits, so there is no in-app peek at the screen underneath. The
  system's back-to-home preview works, because nothing is enabled at the
  root. *Would change our mind:* the stack settled — then `PredictiveBackHandler`
  drives the top page's `translationX`; it is polish, not behaviour.
- **A URL per screen (web).** The address stays `/app`; `history.state`
  carries the stack, so refresh, back and forward reopen the right screen.
  Per-screen paths need a route table for a one-person app that shares no
  links. *Would change our mind:* a link worth sending to someone, or a
  screen the phone opens on the web.
- **A visible clear for the Pantry's History filter (both).** Back and Escape
  clear it first; a control in the *Moves · food* tab is left for the Pantry's
  own pass, so it lands on both surfaces at once. *Would change our mind:*
  that pass, or someone stuck in a filtered History.
