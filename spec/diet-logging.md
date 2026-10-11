# Diet logging

> Status: draft — reconciled from a v1 draft written against different context
> Surface: frontend · backend (estimation, vision) · android (photo, share)
> Evidence: 22 days of manual operation, 4–25 Aug 2026

## What this reconciles

The source draft was written as a standalone meal-logging app. It is not one —
**this is Spica's Diet mode**, and several of its features already exist here or
are already specified elsewhere. Eight corrections, worth reading before the rest:

| Draft said | Actually |
|---|---|
| "Spica — the separate universal-capture project" | Spica **is** this app. Diet is one of its three modes, beside Paisa and Kaam |
| "MCP server — memory layer" | `spec/api.md` settled storage: **local-first SQLite on device**, API serves rows and intelligence, never views. A network hop for every read breaks the offline glance. MCP is a *tool interface for the agent*, not the store |
| Recipe bookmarking as a feature to build (§3) | Already specified in `spec/capture.md`, both doors — bookmark from chat and share from Instagram. **Do not build a second save button** |
| "No folders, no tagging" | Correct as *UI*, wrong as *model*. Substrate's `type · path · tag` still applies; the point is the **user is never asked** — the agent files it, the Inbox catches mistakes |
| Recipe resurfacing when pantry matches — to build | Already works: `cookableNow()` in [stats.ts](../frontend/src/vault/stats.ts), and the Recipes card reads *"6 abhi ban sakti hain"* |
| "Estimate → correct primitive — build it once" | Agreed, and it is **already named three times**: Substrate's `(value, estimatedValue, confirmedAt)`, sleep's `· andaaza`, and `(signals, predicted, actual)` in `spec/paisa-categorise.md`. One name, not four — see §2 |
| Photo logging as a new pipeline | Right that it is the *same* pipeline. The prototype already has the `Media se log` entry point, returning a stub |
| Protein target 130g | It is a **setting**, not a constant. Currently 135 in `seed.ts`. Never hardcode it |

**And one gap the draft is right about, which we are currently failing:**

> *"The reply leads with what's left, not what was eaten — the single most
> important UX line in the whole app."*

That rule is correct, and `dietConfirm` does not follow it. It currently reads
*"Lock kar diya ✓ · 43 kcal gaya. Protein ab 87g — 48g aur chahiye aaj."* — three
clauses of what happened before the one thing that steers the next meal. Paisa has
the same shape. **Fixing the order is a copy change, not a feature**, and it is the
cheapest improvement in this document.

---

## 0. What 22 days of manual logging proved

Kept from the draft, because it is real evidence rather than a hypothesis.

| Signal | Evidence |
|---|---|
| Estimate-then-correct works | Every meal logged this way; grams never once given |
| Protein is trending up, not flat | 56g (4 Aug) → 124g (25 Aug), 21 days of real data |
| Only 1 of 21 days hit target | The gap is real. The report already says this plainly — `Protein 3/7 din` |
| Loose mixed-language input is the norm | *"subah maine wahi high protein oats khaya, whey nahi liya"* parses fine |
| Garbled voice-to-text is common | "circle" → cigarette, "क्षित" → khichdi |
| Purchase → pantry → depletion loop works manually | Every grocery run updated stock same-day |
| Behaviour shifts from patterns shown flat, not from lectures | Cigarette/beer co-occurrence shown without comment; behaviour changed after |

That last row is the whole product's tone in one line, and it matches the
manager-not-coach positioning: **show the pattern, say nothing about it.**

---

## 1. The core loop — text first

The user speaks or types a loose description. No grams, no structure, any mix of
Hindi and English.

> *"Morning mein sprout khai aur high protein oats khaya, shake nahi piya gym skip
> ho rahi thi. Dopahar mein regular chawal dal. Shaam mein vada pav. Raat mein
> beer, namkeen, aur chicken fried rice jisme chicken na ke barabar thi."*

### What the app does

1. **Parse** into discrete entries — slot (breakfast / lunch / snack / dinner),
   multiple items per slot.
2. **Estimate** kcal and macros per item, using **this user's** logged portions as
   the default — not generic serving sizes. A "thali" means what their thalis have
   meant.
3. **State the assumption**, one line, before locking:
   `Chicken fried rice — 520 kcal, 13g protein (chicken thi bahut kam). Sahi hai?`
4. **Correct or accept.** Correction by voice or text — *"nahi chicken zyada thi,
   protein badha do"*.
5. **On lock, lead with what is left:**

```
67g protein aur 80 kcal bacha hai aaj.        ← first
Chicken fried rice lock · 520 kcal, 13g       ← second
```

Not the reverse. A budget stated after the fact is trivia; stated first, it steers
the next meal. This is the rule the current copy breaks.

### Voice — an explicit non-requirement

**No in-app STT.** The user dictates through Wispr Flow and the text arrives as
text. Build the NLU on text only.

Which leaves a live question the draft did not have to answer: the prototype has a
mic button. On Android the honest resolution is that **the mic focuses the
composer and lets the user's own keyboard do the dictation** — if that keyboard is
Wispr Flow, it already is Wispr Flow. No ASR ships in this app either way.

### Ambiguity — log what is clear, flag the rest

1. **Never block the whole entry on one uncertain word.** Log what parsed; flag
   what did not.
2. **Ask only when the answer changes the macros.** *"kitna chicken tha"* changes
   13g to 30g and is worth a question. "circle" versus "cigarette" changes nothing
   in the meal log and is not.
3. Flag rather than silently guess. A wrong number the user believes is worse than
   a visible gap — the same rule as `spec/paisa-categorise.md` §4.1.

---

## 2. The shared primitive — name it once

The draft's strongest structural point, kept and consolidated.

```
estimate  →  state it  →  let the user correct  →  store the pair as calibration
```

This is already in four places under four names. It should be **one** thing:

| Surface | What is estimated | Already built? |
|---|---|---|
| Meals | portion → kcal, macros | Partly — estimation is a stub |
| Sleep | window from screen + motion | Yes, marked `· andaaza` |
| Payments | category, description | Specified, `spec/paisa-categorise.md` |
| Pantry | how much a meal consumed | No |

The envelope Substrate already defines carries it:

```ts
value           // what we settled on
estimatedValue  // what we guessed before the user touched it
confirmedAt     // null until confirmed or corrected
confidence      // how sure the guess was
```

**Build it as one module, four callers.** And keep every `(estimated, corrected)`
pair — that is the calibration set for portion defaults, and it cannot be
backfilled.

---

## 3. Photo logging

Same pipeline, new door. Not a second feature.

- Camera **or gallery** — a meal photographed at 2pm can be logged at 9pm, and a
  friend can send a food photo.
- Vision identifies the dishes, then hands off to the **same** estimate → state →
  correct → lock loop as text.
- When it cannot tell — mixed curry, cropped plate, bad light — **it says so and
  asks.** It does not name a random dish.

Why it matters: photo is the fastest input *in the moment*, and the running budget
in §1 is only useful if it is current. A budget that updates three hours after
eating cannot steer anything.

---

## 4. Recipes — nothing to build here

Covered by `spec/capture.md`. Both doors already specified: bookmark a suggestion
from chat, or share from Instagram. Retrieval against pantry already works via
`cookableNow()`.

The one Diet-specific addition worth noting: the resurfacing sentence — *"paneer
hai aaj, wo bhurji bana lo jo pichhle hafte save ki thi"* — belongs in the
greeting, not a notification. It is a suggestion, not an obligation.

---

## 5. Pantry — inferred, never asked

The feature most likely to fail, and for a known reason: the original Excel pantry
sheet went stale because *"kitna bacha hai"* never got answered by hand.

1. **Depletion is inferred from meal logs.** *"chicken fried rice"* moves chicken,
   rice and oil down. Nobody is asked.
2. **Purchases update stock on entry** — receipt photo, order screenshot, or
   *"aaj chicken aur dahi liya"*.
3. Tracks what is in stock, what a recipe is missing, and what can be cooked now.
4. **Pantry-first is a hard constraint**, not a preference: a suggestion must be
   buildable from current stock, or the app says so and offers a substitute from
   what *is* there.

### Status is derived from the ledger, never typed

The draft said depletion "decrements by an estimated amount", which sounded like
asking for quantities — and nobody knows they have 340 g of rice. The built model
(`spec/done/diet-data-model.md`, `pantry_moves`) resolves it without asking:

1. **Nobody types a quantity.** Purchases arrive with a size ("1 kg atta"), and
   recipes spend grams the recipe already knows. The stock is the sum. The user
   only ever says *bought* or *ate*.
2. **Untracked stays untracked.** A food with no inbound move — the family's atta,
   the salt — gets no arithmetic and no status. That is the honest "present,
   amount unknowable", not a fake `ok`.
3. **The four words are computed, not stored:** `out` at ≤ 0, `soon` at or below
   the item's reorder level, `ok` above it, `unknown` with no moves. The user
   reads the same coarse labels this section always wanted; the store underneath
   can say *why* one is `soon`.

**Only what cycles is counted.** The pantry is for things that run out and get
replaced — tofu, eggs, curd, chicken, whey. Staples that are always in the house
— atta, rice, dal, oil, salt — are never counted, even when a purchase is
mentioned: nobody runs a kitchen by weighing atta, and a number nobody checks is
the number that rots. A food enters the count the first time a purchase of it is
logged, and not before; the agent does not log purchases of staples.

The user never itemises. "Ek thali kha li", a photo, a sentence — the agent
extracts the items and the estimate. This section is only about what happens to
stock once a meal row exists: recipes spend from the counted set, and touch
nothing else.

So the pantry shows status, and status comes from the ledger. A stored
`PantryItem.status` is not built. Countable things (eggs, whey scoops) are the
same ledger in units instead of grams.

### Purchase ≠ possession

An item marked bought has not necessarily arrived or been unpacked. Logging the
purchase and logging its arrival must not be two chores. Default: a purchase marks
stock immediately, and being wrong for a few hours is cheaper than a second step
nobody performs.

---

## 6. Shopping list

1. **Triggered by real depletion, never a calendar.** Cadence is not weekly — it
   is however fast things actually run out.
2. Prioritises cheap, high-protein staples still marked as gaps — eggs, chicken,
   dal, paneer, the standing gap in this pantry.
3. Rough cost per item, and a total.
4. A confirmed purchase closes straight back into stock. No reconciliation step.

Point 3 is quietly the most interesting thing in this document: it is **Diet
reaching into Paisa**. A shopping list that knows both the protein gap and the
remaining spend limit can say *"anday sabse sasta protein hain, aur ₹191 bacha
hai"* — which no single-purpose app can. That cross-domain line is the reason all
three modes live in one app.

---

## 7. Architecture — corrected

```
   text            photo           share / bookmark
 (keyboard STT)  (camera·gallery)  (spec/capture.md)
      │                │                  │
      └────────┬───────┘                  │
               ▼                          ▼
     estimate → state → correct → lock    capture → classify → file
               │                          │
               ▼                          ▼
   ┌───────────────────────────────────────────────┐
   │   local SQLite — the source of truth          │
   │   meals · pantry · workouts · library         │
   └───────────────┬───────────────────────────────┘
                   │  /events sync  ·  /categorise  ·  /chat
                   ▼
        backend — rows in and out, plus the models
        (never a dashboard; see spec/api.md)
```

Two rules from elsewhere that constrain everything above:

- **Local-first.** Reads never need the network. The rings, the strip and the
  running budget all compute on device.
- **Pantry-first.** No suggestion exists outside what is in stock or genuinely
  needed.

---

## 8. Build order

Inside the phases in `CLAUDE.md` — web prototype, then backend, then Android.

| # | Build | Depends on |
|---|---|---|
| 1 | **Reorder the confirm copy** to lead with what's left | Nothing. Do it first, it is one function |
| 2 | Meal parsing + estimation, text only | The `/chat` endpoint |
| 3 | The shared estimate primitive, as one module | Step 2 defines its shape |
| 4 | Pantry status-stepping from meal logs | Step 2 flowing |
| 5 | Shopping list | Step 4 being accurate |
| 6 | Photo logging | Android; same pipeline as step 2 |

Recipes are absent on purpose — `spec/capture.md` owns them.

---

## 9. Out of scope for v1

- **In-app voice capture / STT.** The keyboard does it
- **Exact grams anywhere.** If a feature needs precise input to work, it is the
  wrong feature for this user
- Multi-person households, shared pantry
- Nutritionist or dietician collaboration
- A second recipe-saving mechanism
- Quantity-level pantry tracking for anything not naturally countable

---

## 10. Open questions

- **Where does portion calibration live?** It is per-user learned data, like the
  amount bands in `spec/paisa-categorise.md`. Probably the same mechanism and the
  same skill file — worth checking before building two learners.
- Vision model on-device or server? Same question as the LLM in `spec/api.md`, and
  probably the same answer.
- Does a **flagged** ambiguous word ever get chased, or does it just sit? Chasing
  is nagging; not chasing means the log quietly has holes. Leaning towards: the
  agent asks once, in the next conversation, never again.
- Pantry `soon` and `out` are useful; is `full` versus `ok` a distinction anyone
  acts on, or is three states enough?
