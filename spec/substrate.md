# Substrate

> Status: draft — the scoped-down replacement for the **Substrate** design note
> Surface: everything. This decides what the agent can ever answer
> Supersedes: the artifact of the same name, which was written before the cuts below

## What changed, and what it costs

The design note was written when the plan still included an always-on-top
capture extension and a general reading library. Both are gone. Applying that:

| Cut | Consequence |
| --- | --- |
| **Articles** — removed entirely | The reading pile was the only type that needed a deep, growing tree. Without it, see below |
| **The always-on-top extension** — cancelled | One capture door instead of two: the Android **share sheet** |
| **Places as a saved thing** — cancelled | Places are no longer captured. They are **derived from payments** — see §5 |

**The consequence worth noticing: the tree almost disappears.**

The design note spent its longest section on `type · path · tag`, one-axis rules
and depth caps. That machinery existed mostly for articles — hundreds of items
across many topics. What is left is two types with one shallow axis each:

| Type | Tree |
| --- | --- |
| Recipes | Breakfast · Lunch · Dinner · Snack |
| Workout plans | Push · Pull · Legs · Full body |
| Pantry | none — a flat stock list |
| Notes | none — tags only |
| Places | none — derived, grouped by the category of the payments made there |

So **do not build a folder system.** Two fixed lists and a tag field cover it.
The `path` field stays on the envelope because it costs nothing and a third
type may want it later, but nothing in v1 needs a folder editor.

The rest of this file is the design note, cut to what remains true.

---

## 1. The first decision — two stores

Payments, meals, sleep, workouts, recipes, pantry in one breath sounds like one
pile. It is two, and conflating them is the mistake that is expensive to undo.

| | **Ledger** — things that happened | **Library** — things you keep |
| --- | --- | --- |
| Examples | Payments, meal logs, sleep, steps, a workout you did, a task you closed | Recipes, workout plans, pantry, notes |
| Mutability | **Append-only.** A correction is a *new* row, never an edit | Curated and mutable — rename, retire, re-file |
| Queried by | Time, amount, category | Topic, tag |
| Growth | Forever, linear. Thousands of rows a year | Bounded by attention. Hundreds of items |

A payment has no business in a folder. A recipe has no business in a time
series. Same app, same agent, two stores.

### The pattern that connects them

The library holds the **template**, the ledger holds the **instance**:

| Library (template) | Ledger (instance) | What the link buys |
| --- | --- | --- |
| Recipe | Meal log | *"Soya keema — 4 baar banaya is mahine"* |
| Workout plan | Workout done | Adherence, without tracking it |
| Pantry item | Purchase, consumption | Stock that falls on its own |
| Commitment (EMI, udhaar) | The payment against it | What is still owed, actually |
| **Place** | Payments there | *"Is cafe pe ₹2,400 ja chuke"* |

Every row is a question no single-purpose app can answer. That is the reason to
build this rather than use five apps.

---

## 2. The envelope

Every record, both stores, shares a spine. This is what makes any adapter
possible — it only has to fill one known form.

```ts
interface Record {
  id: string;          // opaque, stable, never reused
  type: Type;          // closed set — see §3
  createdAt: string;   // UTC ISO-8601
  updatedAt: string;
  source: Source;      // 'share' | 'voice' | 'manual' | 'device' | 'notification' | 'import'
  confidence: number;  // 0–1. 1.0 only when the user confirmed it
  tags: string[];
  deletedAt?: string;  // soft delete — sync cannot converge on a row that vanished
}

// ledger rows add
interface LedgerRow extends Record {
  occurredAt: string;  // UTC — when it actually happened
  localDay: string;    // "2026-08-22" — the day *you* were living
}

// library items add
interface LibraryItem extends Record {
  title: string;
  path?: string;       // only Recipes and Workout plans use this
  sourceUrl?: string;  // where it was shared from
  medium?: 'video' | 'page' | 'image' | 'text';
}
```

### Two fields that carry more than they look like

**`localDay`, stored — not derived at read time.** *"Aaj kitna kharch hua"* is a
local-day question and a UTC timestamp alone cannot answer it: an 11:30pm chai
lands on tomorrow. India is **UTC+5:30**, so the offset is not even a whole
hour and every ad-hoc fix gets it wrong. Compute it once, at write. Every
"aaj / kal / is hafte" then becomes a string comparison instead of a timezone
bug.

**`medium` is not `type`.** A recipe that arrives as a YouTube reel is a
**recipe**, not a video. `vault.ts` currently has `video` as a kind, so *"Soya
keema in 20 minutes"* is filed as a video — that is a bug to fix while the data
is still fake. Medium is how it reached you; type is what it is.

---

## 3. The closed type list

Seven, and the set is fixed. Untyped records cannot be computed over — no types,
no rings, no reports, no agent worth having.

**Ledger**

| Type | Shape |
| --- | --- |
| `transaction` | amount, direction, payee, flat category, method, place? |
| `meal` | items, kcal, protein, carbs, fat, slot |
| `workout` | kind, minutes? |
| `sleep` | window (start, end), estimated vs confirmed |
| `steps` | count, from Health Connect |
| `task` | name, project?, due?, priority?, done, doneDay? |

**Library**

| Type | Shape |
| --- | --- |
| `recipe` | ingredients, method, time, macros?, `needs[]` → pantry ids |
| `workout_plan` | the routine a `workout` is an instance of |
| `pantry_item` | name, status: `full · ok · soon · out` |
| `note` | free text, tags |

**Derived**

| Type | Shape |
| --- | --- |
| `place` | see §5 |
| `commitment` | see §4 |
| `account` | bank, UPI handle, cash, card |

---

## 4. Money is three entities, not one

| Entity | What it is | Store |
| --- | --- | --- |
| **Transaction** | One movement of money that already happened | Ledger. Immutable. **Flat** category |
| **Account** | Where money sits or moves through | Library. A handful |
| **Commitment** | Money owed, either direction, with a date — EMI, rent, gym fees, *Sunny se aana hai* | Library, with a schedule that generates expected transactions |

**Udhaar is a commitment**, not a separate entity — `kind: 'person'`,
`direction: LENT | BORROWED`. `spec/udhaar.md` carries the detection and
repayment-matching logic, which is real and belongs there; the storage and
reminder machinery should not be built twice.

**Spend categories stay flat, deliberately.** Everything else here is a list, so
this exception needs a reason: *you add categories up.* The moment they nest,
every total has to decide whether a parent includes its children, and every
screen has to say which it did. Want `Khana → Bahar / Ghar`? That is `Khana`
plus a tag.

**Corrections are entries, not edits.** A wrong payment is fixed by a second row
that supersedes it. The trail stays auditable — and more importantly, the agent
gets to see that it guessed wrong, which is the only way passive capture ever
improves.

---

## 5. Places — derived, not collected

This is the biggest structural change from the design note.

A place is **not something you save**. It appears because you paid there. There
is no "add a place", no travel-app list of spots you want to visit, no folder.

```ts
interface Place {
  id: string;
  name: string;
  lat: number;
  lng: number;
  radiusM: number;      // a paan shop is ~20m, a mall ~200m
  rawType?: string;     // what the provider called it
  category?: string;    // what we make of that
  address?: string;
  provider?: 'google' | 'user' | 'derived';
  providerId?: string;  // so a re-lookup is stable
  confidence: number;
}
```

### A place is a different thing, and got its own table

This section originally merged three names into one table — `Place`,
`PayeeProfile`, `CounterpartyStats`. Two of those are still one table. **Place
is not**, because the word changed meaning.

When this was written, "place" meant *a location you had saved* — a travel-app
list — and those really were the same rows as the payees. Cutting that idea left
a different concept behind: **a place is where you were when a payment
happened**.

| | |
|---|---|
| **Counterparty** | *who* you paid |
| **Place** | *where* you were |

They coincide at a shop and diverge everywhere else: Rapido is a counterparty
with no place; a Zepto delivery is a counterparty whose place is your home; a
food court is one place holding many counterparties.

A place is created silently from a payment's coordinates, but **only when the GPS
fix is good enough to mean something** — worse than ~50m covers a whole market,
and inferring a shop from that is inventing data. The raw coordinates stay in
`predictions.signals` either way, so a location that was too vague today can
attach to a place tomorrow.

### Payee and counterparty are still the same table

`spec/paisa-categorise.md` defines `PayeeProfile` — normalised name, user label,
amount band, `hasReceivedFrom`, `inContacts`. `spec/udhaar.md` defines
`CounterpartyStats` — the same fields again under a third name.

**All three are one table.** A payee, a counterparty and a place are the same
row seen from three features. Building them separately means three sources of
truth for *"is Mohan Lal a shop or a person"*, and they will disagree.

Naming it `Place` is the wrong emphasis — most rows are shops, but some are
people. **`Counterparty` is the honest name**, with places being the subset that
are shops.

---

## 6. Capture — two doors, one pipeline

**Decided 2026-09-04, reversing the earlier "share only" call:** on the phone,
the Android share sheet; on the desktop, a **Chrome extension** with one
deliberate action — send this page to Spica. Both are the user choosing to
share, exactly as they would to a friend. Neither watches what is on screen;
the earlier always-on-top extension that filed things by itself stays cancelled.
Both doors feed the same pipeline:

```
Instagram reel / YouTube video / blog
        │  share sheet (phone)  ·  extension button (Chrome)
        ▼
   Spica receives a URL
        │
        ├─ stored immediately, as a link          ← never fails
        │
        └─ background: fetch → parse → LLM → structured, with sources
                 │
                 ├─ resolved  → filed as recipe / workout_plan / note
                 └─ unresolved → Inbox, and the agent asks once
```

Three rules, and the first is the one that decides whether the habit survives:

1. **The share always succeeds.** Store the link and confirm before anything is
   understood. A share that can fail is a share the user stops doing.
2. **Enrichment is allowed to fail.** Instagram often yields only a URL and
   blocks scraping. Unresolved is a normal outcome, not an error.
3. **Keep the source.** Every enriched item stores where it came from. An
   LLM-parsed ingredient list without a link back is a guess nobody can check.

### What gets shared, and what does not

This is a health, finance and work app. It is **not** a general bookmarking
tool — that is what removing articles was for.

> Treat it like a friend you send *certain* reels to. Recipes, workouts, and the
> occasional note. Not everything you see.

If a shared thing does not resolve to `recipe`, `workout_plan` or `note`, it
lands in the Inbox and probably should not have been shared. That is the correct
outcome, not a gap to fix.

`spec/capture.md` has the mechanics. Its "Door 1 — bookmark from conversation"
is secondary at best; **sharing is the door, from whichever device you are on.**

---

## 7. Inferred values keep both numbers

Most of the ledger is guessed rather than entered. Steps come from Health
Connect; sleep is a heuristic; a payment's category is a prediction; a meal's
macros are an estimate.

Every inferred value keeps **both**:

```ts
value           // what we settled on
estimatedValue  // what we guessed before you touched it
confirmedAt     // null until confirmed or corrected
confidence      // how sure the guess was
```

The gap between the two is **the only training signal this system will ever
get**, and it cannot be backfilled. The app already shows the discipline — an
inferred night reads `· andaaza`, a confirmed one does not. That should be a
rule everywhere, not a one-off.

---

## 8. The edges

Types and tags find things. What makes this a personal OS rather than a tidy
archive is that records point at each other.

```
recipe ──needs──▶ pantry_item ──bought via──▶ transaction ──at──▶ counterparty
   ▲                                                │
   │                                                └──against──▶ commitment
meal ──from──┘

workout ──from──▶ workout_plan
task ──in──▶ project
```

Already working: a recipe knows its pantry dependencies, so the Recipes card
says *"6 abhi ban sakti hain"*. Every other edge is the same trick again:

- **transaction → counterparty** turns *"cafes pe kitna gaya"* into *"tum ek hi
  cafe jaate ho"*
- **meal → recipe** lets the diet report say what you actually cook
- **transaction → commitment** tracks a loan down to zero without a spreadsheet
- **pantry → shopping list** is what makes the list trigger on real depletion
  rather than a calendar

---

## 9. Where it lives

- **SQLite on the device**, source of truth for reads. Every glance is local; the
  app never shows a spinner to report something you just logged
- **Full-text index** on titles — cheap, and covers most filtering
- **Embeddings** for asking, computed server-side, cached against the item id
- **An append-only event log** — `{seq, id, op}` — so any client syncs from its
  own cursor. Also what makes backup incremental
- **Size:** library in the hundreds, ledger in the low thousands per year. Index
  the ledger on `localDay` and `category`; the library barely needs it

**Backup is not export.** One-tap "download everything" stays a **no** — it is
the largest leak in a personal-data app. But no-backup is a different and worse
risk: a lost phone is years of ledger gone. The resolution is **encrypted backup
that only restores into Spica**, never landing as a readable file. Per-item
delete stays the user-facing control.

---

## 10. Deliberately not

| Not doing | Because |
| --- | --- |
| A folder system | With articles gone, two fixed lists and a tag field cover it |
| Articles / read-later | Removed from scope. Not what this app is for |
| Places you want to visit | Places come from payments. Anything else is a travel app |
| Separate payee / counterparty / place tables | One row seen three ways. Three tables will disagree |
| Passive capture | The always-on-top extension that filed things by itself is cancelled. Every capture is a deliberate share — share sheet on the phone, an extension button in Chrome |
| Nested spend categories | Totals become ambiguous the moment a parent might include children |
| Editing ledger rows | Destroys the audit trail and the agent's only feedback signal |
| Untyped notes as the main store | Untyped records cannot be computed over |
| Reading SMS or call logs | Your constraint, and Play Store's |
| One-tap export | Encrypted restore-only backup covers the real risk |

---

## 11. Open

- **`Counterparty` or `Place`?** The table is the same either way; the name sets
  what people expect it to hold. Leaning `Counterparty`, with places as the
  subset that are shops.
- **Does `note` earn a place in v1?** It is the one type with no structure, and
  untyped catch-alls tend to absorb everything around them. Possibly wait until
  something concrete needs it.
- **Where do payments come from** — notification listener, Account Aggregator, or
  manual. Still the biggest unanswered question, and it shapes the whole ledger.
- **Commitments in v1 or not?** They explain *kitna aana hai, kitna jaana hai*
  properly, but bring schedules and recurrence rules with them.
- Should `workout_plan` ship at all in v1, or do workouts stay instance-only
  until there is a plan worth storing?
