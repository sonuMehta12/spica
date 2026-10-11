# Spica

A personal OS for one person. One conversation, no forms: you say a thing and the
agent logs it. Three modes — **Paisa** (money), **Diet** (food), **Work** (kaam —
across projects).

The premise the whole product hangs on: **agent hi app hai.**

It was called Cortex until 2026-10-09. Everything a person reads and the code's
own names say Spica — the Android package is `com.sonu.spica`. A few things keep
the old name on purpose, because renaming them breaks something and nobody
reads them: the databases `cortex` and `cortex_test` (every row and `.env`
would move), the browser's storage keys `cortex.*` (every browser would be
signed out), the Google Cloud project `cortex-508717` (an id cannot change),
the emulator AVD `cortex`, and `spec/done/` (decisions made under that name).

## Repo layout

```
frontend/   the web version — Vite + React 19 + TypeScript
backend/    the API — FastAPI + Postgres; one test file per shipped spec
android/    the native app — Kotlin + Jetpack Compose, see android/README.md
spec/       PRD and one spec file per feature. Written before the code
```

## How this gets built

The end product is an **Android app (Kotlin + Jetpack Compose)**, built in this
order on purpose:

1. Build the whole thing as a **web version** first — fast to iterate, cheap to change
2. Build the **backend** against that, end to end
3. Only once the flow is proven, build the mobile app — knowing exactly what to build

Step 3 has started: `android/` is the web version, native, against the same API
(`android/README.md`). Work in `frontend/` to try an idea, `backend/`
for anything that persists, `android/` for the app that ships. A change you can
see lands on both surfaces, token for token.

## Before any UI work — read `THEME.md`

**`THEME.md` at the root is how Spica looks**: the tokens, what each colour is
for, who the serif belongs to, the icons, each surface's cards and ground, the
honest states, and a checklist. Read it before you build or change anything a
person sees, on either surface, and design with it — a new screen uses its
tokens and kit, never a colour, font or shape of its own. If the design needs
something it does not hold, add it there and to both token files.

## Running it

```bash
npm --prefix frontend run dev
```

The landing page is the root, `/`; the app is at `/app`; `/film` is the
landing's film alone, for recording.

`npm --prefix frontend run build` · `npm --prefix frontend run typecheck`.
There is also a `frontend` entry in `.claude/launch.json` for the preview pane.
Never start a dev server with a raw Bash command — use the preview tooling.

The Android app builds with Gradle and runs on the `cortex` emulator;
`android/README.md` has the toolchain, the dev login and the commands.

## Before writing a feature

Write the spec first. **Read `spec/README.md`** — it holds the layout, the naming
rule and how a spec is written. `spec/_TEMPLATE.md` is the shape.

Two rules from it that are easy to get wrong:

- **Specs hold decisions, not conversations.** No questions, no answers to review
  comments, no "you asked X". Discussion happens in chat; the spec records what
  was decided and why. A spec should read as a clean document to someone seeing
  it cold.
- **`spec/in-progress/` is where a decision is still being argued.** It moves up
  to `spec/` when settled, and on to **`spec/done/`** once the feature actually
  ships. So `spec/` is what is still owed; `spec/done/` is why the code is like
  it is.
- **`spec/notes.md` holds deferred decisions** — things deliberately not built
  yet, with the reason and what would change our mind. Read it before proposing
  something; it may already have been considered and parked. Add to it whenever
  something is postponed.

`TODO.md` at the root holds small concrete jobs — scripts, data collection,
chores — that do not deserve a feature entry.

The roadmap lives in `feature.json` at the root — every feature with its status,
a description and a link to its spec. Keep it current as things ship.

## Conventions that already hold

Read `THEME.md` and `frontend/README.md` for the full picture.
The rules that matter most:

- **Tokens, always.** Every colour and font resolves through
  `frontend/src/theme.ts` on the web and `ui/theme/Tokens.kt` on Android — one
  token set (Jamun), hex for hex. Nothing hardcodes a hex.
- **Serif is the agent speaking.** Newsreader is the agent's words (and the
  page's date heading); Anek Latin is everything else, every number included,
  with tabular figures. No mono face, no tracked caps. The agent has no bubble
  and no face beside its replies; your messages are a brand-tint pill.
- **One brand colour, far from the data.** Jamun is the mic, send, selection
  and links. Mode colours (Paisa, Diet, Work) appear on data only, and the
  brand sits at least 80° of hue from every one of them.
- **Icons are Phosphor.** No hand-drawn paths, and no text character (▾ ⋮ × ✓)
  standing in for an icon.
- **Never store a sentence about the user's own data.** Card notes and insights
  are computed from live rows at render time — a stored sentence quietly starts
  lying when a row is deleted or a task is ticked. This is about claims, not
  about reference values: a recipe's macros or a portion size are inputs, and
  they are stored like any other data.
- **Live ids, not snapshots.** Cards store row ids so deleting a row updates every
  card that showed it.
- **Honesty over completeness.** No fabricated deltas — say `no prior data`.
  Inferred values are marked — an amber dot before the value; confirmed ones are
  not, and there is no "confirmed" mark. A weight given as a guess keeps the dot
  until an exact one replaces it. Amber means nothing else. Show coverage.
  A metric that would flatter the user is the one worth showing plainly.
- **Copy is English** — the app's language, UI included. Terse, specific, no
  jargon; the register stays the user's, the vocabulary does not. Two words
  are names, not copy, and stay: *Paisa*, *udhaar* — though the phone calls
  Paisa *Money* (2026-10-08). (*andaaza* was retired as
  UI copy 2026-09-13 — a state is copy, and the dot says it; see
  `spec/done/chat-cards.md`.) Data is data: a
  row called `Dost 2 ko diya` is never translated.

## Tests — backend only, spec by spec

Decided 2026-09-04, after a feature shipped with a bug the review caught by
hand. **Every backend feature lands with its tests, in the same commit.**

- `backend/tests/test_<spec>.py` asserts that spec's Definition of done against
  the real API. One file per shipped spec.
- `backend/tests/test_regression.py` is the cross-cutting sweep: schema drift,
  soft deletes, no orphans, no `'me'`, replays, unknown-is-not-zero.
- Run with `cd backend && uv run pytest`. Each run builds a fresh `cortex_test`
  database from the migrations, so the dev data is never touched and a missing
  migration fails a test rather than hiding.
- **`backend/evals/n2n_eval.py` is the end-to-end check with the real model**:
  every card case's sentence, the tool, card and row it must produce
  (`uv run python -m evals.n2n_eval`). Not part of `pytest` — it spends real
  tokens. Run it before a build and after any prompt or tool-description change.

**The frontend is not tested.** The web version is where flows get proven and
change fastest (see *How this gets built*); the backend is what the Android app
keeps, so the backend carries the tests.

## Product constraints — these are settled, don't relitigate

- **No SMS, no call logs.** The user said so, and Play Store policy agrees.
  Payment capture comes from notifications or the RBI Account Aggregator instead.
- **No data export.** A one-tap "download everything" is the biggest leak in a
  personal-data app. Per-item delete is the user-facing control. *Encrypted
  restore-only backup is a separate, allowed thing* — see the Substrate note.
- **No Accessibility Service.** Play Store prohibits it for this use.
- **Three domains, no more** — money, health, work. The phone's Home shows
  them as five widgets (Today; Money; Diet, Activity and Habits, all health),
  which is not a fourth domain. A screen-time card existed on hardcoded data and was removed
  2026-09-07; `spec/archive/screen-time.md` says why. Attention is not this
  app's problem.
- **No read-later list.** `article` and `video` were kinds in Your data until
  2026-09-06; a thing is what it *is*, never the medium it arrived in. A recipe
  reel is a dish with a `source_url`. Spica is not a bookmarking app.

## Design notes

Longer thinking lives in published artifacts rather than this file:

- **Work (kaam)** — the work mode's design and why its ring became a bar chart
- **Substrate** — the data model: ledger vs library, type/path/tag, the graph

Ask the user for the links if you need them; they are in their artifact gallery.

## Working style

- The user prototypes on weekends, on a personal laptop, and intends to keep all
  IP personally. Nothing here goes near an employer's machine or accounts.
- **Weekends only, by their own rule (2026-10-08).** On a weekday, Monday to
  Friday, open the session by saying so plainly: this time belongs to office
  work. It is a reminder, not a refusal — once said, do what was asked and
  keep it short.
- They think in Hinglish and design by reacting — show the thing, don't describe it.
- Verify in the browser before claiming something works. Screenshots in the
  preview pane lag a frame; read the DOM for anything you are asserting.
