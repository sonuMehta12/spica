# Projected savings — the cricket card

> Built and verified same day — all three rows reproduce the expected numbers
> on the paisa report, plus the vs-goal note the user asked for on sight. Reads from: `spec/done/deck-ui.md` (ledger arithmetic settled
> there), the workbook's Dashboard §3 (the user hand-built this feature in
> Excel before the app existed — the strongest validation a feature gets).

## The problem

The daily limit says what to do *today*; nothing says where the month is
*heading*. Cricket solved this display problem decades ago: projected score at
the current run rate, and at a couple of alternatives. The workbook's own
Dashboard carried exactly this table — *"Agar roz kharch karo 300 → bachega
12,092"* — and it is the one part of the sheet the deck has no answer to.

## What it does

Three columns in the **paisa card's bottom band** — the strip of card reserved
for the deck's mode glyph, empty on paisa:

```
─────────────────────────────────────────  hairline
per day   ₹791 now   ₹2,085      ₹2,978 goal
saves     ₹20,749    ₹15,573     ₹12,000
```

**Sorted by rate, not by concept.** Unsorted the three were just numbers; in
ascending order they are a curve — *spend more, save less* — and the reader
gets a model instead of a list.

**Both anchors are tagged.** `now` and `goal` are the two points a reader
needs to locate themselves between; the middle column is legible as "somewhere
in between" without a label of its own.

**A hairline makes it a footer, not floating text.** The habit strip gets the
same rule and the same geometry, so both cards' bands are one shape.

**Always on screen, never behind the menu.** The "More" menu is right for
diet's macros because those are occasional; this is a number wanted every
time, and a tap is a barrier in front of it.

**In the band, because the band is free.** This is the same trick that lets
the diet card carry its habit strip: the glyph's row has empty space to its
left, so anything living there costs the card no height. The deck's three
cards share one height and it is not negotiable — measured before and after,
all three stay at **268px**.

**Two label words, once.** `per day` / `saves` label the rows, so the numbers
need no units — `/day` repeated three times spent width on a word carrying
nothing.

**Placed on the card, not the report.** Built on the report first and moved on
sight: the projection answers *"aage kya"*, which is the question you have
while looking at the arc — a screen away it is a statistic nobody opens. The
"card stays at two numbers" rule survives intact, because the earlier casualty
was an explainer *sentence*; three chips of rate-and-outcome are the arc's
continuation, not prose about it.

English throughout — the app's language, decided the same day.

| Row | Meaning | Formula |
|---|---|---|
| **Line 1** | where the month lands if nothing changes | pace = spent ÷ days elapsed · projection = remaining + udhaar pending − pace × days left |
| **Line 2** | what the limit is *for* | always lands exactly on the goal, because the limit is reverse-engineered from it. This chip is the limit's explanation — the card's explainer line died trying to say it in prose |
| **Line 3** | "what if I tightened up" | the limit cut by 30%, shown as a **rate you could actually run at**, not an abstract lever. The first version said "spend ₹100/day less → +₹400", which is arithmetic; this says ₹2,085/day → ₹15,573, which is a choice |

All ledger arithmetic — the same settled frame as the limit. No bank balance,
no roll-forward.

## Rules

- **Projections are labelled as projections.** A future number is andaaza by
  nature; the row says `projected`, and the honesty rule is satisfied by the
  label, exactly as the workbook's table was.
- **Pace uses the whole month** (spent ÷ days elapsed), like cricket's current
  run rate. A 7-day "recent form" pace is a later refinement if the month pace
  ever feels stale — not two paces at once.
- **Over-goal months read plainly.** When current pace already beats the goal
  (this August: ₹20,749 vs ₹12,000), row 1 simply shows the bigger number. No
  celebration, no nudge to spend more.
- The third chip is a **rate**, not a delta. Three comparable rates read as
  one scale; a rate plus a saving-delta reads as two unrelated ideas.
- The tighter step is fixed at 30%. A configurable step is a settings screen
  nobody asked for.

## Decided against

| Option | Why not |
|---|---|
| On the report page | Tried first, moved on sight — a screen away from the arc it is a statistic nobody opens |
| The workbook's 5-row rate ladder (300…800) | Three chips answer the question; five decorate it |
| A vs-goal note on the first line | Built, then dropped: stacked in one column the three values compare themselves, and ₹20,749 above ₹12,000 needs no sentence |
| Chips with borders and captions | Cost 52px of card height for chrome around six numbers. The card's height is shared by all three modes and is not negotiable |
| Behind the three-dot menu | Considered against diet's "More" precedent and rejected: macros are occasional, this is not. A tap in front of a number you check daily is a barrier |
| In the legend column under *Aaj* | Fit, but read as a footnote to the rings rather than its own idea. The band gives it a line of its own for the same zero height |
| Column headers with `rate → saving` pairs | Built and compared side by side. To fit an arrow pair in a third of the width the numbers dropped to 9px — making the **saving, which is the answer, the smallest thing in the row** — and the arrow was invisible at any weight that did not overpower the numerals it joined. Stacking the pair vertically buys the same relationship from position, for free |
| Recent-form pace (7-day) alongside month pace | Two paces invite reconciling them; one is a story |
| Configurable lever step | A setting for a number nobody will change |

## Definition of done

Anchored 28 Aug, in the paisa card's band: ₹791 → ₹20,749 · ₹2,978 → exactly
₹12,000 in green · ₹2,085 → ₹15,573. **All three deck cards measure 268px** —
the projection added none. Changing the goal in the profile moves the middle
line and the limit together. Verified in the browser.
