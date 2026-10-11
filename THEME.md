# THEME.md — how Spica looks

**Read this before you build or change anything a person sees**, on the web
(`frontend/`) or the phone (`android/`). It is the design system as rules to
follow, not a history. The theme is called **Jamun**.

The tokens are code, and this file never restates a hex the code does not
hold:

| Surface | Tokens | Kit |
|---|---|---|
| Web | `frontend/src/theme.ts` — `color`, `font`, `radius`, `space`, `shadow`; `global.css` reads them as custom properties (`--ink`, `--brand-tint`) | `components/messages/*` for cards |
| Phone | `android/…/ui/theme/Tokens.kt` (`C`, `F`, `T`) and `Shadows.kt` (`S`) | `ui/common/Page.kt` — ground, panel, page header, coins, switches, pills |

**The two token sets are one set, hex for hex, under the same names.** Change
a value in one and you change it in the other in the same commit. A visible
change lands on both surfaces unless the surface rule below says otherwise.

---

## Before you write a line of UI

1. Find the token for every colour and the style for every piece of text. If
   none fits, **add a token to both files** — with its OKLCH reasoning and its
   contrast ratio in the comment — never a literal in a component.
2. Find the kit piece that already does the job (a panel, a page header, a
   coin, a pill, a switch). Build from it. A one-off card shape is a bug.
3. Decide **who is speaking** in every line: the agent (serif) or the data
   (sans). See *Type*.
4. Decide what each state looks like: **loading** (a dash), **unknown** (a
   dash), **empty** (one plain line saying how it fills), **estimated** (the
   amber dot), **over** (red). See *Honest states*.

## Colour

| Token | Job | Never |
|---|---|---|
| `ink` | text | — |
| `muted` | supporting text (6.8 : 1) | — |
| `faint` | labels, metadata — passes AA on white and on `surface` | — |
| `grey` | decoration only: a future day, an idle mark (2.7 : 1) | text someone must read |
| `line`, `lineSoft`, `border` | hairlines, dividers; `border` for fields, the composer, chips | — |
| `brand` (Jamun `#732F67`) | the mic and send, the agent's mark, the current selection, links | data, a number, a decoration |
| `brandTint` | your own messages | — |
| `paisa`, `diet`, `work` (+ `Soft`, `Ink`, `Tint`) | marks on that mode's data | chrome, buttons |
| `amber` | **the estimate dot, and nothing else** | a warning, a highlight, a category |
| `red` | over a limit, money out, late, negative | emphasis, a delete button's decoration |

The rules behind the table:

- **One brand colour, used sparingly.** Jamun is an action or a selection.
  Everything else on screen is ink, greys, or a mode's data colour.
- **The brand sits at least 80° of hue from every mode** (Jamun 335; Paisa
  160, Diet 55, Work 250), so an action never reads as a number and a mark
  never reads as a button. A new colour keeps this distance.
- **Modes share lightness and chroma** (OKLCH L 0.62, C 0.13): the hue says
  *which* mode, and none looks more urgent than another. Within a mode, steps
  go by lightness — `base`, `ink`, `soft` — never by a new hue.
- **Neutrals lean 0.5% toward Jamun** (C 0.005 at H 335), so greys and the
  brand read as one material. A new grey follows the same lean.
- **Categories** take `categoryPalette` (mode hues, then their soft stops,
  then grey) — never amber, never red.
- **Other companies' colours** (`brand.claude`, `brand.whatsapp`…) are for
  their marks only, beside their names.
- **New colours are computed, not picked by eye**: an OKLCH value, a WCAG
  ratio against what it sits on, written beside the token.

## Type

| Face | Job | Phone style |
|---|---|---|
| **Newsreader** (serif) | the agent's own words; the page's date heading, italic | `T.agentVoice` (15.5 / 23), `T.display` |
| **Anek Latin** (sans) | everything else — controls, labels, **every number** | `T.sans`, `T.figure`, `T.cardHeading`, `T.mono` |

- **Serif means the agent is speaking.** Never set a label, a number or a
  button in it. Never set the agent's sentence as grey small print.
- **A figure is data**: Anek, medium weight, **tabular figures** on (`tnum`),
  so ₹1,100 and ₹8,880 line up.
- **No mono face and no tracked uppercase.** Labels are sentence case. `mono`
  is an alias for sans in grey — the name only survives so old call sites
  compile.
- **The wordmark** is `spica`, lowercase, Anek semibold, beside the mark —
  never the serif. In a sentence the name is *Spica* (`frontend/src/brand.ts`).
- **A CSS px is a dp** (or sp for text). The same number on both surfaces.
- Both faces draw ₹, a true minus (−) and tabular figures. A replacement face
  must too — check the file, not the specimen page.

## Icons

**Phosphor**, one family. Regular for chrome; fill for marks drawn small
(habit coins, project icons); bold for glyphs under about 12dp (ticks, carets,
close). On the phone only the glyphs drawn are compiled in: add one with
`android/tools/phosphor_kt.py`, which writes `ui/common/Ph.kt`.

**Never** a hand-drawn path, and **never** a text character standing in for
an icon — `▾ ⋮ × ✓ ✎ ‹ › ↑ ↓ ● ○`. Google's sign-in uses Google's mark.

## Surface, shape, space

Colour, type and icons are shared. **The surfaces differ on purpose:**

| | Phone — the app that ships | Web — the prototype |
|---|---|---|
| Ground | `lineSoft`, a tint, under every page — Home, Chat, Reports, Your data, Profile, the menu, the door | `paper`, white |
| Cards | white **panels that float**: `Modifier.panel()` — 24dp corners, `S.widget` soft shadow, no border | white, a hairline border, **no shadow**; radius 14 small cards, 18 the deck and bubbles |
| What lifts | panels, popovers | only menus and the toast (`shadow.popover`) |
| Layout | Home and Chat, two pages behind a pill | the deck above the thread |

When you build on the phone, build from `Page.kt`; when on the web, from the
web's tokens. Do not carry one surface's treatment to the other without
deciding it for both.

Shared on both:

- **Shadows are ink at a low alpha, never black** (`C.shadow`).
- **Pills and round buttons are fully round** (999).
- **A 4-unit grid.** Page gutter 16. In the thread, **8 between messages of
  the same speaker, 20 where the speaker changes** — the rhythm says who is
  talking.
- **The agent has no bubble and no face.** Its words run the thread's full
  width in serif. Yours are a `brandTint` pill on the right, ink text.
- **Text first, the card below — never a sentence inside a card.** The card
  holds data only; what it means is the agent's line above it, worked out from
  live rows at render time.
- **The mark** is the Constellation (`Mascot.tsx`, `Mascot.kt`). It moves only
  on the live row of a working turn, the door and the drawer: idle breathes,
  thinking pulses the outer dots, saving pulls in and settles. Everywhere else
  it is still.

## Back

Screens over Home form **one back stack** — `AppState.stack` on the phone,
`State.stack` with `state/nav.ts` on the web. The rules are the same on both.

- **Home is the root and is never on the stack.** On Home at rest nothing
  catches Back: the phone leaves the app, with the system's back-to-home
  preview; the web leaves `/app`.
- **Opening a screen pushes it; Back pops exactly one**, to whatever opened it
  — never "close to Home". Levels inside a page (a Your data section, a
  Profile group, a nudge's page) are entries too, and a deep link pushes only
  the level it opens. A screen already on the stack is gone back to, never
  stacked twice.
- **A page has one exit: ← at the top right of its head**, where each
  surface's page close used to sit, in that close's style — on the phone a
  white 40 disc, the arrow at 19 in `ink`; on the web a 36 borderless round
  button, the arrow at 20 in `muted`, with the hover tint. No label beside
  it. A screen reader hears where it goes: *Back to Menu*, *Back to Your
  data*, *Back to Home*. **No X on a page.**
- **X is only for the root of a modal layer**: the menu, a sheet, a dialog.
- **← and system or browser Back pop the same entry.** Back first closes what
  is open on the top layer, innermost first: the keyboard; a popover, dialog
  or sheet; a page's open editor, form, prompt, tray or choices — **the one
  opened last closes first**; then the composer's edit, then its context; then
  the top entry. Escape on the web is Back. The on-screen ← skips the inner
  steps: it leaves the page.
- **Opening a screen is a context switch**: the keyboard, the composer's edit
  and its context go. Leaving a page that carries the composer (Report,
  Profile) drops them too.
- **Layers under the top stay drawn and keep their state** — same scroll, same
  tab, no entrance replayed — **and are inert**: no taps, no focus, no Back,
  hidden from screen readers. A field open there lets go of the keyboard when
  something is pushed over it. On the web, closing a layer returns focus to
  what opened it.
- **Tabs, ranges, filters, month paging and popovers are not navigation**:
  they never push.
- **The menu is a destination**: a row pushes its page over it, and the
  page's ← comes back to it. A row marked *Soon* does nothing when tapped.
- **Only a question leaves everything.** A send from a page's composer that
  asks the agent, or a nudge's *Ask about this*, clears the stack and lands
  in Chat — the thread, not the deck — with the cursor still in the composer.
  A correction sent from a page stays on the page, where its row changes. A
  result that arrives in the background never moves you.
- **Phone:** one ordered `vm.back()` behind one stack `BackHandler` in Home.
  Everything a page opens closes through `BackStep(open)` (`Page.kt`) — one
  per open thing, never a branch inside — enabled only while it is open and
  its layer is on top (`LocalOnTop`). The keyboard's step is the app's own,
  in `Gate` (`MainActivity.kt`): a `BackHandler` composed while the keyboard
  is up, and again whenever the stack moves, so it is always the newest and
  outranks every page's — one press hides the keyboard and does nothing else.
- **Web:** every push is a history entry carrying the stack in
  `history.state`; ← and X call `history.back()`. Inner steps are
  `useBack(open, close)`, counted only on the top layer. Never push for small
  state.

## Honest states

These are the product's rules made visible. A screen that breaks one is wrong
however good it looks.

- **Unknown is not zero.** Not loaded, not logged, not recorded → a dash (—),
  never `0`, `₹0` or `0 / 0`. A habit day with no log is an empty mark.
- **Estimated gets the amber dot before the value.** Confirmed gets nothing —
  there is no "confirmed" mark. A weight the person gave as a guess (*around
  72*) carries the dot too, and keeps it until an exact weight replaces it:
  confirming a guess does not make it exact.
- **Red means over** — a limit passed, money out, late — and nothing else.
  Habits are counted in ink, never judged in red.
- **Empty is a state**: one plain line saying what will be here and how it
  fills (*No spends yet this month*).
- **Nothing on screen is a stored sentence about the person's data.** Notes,
  insights and counts are computed from live rows each render; cards hold row
  ids, so deleting a row changes every card that showed it.
- **No fabricated numbers.** If nothing measured it, it is not on screen.
- **Something not built says so.** A menu row that leads nowhere yet says
  *Soon* instead of a caret.

## Data, written the way a person reads it

- Money: `₹1,100`, Indian grouping (`₹1,40,350`), a true minus: `−₹21`, never
  `₹-21`.
- A day: `Wed, 16 Sep`, never `2026-09-16`. A window in words: *This month*,
  *Today*, *This week*.
- Data is data: a row called `Dost 2 ko diya` is shown as written, never
  translated.

## Copy

English, terse, specific, no jargon — the register stays the user's, the
vocabulary does not. *Paisa* and *udhaar* are names and stay; the phone calls
Paisa *Money*. Placeholder in the composer: *Say what happened…*. A state is
copy too: *estimated*, not a word for it in another language — the dot says
it.

## Checklist — before you say a UI change is done

- [ ] No hex, no font name, no shadow value outside the token files.
- [ ] The same token change made on both surfaces, or a reason it is one
      surface only.
- [ ] Every colour has its job from the table; amber only on the estimate dot;
      red only for over.
- [ ] Serif only for the agent's words and the date; every number tabular sans.
- [ ] Phosphor only; no character standing in for an icon.
- [ ] Loading, unknown, empty, estimated and over each render as above.
- [ ] A new screen is a stack entry with ← at its top right, said as *Back
      to* its opener; anything it opens closes on Back first (*Back*).
- [ ] Text meets AA on the surface it sits on; a mark meets 3 : 1.
- [ ] Checked on screen — the web in the preview pane (read the DOM, not only
      a screenshot); the phone on the emulator.

## Decided against — do not bring back

- **A green brand** (Neem): it shared Paisa's hue, so chrome and money blurred.
- **A black or indigo brand**: today's default template look.
- **Cream grounds**: white reads cleaner; the warmth comes from type and the
  mode inks.
- **Lucide, Heroicons, Material Symbols**: the default of every generated
  app. Phosphor's weights cover chrome and tiny marks in one family.
- **Material 3 components on screen** (phone): Material is underneath only for
  ripples and popups; its tonal surfaces and type scale are not ours.
- **Downloadable fonts on Android**: the emulator knew neither face and fell
  back to Roboto silently. Both faces are bundled in `res/font`.
- **Rings for everything**: arcs are hard to compare. Bars, or one ring for
  the one quantity a ring is for (protein against its target).
