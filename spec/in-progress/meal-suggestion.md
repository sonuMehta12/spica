# Meal suggestion — what to eat, worked out the way a person would

> Status: **requirement recorded, 2026-10-10 — to design before anything is
> built.** One spec for all of meal suggestion: the gap between what is built
> and what should be, and — under *The reasoning* — how a suggestion is worked
> out, written from 25 days of doing it by hand (4–28 Aug 2026). That reasoning
> was `spec/Meal_Suggestion_Engine_Spec.md` until 2026-10-10, merged here so
> there is one place to read.
> Surface: backend (the reasoning, the state it reads) · Home's *Meals today* ·
> the chat's *"aaj kya khaun?"*
> Related: `spec/in-progress/today-plan.md` (Home's plan), `spec/done/chat-quality.md`
> (where the eval found it), `spec/launch.md` § 6 (suggestions from a cold start).

## The problem

Asked what to eat, Spica can only offer dishes already in the library, at the
one serving the library records. A new account has a handful of dishes and an
empty pantry, so it has almost nothing to say; a full library still cannot size
a day, because a dish cannot be planned at two servings. The reasoning below says a
suggestion is *a gap-closing calculation, not a recipe lookup* — what is built
is the lookup.

What was seen:

| Where | What happened |
|---|---|
| Home's morning plan, chat eval 2026-10-10 | Planned 1,340–1,800 kcal against a 2,000 target in six rounds of seven, at either effort — every time library dishes at one serving each (egg bhurji 280, whey 120, soya keema 360). It cannot reach the target whatever the model decides. |
| The chat, real thread 2026-10-01 | *"What can I eat today"* → "pantry mein kuch listed nahi hai, aur dish suggestions bhi nahi mile"; asked again to suggest from general knowledge, it repeated the lunch already logged. |
| Exercises, same day | *"legs ke liye kya karu"* → "library mein nahi mila" — the same shape: no library row, no answer. |
| The card test run, round 1 (`suggest`, `suggest-log`) | The person's notes: it relies on the library and pantry but needs a fallback when they are empty; a suggestion should weigh what is left of the day's macros, the eating pattern, and what is at home. |

There are also **two paths** that can disagree: the chat's `suggest_dishes`
(library candidates with signals, the model ranks them) and Home's
`/plan/today` (one model call over gathered state, `app/agent/plan.py` and
`skills/plan.md`).

## What already exists

| Piece | What it gives |
|---|---|
| *The reasoning*, below | The state needed (§1), the algorithm — gap, slots, pantry, context, rotation, guards, effort, one suggestion (§2), slot-aware logic (§3), guards (§5), what never to do (§10) |
| `suggest_dishes`, `dishes_search` | Library dishes with signals — cookable now, protein, minutes, times eaten, days since |
| `/plan/today` | Home's whole-day plan; checked against the rows, ideas marked as ideas |
| Meal logs, the pantry, targets | The state the reasoning reads |
| `keep_dish`, *Log it* on a suggestion card | Saving an idea; logging a suggestion in one tap |

## What it should become — recorded, not decided

- **The reasoning below, implemented as it says:** prompt plus retrieved
  state, not a rules engine. The state of §1 loaded, the algorithm of §2
  followed.
- **More than the library to draw from:** dishes they actually eat (their meal
  history), what the pantry can make, the library — and general knowledge when
  those run out, an *idea* shown as one (the amber dot, estimated macros) and
  savable in one tap.
- **Portions it can size:** a suggestion says how much — servings or grams — so
  the day can land on its targets.
- **One reasoning for both places:** *"aaj kya khaun?"* in chat and *Meals
  today* on Home answer from the same thinking, so they never disagree.
- **A first day that works:** a new account with no library and no pantry still
  gets ordinary, sensible suggestions for its targets.

## Rules already true

- **Never invent pantry stock** — §1 below and the agent's rules. An idea
  that needs what is not at home says so.
- **A library dish keeps the library's numbers; an idea's are estimates, marked.**
- **A suggestion is not a stored sentence about the person.** It is worked out
  from live rows each time, and goes stale with nothing.
- **One suggestion, at most one alternative** — §2 step 9 below.

## Open

- **How the context the reasoning needs is known** — home or office, who
  cooks, a workout day, a long workday (§1 below). Asked, remembered (`spec/in-progress/memory.md`),
  or read from the phone.
- **Servings or grams** for a sized suggestion, and how a correction to a
  portion teaches the next one.
- **One service or two entry points** over the same reasoning.
- **Whether an idea outside the library can be logged straight away**, or is
  saved first.
- **How it is evaluated** — Home's plan checks exist (`evals/n2n_eval.py`); the
  chat's suggestion cases check only that it suggests from what the tools gave.

## The reasoning — v1, from 25 days of doing it by hand

How a suggestion is worked out. Written for the model that makes it; the
companion documents it names (`Meal_Logging_App_Spec.md`, `product_notes.md`)
predate this repo.

### 0. The core principle

**A meal suggestion is not a recipe lookup. It is a gap-closing calculation.**

The wrong mental model: *"user wants dinner ideas → return popular high-protein recipes."*

The right mental model: *"user has consumed X so far today, has Y left against target,
has Z hours and Z' meals remaining, has these ingredients, ate these things the last 7
days, and is in this life-situation right now → what single thing should they eat next?"*

Everything below is in service of that one calculation.

### 1. State the agent must have before suggesting anything

The agent cannot make a good suggestion without all of these loaded into context:

| State | Why it matters | Example from real use |
|---|---|---|
| **Today's log so far** | Determines the remaining gap | 48g protein done by 11am → dinner target adjusts down |
| **Remaining meals today** | 90g gap across 3 meals ≠ 90g across 1 meal | If it's 9pm, suggesting "eat 90g protein" is useless |
| **Last 7 days of meals** | Rotation, repetition fatigue, ingredient reuse | Paneer eaten 3× this week → don't suggest paneer again |
| **Daily targets** | The gap is meaningless without them | 130g protein, 2050 kcal, 60g fat, 30g fibre |
| **Pantry stock** | Hard constraint — cannot suggest what isn't there | No paneer at home → suggest tofu/dal instead |
| **Standing food culture** | North Indian home cooking, not generic "healthy food" | Suggest dal-chawal adjustments, not quinoa bowls |
| **Where the user is** | Home vs office changes what's possible | Office lunch is fixed → suggest carrying dahi, not cooking |
| **Kitchen control level** | Lives with family → cannot dictate the menu | Suggest *additions* to what's cooked, not replacements |
| **Workout status today** | Rest day vs lifting day shifts carb tolerance | Gym day → more rice is fine |
| **Recent life context** | Stress/sleep/work load caps realistic effort | 12-hour workday → 5-min suggestions only |

**Rule:** If pantry state is unknown, the agent asks — it never invents an ingredient.

### 2. The suggestion algorithm (order matters)

```
1. Compute remaining gap        → target − consumed, for protein first, then kcal
2. Count remaining meal slots   → how many chances are left today
3. Divide gap across slots      → per-meal protein need (not one heroic meal)
4. Filter by pantry             → what can actually be made/eaten right now
5. Filter by location/context   → home? office? travelling? time available?
6. Filter by 7-day rotation     → drop anything eaten 2+ times this week
7. Apply physiological guards   → fibre ramp, fat ceiling, late-night timing
8. Rank by effort               → lowest-effort option that closes the gap wins
9. Output ONE primary suggestion + at most one alternative
```

**Step 8 is the one most systems get wrong.** A suggestion that closes the gap perfectly
but takes 40 minutes of cooking will not be followed. A suggestion that closes 70% of the
gap in 3 minutes will be. **Optimize for the meal that actually gets eaten, not for macro
perfection.**

### 3. Gap-driven, meal-slot-aware logic

The agent must reason about *when in the day it is*, not just *what's missing*.

**Morning (gap is large, all slots available):**
Distribute the target across the day. Front-load protein, because evening compliance is
historically worse than morning compliance (real pattern: breakfast is the most reliably
high-protein meal; dinner drifts carb-heavy).

> "3 ande ubaal lo aur roti kha lo — jo ghar par bane wahi, bas roti kam karna."

Note the shape: it *adds a protein item* and *adjusts the quantity of the existing carb*.
It does not replace the family meal.

**Midday (some slots gone, gap now concrete):**
If the user is at the office and lunch is fixed and uncontrollable, the only lever is what
they can *carry*. Suggest add-ons, not meals.

> "Office mein ho to ek dahi carry kar lena — lunch ke saath kha lena, protein pura ho
> jayega."

**Evening (gap known precisely, 1–2 slots left):**
This is where the agent should *check what was missed earlier* and patch it.

> "Subah anda nahi khaya tha — to shaam mein anda kha lo, ya shake pi lo."

**Night (last slot):**
If the remaining gap is unreachable, say so plainly and suggest the best partial close.
Do not suggest a 60g-protein dinner at 10pm. Suggest the realistic thing and let the day
land where it lands.

### 4. Rotation and variety rules

- **7-day lookback.** Any protein source used 2+ times in the last 7 days drops in rank.
- **Never suggest the same dish twice in 48 hours** unless the user asks for it.
- **Rotate within the same protein tier**, don't jump tiers. If dal is due for a break,
  suggest rajma/chana/soya — not "have chicken every night," which is unaffordable and
  unrealistic for a home kitchen.
- **Non-veg realism:** assume non-veg is cooked 2–3 days/week max in a North Indian home,
  not daily. The other 4–5 dinners must be solvable with vegetarian protein.

**Reference rotation for dinner protein (~20g target), all home-kitchen normal:**

| Source | ~Protein | Note |
|---|---|---|
| Soya chunks curry (40–50g dry) | ~25g | Highest non-meat density, cheapest |
| Paneer sabzi/bhurji (100g) | ~18g | |
| Anda curry/bhurji (2–3) | ~18g | |
| Rajma / chana masala (1.5 katori) | ~15–18g | High fibre |
| Boiled chana salad (200–250g) | ~20g | Can be requested as an add-on to family cooking |
| Thick dal (1.5–2 katori) + dahi | ~20g combined | **Pair two sources** — dal alone won't hit 20g |
| Chicken / fish | ~25–30g | Reserve for the 2–3 non-veg days |

**Pairing insight:** single vegetarian sources rarely hit 20g in realistic portions.
The agent should default to **combining two** (dal + dahi, sabzi + tofu) rather than
suggesting an unrealistically large portion of one.

### 5. Physiological guards (the "don't hurt them" layer)

These override macro optimisation.

- **Fibre ramp:** If a suggestion raises daily fibre substantially above the recent
  average, warn and suggest starting at a smaller portion. Sudden large increases in
  legumes/chana cause bloating and gas. Ramp over ~a week.
- **Fat ceiling:** Track fat against target. Rich curries (butter chicken, poori, kadhi),
  fried snacks, and nut/seed-loaded breakfasts stack fast. If fat is already at/over
  target, the next suggestion must be a low-fat protein (dahi, egg whites, grilled/tandoori
  over fried).
- **Late-night timing:** If the user is eating within ~1–2 hours of sleeping, prefer
  lighter, lower-fat options — heavy late meals worsen sleep, which is already a known
  problem area.
- **Fried vs grilled swap:** When the user names a fried item, offer the grilled/tandoori
  equivalent as the alternative — same protein, much less fat. Never demand it; offer it.
- **Effort ceiling:** Nothing requiring >20 minutes active cooking on a weekday.

### 6. Context-sensitivity rules

**Kitchen control is the single most important context variable.**
The user lives with family and does not control the menu. Therefore:

- Suggestions are **additions and adjustments**, not replacements.
  ✅ "Jo bane wahi khao, bas roti kam karna aur ek dahi add kar lena."
  ❌ "Make grilled chicken with quinoa salad."
- The agent may suggest **requesting** something from the household cook, framed as a
  standing weekly ask, not a per-meal demand.
  ✅ "Ghar par bol do hafte mein ek din chana/rajma bane."
- **Office days:** lunch is provided and fixed. Only carry-along additions are actionable.
- **Festival / social days:** do not attempt to optimise. Log flat, no correction, no
  guilt. Resume normal suggestions the next day.

**Effort scaling by life context:** if recent context shows high stress, poor sleep, or a
heavy work stretch, the agent must *lower* the effort bar, not raise the discipline bar.
Under load, the correct suggestion is "ek dahi kha lo" — not a meal plan.

### 7. Prep-ahead awareness

The agent must think 24–48 hours ahead, not just about the next meal.

- Sprouts need ~24h soaking → flag today for day-after-tomorrow.
- Chicken benefits from overnight marination → flag the evening before.
- Boiled eggs / boiled chana keep for days → suggest batch-prep when the user has a
  low-effort window, so high-protein options exist during high-stress days.
- If tomorrow's suggested meal needs an ingredient not in the pantry, **flag it today**
  as a purchase, not tomorrow as a failure.

### 8. Tone and output format rules

- **One suggestion, not a menu.** Decision fatigue kills compliance. Offer at most one
  alternative.
- **Compact.** Read on a phone in under 30 seconds. No essays.
- **Lead with what's left, not what's eaten.** "67g protein bacha hai" beats "you have
  consumed 68g."
- **State assumptions inline, briefly**, so the user can correct: "~200g chana maan raha
  hoon."
- **Never lecture, never guilt.** A missed target is logged flat. 80% consistency is the
  goal.
- **Match the user's language register.** Mixed Hindi/Hinglish/English as the user writes
  it.
- **Ask, don't invent.** Unknown pantry item → ask. Never fabricate stock.

### 9. Worked examples (use as few-shot prompt material)

**Example A — morning, full day ahead, home**
> State: 0 consumed. Target 130g protein. Pantry: eggs, dahi, tofu, soya, dal. Gym day.
> Output: "Subah 3 ande ubaal lo + jo roti bane wahi, roti thodi kam. ~24g ho jayega.
> Lunch mein dahi add kar lena. Shaam mein shake. Raat mein soya curry bolna ghar par —
> phir 130 ke aas-paas pahunch jaoge."

**Example B — evening, gap known, morning protein was missed**
> State: 48g consumed by 6pm. 82g remaining, 2 slots left. Eggs not eaten today.
> Output: "Subah anda miss ho gaya tha — abhi 2 ande ya ek shake le lo (~24g). Dinner mein
> dal ke saath dahi le lena, ~20g. Total ~92g tak pahunch jaoge aaj."

**Example C — office day, no kitchen control**
> State: at office, lunch provided and fixed.
> Output: "Lunch to jo mile wahi hai — ek dahi carry kar lena, saath mein kha lena.
> ~9g extra mil jayega bina kuch badle."

**Example D — festival / social day**
> State: Rakhi. Poori-paneer twice, mithai, beer.
> Output: log it, state totals once, no correction, no suggestion. "Aaj festival hai,
> kal se normal."

**Example E — fibre ramp guard**
> State: user proposes 250g boiled chana dinner; recent fibre intake low.
> Output: "Plan sahi hai. Bas pehle hafte 150g se shuru karo, phir 250 tak badhao —
> achanak itni fibre se bloating ho sakti hai."

### 10. What the agent must NOT do

- Suggest ingredients not confirmed in pantry
- Suggest replacing family-cooked meals
- Suggest >20 min weekday cooking
- Give a multi-option menu (decision fatigue)
- Optimise macros at the cost of realism
- Lecture, moralise, or reference a bad day
- Ask for gram-level input from the user — the agent estimates, the user corrects
- Suggest anything at all on a flagged festival/social/sick day

### 11. Implementation note

This reasoning is a **prompt + retrieved state**, not a rules engine. The retrieval layer
(MCP server / DB) must supply: today's log, 7-day history, targets, pantry stock, location
flag, workout flag, and recent context notes. The LLM does the reasoning above.

The (estimated → corrected) pairs from the logging loop feed back as portion calibration
— same shared primitive described in `Meal_Logging_App_Spec.md` §1 and `product_notes.md`
§3.9.
