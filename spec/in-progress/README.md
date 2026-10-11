# in-progress

Working documents for whatever is being built **right now**.

A file here is unfinished by definition — half-decided, with open questions still
in it. That is the point: `spec/*.md` holds decisions, this folder holds the
arguing.

## The rule

When a document here is settled, it **moves up** to `spec/` and this folder gets
smaller. Nothing lives here permanently. If a file has sat here for weeks, either
it is not actually being built or the decisions in it were never made — both
worth noticing.

Ideally one file at a time. Two means two things are half-built.

---

## Queue — to a release, agent last

**Decided 2026-09-05.** Task sync is deferred until after the app is in
friends' hands. The order is: build the rest of the app → use it → send it to
friends → then Work, taught to them as *"coming soon"* so that when it lands it
already makes sense. Work would have eaten the weeks that release needs.

| # | Work | Why it is before the agent | ~Size | Spec |
|---|---|---|---|---|
| 1 | **People** — the humans among your counterparties: relation, a note, what went and came back | eighteen counterparties with real money against them; udhaar's per-person history gets its first home | ½ day | **shipped** → `spec/done/people.md` |
| 2 | **Workouts** — an exercise library like dishes, sessions as a ledger with the exercises done | *"kal kya karu"* needs to know what exists and what you did this week; the habit tick cannot answer either | 1 day | **shipped** → `spec/done/workouts.md` |
| 3 | **Places** — where you pay and where you go, on a map, each with a kind | the coordinates and kinds are what payment detection will match against later; a place you add now is a signal the agent gets for free | 1–1.5 days | **shipped** → `spec/done/places.md` |
| 4 | **The agent** — one brain, many mouths, typed cards | everything above gives it truer data to sit on; every card now reads a real table | phases A–F | settled → **`spec/agent.md`**, `spec/agent-tools.md`; prerequisites shipped 2026-09-12 |
| — | *Release prerequisites* — the auth lock on the seam, hosting off localhost, the encrypted backup | friends cannot use a laptop's localhost | — | drafts → `sign-in.md`, `onboarding.md`; hosting in `spec/backend.md` |

**Also queued, not started:** `chat-cards.md` shipped 2026-09-13 → `spec/done/chat-cards.md`: every write
earns a card, dishes named in prose become a tap-to-log card, an amber dot
replaces *andaaza*.

`commitments.md` shipped 2026-10-10 → `spec/done/commitments.md`: commitments are
rows the user owns, set and changed from a page, from chat and from a payment's
tray; the `fixed` / `repeats` flags retired.

`habits.md` — three habits exist because a migration inserted them; there is no
route, no screen and no tool that can add a fourth. Four routes, a row per habit
in Profile under Health, and one `manage_habit` tool. One decision open.

**Deferred past release:** everything Android. The work sync that was
`task-sync.md` is settled as `spec/work-sync.md`; the file-scanning design it
replaced is archived as `spec/archive/repo-task-scanner.md`.

**Waits for the agent (phase 3):** `categorise`, `chat-api`, `enrich`,
`diet-logging` §1–3, udhaar detection (§4–6), the dish suggestion engine.
