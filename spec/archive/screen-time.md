# Screen time — attention ka Paisa

> **Archived 2026-09-07 — not being built.** Cortex is three domains: money,
> health, work. Screen time was a fourth deck card running on 98 lines of
> hardcoded data with no table behind it, kept as a preview so the idea could
> be judged before it was built. It was judged: no.
>
> Kept for the argument in it, not as work owed. What would bring it back is a
> decision that attention belongs in this app at all — not a missing feature.

> Status: idea recorded; **a card preview exists on hardcoded data**
> (`frontend/src/data/screenTime.ts`) so the idea can be judged before it is
> built. Capture is Android-only, so the real thing still waits for phase 6.
> Reads from: `spec/done/paisa-data-model.md`, `spec/done/diet-data-model.md`

## The problem

Reels, YouTube, the endless scroll — time going where it was not meant to go,
in amounts nobody chose. The user's friend named it; the user has it too. It is
the same problem Paisa solves for money: **spending that never got counted, so
it never got decided.**

## The insight: money and attention are the same shape

The whole Paisa apparatus maps across almost column for column:

| Paisa | Screen time |
|---|---|
| a transaction | an app session — app, minutes, `local_day` |
| category | the app, or its class (social, video, work) |
| daily limit (`AAJ SE ROZ KA LIMIT`) | per-app target — *Instagram: 60 min/din* |
| `JO YAAD HI NAHI` — the gap | time with no memory of spending it |
| savings — *itna bacha liya* | *itna time bacha liya* — the same win, same framing |
| notification capture | **better**: the OS itself is the ledger (see below) |
| `andaaza` vs confirmed | intent — the honest gap that stays (see below) |

And the one place screen time is *easier* than money: **capture is solved.**
Paisa fights for every row — notifications, parsing, dedupe. Android's
UsageStats API hands over per-app time authoritatively. The hard part flips:
Paisa's hard part was *getting* the data; this mode's hard part is *what it
means*.

## What it reuses, unchanged

- **The envelope, `local_day`, integer units** (minutes, not float hours)
- **Targets live where targets live** — the profile, beside `savings_target`
  and `protein_target`, when profile exists
- **Habits already model the behaviour half.** *Reels kam karna* is a `break`
  habit; the streak strip and the beer→cigarette-style correlations come free —
  *raat 11 baje ke baad scroll → agli subah neend kharab* is two tables away
- **Honesty over completeness.** No shame mechanics, no red. A manager states
  the number; a coach nags. This is a manager

## What the preview proved, and what it exposed

Built on the Paisa card's exact shape — same two rings, and at first the same
projection band — to test the "column for column" claim by rendering it rather
than arguing it.

**The mapping held everywhere it was claimed.** Work apps became `fixed`
without argument: Slack and Gmail are screen time you cannot cut, so they draw
as the arc's pale stretch and the daily target applies only to what is left.
That is rent and EMI, exactly. Calendar-day division, the anchor tags, the
sorted rate curve — all reused unchanged.

**One thing did not map, and it is worth knowing.** Paisa's projection row is
labelled `saves`, and a higher rate saves less. Screen time inverts: a higher
rate gives you *more* screen time, so `saves` would have read as *spend more,
save more*. The row label had to become the mode's, not money's — `month` for
screen time. **Attention is money with the sign flipped**, and any copy that
assumes "more is worse" or "more is better" has to be per-mode.

### The rings became bars, for the same reason Work's did

A ring answers *how much of my budget is gone*. The question here is
different: **which apps are eating me** — and that is a comparison between
three magnitudes, which nested arcs cannot show, because an arc's length
depends on its radius. Bars share a baseline. Same argument that turned the
Work card's concentric circles into a chart, arriving independently.

**Only the watched apps are charted.** Addiction concentrates in two or three
— a feed, a video app, a game — and a chart of every app is a chart of
nothing. The user picks which to watch; **capture stays complete regardless.**
Watching is a view, never a filter on what is recorded, which also means the
choice is reversible without losing history.

**Each bar splits at its target**: solid up to it, a lighter cap above, and an
amber pip when the day is already past. Amber, not red — this records what
happened, it does not scold.

**Icons, not initials.** The Work chart labels bars `A / C / S` because a repo
name has no picture. An app does, and it is the most over-learned image most
people own — recognition beats reading at 14px. Traced rather than copied: a
rounded square with a lens, a play tab, a crosshair. Unknown apps fall back to
a letter, the same rule the habit strip uses.

**What the preview shows, on the hand-written month:**

```
        ▉  ▊  ▉          Instagram 1h26 · YouTube 1h06 · BGMI 1h18
        ●  ●  ●          all three past target — amber pips

Total    131h 39m / 119h 14m     ← pale stretch = work apps
Aaj      4h 44m / 2h 30m

per day  1h 45m   2h 30m target   3h 13m now
month    96h 55m  99h 55m         102h 47m
```

The sort puts `now` past `target`, which is the whole story in one glance:
the current pace is over the line, and the month lands ~43 minutes a day
above where it should.

**Removed 2026-09-04.** The band came off the screen card on the user's call:
*"where the month lands"* is a money question, and nobody manages phone use by
a month-end total. Screen time is judged today, per app, against today's
target — the rings and the bars already say that. Paisa keeps its band; the
inversion lesson above stands for any future mode that borrows it.

**Deck rule intact.** This is a fourth card in the prototype so it can be seen;
shipping it means choosing three of four, which is what *domains are
selectable* has always meant.

## What is genuinely new

One table, roughly:

```
app_sessions:  app · minutes · local_day · (source: usage_stats)
app_targets:   app/class · minutes_per_day     ← or on profile; decide later
```

## The honest limits, named now

**Reel *counts* are not capturable.** That needs an Accessibility Service, and
that is a settled product constraint (Play Store prohibits it for this use).
Time-per-app is the measurable truth; "n reels" is not. The target vocabulary
is minutes, not counts.

**Intent is invisible.** Chrome for work and Chrome for scroll are one number.
YouTube tutorial and YouTube shorts likewise. Time alone mislabels — the same
way an amount alone could not categorise a payment. Whatever solves it
(app-class defaults, time-of-day signals, asking once) inherits Paisa's
`predictions` pattern: guess, mark, learn from corrections. Not designed here.

**The permission is real.** `PACKAGE_USAGE_STATS` needs a Play Store
justification (digital-wellbeing category is accepted practice) and a settings
toggle the user grants manually. Same class of honest friction as notification
access — declared in the same breath, when Android is built.

## This is a domain, not a fourth card

The deck holds three modes — settled, not reopened. The resolution was always
the user's own: **domains are selectable.** Health, money, work today;
screen time joins the shelf; the user activates what they want measured. A
domain someone never chose costs them nothing, not even a menu entry.

That framing is the real content of this spec: **new domains plug in as
rows + targets + habits**, and the deck stays three cards deep.

## Prior art, acknowledged

Digital Wellbeing, Screen Time, Opal, one sec, Forest — the space is heavily
built and heavily researched. The difference here is not the measuring; it is
that the measurement lands in the same ledger, the same conversation and the
same honesty rules as money and food — *one* agent that knows the whole person,
not a fifth app with its own dashboard.

## Open, deliberately

- Sessions per app-open, or one row per app per day? (Paisa says: per event;
  the OS may only give daily aggregates — capture decides, not preference)
- Targets per app, per class, or both?
- Does "time saved" get the savings framing literally — a number that grows —
  or is that gamification creeping in?
