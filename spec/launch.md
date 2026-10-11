# Spica — what it is, and what is left before it goes live

> Status: **written 2026-10-07** from the repo's own state — `feature.json` on
> both working branches, the specs, `TODO.md`. A snapshot of what is owed, not
> a log: tick items off here, and move a line to its own spec when it grows.
> **Live** means: the Android app on Google Play, the web version and the
> landing page on a public HTTPS domain, one backend behind both.

---

## What Spica is

**Money, food and work in one conversation.** Spica is a personal OS for one
person. There are no forms: you say *"Rapido home, one sixty"*, *"2 roti aur
dal"* or *"novachan me task add kar do"*, and the agent logs it, sorts it and
adds it up. The premise the whole product hangs on: **agent hi app hai** — the
conversation is the interface, and the deck of cards above it is the glance.

### Three modes

| Mode | What it does |
|---|---|
| **Paisa** — money | Logs a spend from a sentence and guesses its category, marked as a guess until confirmed. A daily spend limit worked out from what is committed and what is left. *Udhaar* — money lent and borrowed, and the repayments that settle it. A nightly categoriser that takes a second look at payments it was unsure of. |
| **Diet** — food | Logs a meal from a sentence; the model prices the plate — calories, protein, carbs, fat, fibre — and learns from every correction. A pantry the meals draw down. Habits ticked daily, workouts, weight, sleep. |
| **Work** — kaam | Tasks in projects the person makes, each with a description the agent reads to file a task where it belongs. Add, tick, move and ask about tasks by chat. Linear issues and meeting action items arrive through a Claude routine, and a task ticked in Spica is a reminder to move it in Linear — Spica never writes there. |

### Where it lives

- **The Android app** — the main surface. Native (Kotlin, Jetpack Compose), the
  same API as the web. In build.
- **The web version** at `/app`, and **the landing page** at `/`.
- **Claude**, through Spica's own MCP server: a scheduled routine fills the
  task list from Linear and Wispr Flow.

### What it holds itself to

- **Honest numbers.** A value the agent worked out carries an amber dot until
  the person confirms it, and a weight they gave as a guess until an exact one
  replaces it. Unknown is never shown as zero. A sentence about the
  person's data is never stored — every note is computed from live rows.
- **The person's data stays theirs.** Per-item delete everywhere, and deleting
  the account removes every row. No export, no SMS or call-log access, no
  Accessibility Service.
- **One agent voice**, in the person's own register — Hinglish as they write it.

### How it is built

FastAPI and Postgres on the server, one seam to the language model
(`backend/app/llm.py`), a React web version, a native Android app. Every
backend feature lands with its tests — 367 of them on 2026-10-07. Forty
features are done (`feature.json`).

---

## Before it goes live

Ordered by what blocks what. **You** marks a decision or an account only the
owner can make; **build** marks code.

### 1. Decisions — these shape everything after them

- [ ] **Payment capture** (**you**). Notification listener, RBI Account
      Aggregator, or manual only. The one item marked *blocked*: it shapes the
      Paisa ledger, so it is decided before the schema hardens. Launching with
      manual logging and adding capture later is a legitimate answer — but it
      is an answer to write down, not a default. `spec/paisa-categorise.md`,
      `spec/capture.md`.
- [ ] **Who can sign up on day one** (**you**). `ALLOWED_EMAILS` — a list, or
      `*` for anyone. The model key is server-wide, so every user's turns are
      one bill; `DAILY_TURN_LIMIT` and `DAILY_SIGNUP_LIMIT` cap it.
      `.env.example` says to open it only once a privacy policy exists.
- [ ] **The deploy choices** (**you**). The web version as a Render Static
      Site, or the connector's approval page moved to the backend; plan sizes;
      a domain; production starts with an empty database.
      `spec/in-progress/deploy.md` § Open.
- [ ] **The landing page's numbers** (**you**). `3×`, `5×`, `90%` and *9 in
      10* in `frontend/src/landing/Landing.tsx` are placeholders. Each is
      measured or removed — the page's own honest-copy rule.

### 2. One codebase

- [ ] **A private GitHub remote** (**you**). There is none; the work exists on
      this laptop only.
- [ ] **Bring the branches together** (**build**). `main` was last moved on
      2026-09-12. `claude/work-sync` is 10 commits ahead of it and
      `claude/android` 14, diverged at `c8d116f`, both touching the card
      redesign. Merge both into `main`, resolve, run every test, and release
      from `main`.

### 3. Server and hosting

- [ ] **Render** (**you** for the account, **build** for the config).
      Always-on paid web service and paid Postgres — a free web service sleeps
      after fifteen minutes, and a free database is deleted 44 days after it
      is made. A Cron Job every five minutes for `scripts/run_due.py`, which is
      what runs the nightly categoriser; it replaces the crontab line
      `spec/in-progress/schedules.md` still owes. `alembic upgrade head` as the
      pre-deploy step. `spec/in-progress/deploy.md`.
- [ ] **Check Render's Postgres has the extensions the migrations create**
      (**build**) — `vector`, `pg_trgm`, `unaccent`.
- [ ] **Backups of the production database** (**you**). Which plan keeps what,
      and a restore tried once before anyone's ledger depends on it.
- [ ] **A domain and HTTPS** (**you**), then three settings together
      (**build**): the domain added to the Google sign-in client's authorised
      origins; `CORS_ORIGIN_REGEX` widened to the deployed app; `VITE_API`,
      `PUBLIC_URL` and `APP_URL` set for production. `TODO.md` § Chores.
- [ ] **Secrets** (**you**). The model key in Render only. Delete the
      downloaded `client_secret_*.json` — nothing reads it.

### 4. Sign-in

- [ ] **Publish the Google consent screen to Production** (**you**). In
      *Testing*, only addresses on a hand-kept list can sign in at all. No
      review is needed — sign-in asks only for `openid`, `email`, `profile`.
- [ ] **A sign-in client entry for the release key** (**you**). Android
      sign-in is tied to the signing key's SHA-1; Play's app-signing key needs
      its own entry (`android/README.md`).
- [ ] **Sign-in verified against real Google** (**build**), on the deployed
      web and a release build — `spec/in-progress/sign-in.md` is built but
      marked unverified.

### 5. Google Play

- [ ] **A Play developer account** (**you**).
- [ ] **A release signing key** (**you**) — release builds are signed with the
      debug key until there is one.
- [ ] **Play's Health Connect declaration** (**you**) — Activity reads steps,
      active calories and exercise sessions from Health Connect, and Play
      asks every app that does to declare why before it can be listed.
- [ ] **The release build points at the deployed API** (**build**) —
      `spica.apiBaseRelease`, HTTPS only.
- [ ] **A privacy policy at a public URL** (**you**, **build** for the page).
      Required by Play, and the condition `.env.example` sets for opening
      sign-ups. What is kept — money, meals, tasks, the conversation; that the
      language model provider processes what is said; that nothing is sold;
      how to delete.
- [ ] **Account deletion that Play accepts** (**build**). `DELETE /users/me`
      exists and removes every row. Play also asks for a web page where
      deletion can be requested without the app.
- [ ] **The store listing** (**you**) — name, a short description of at most
      80 characters, a full description, screenshots, icon, feature graphic;
      the content rating questionnaire; the **Data safety** form, which must
      match the privacy policy.
- [ ] **A closed test before production** (**you**). New personal developer
      accounts must run one — at the time of writing, twelve testers for
      fourteen days. Check the current rule in the Play Console; it sets the
      earliest launch date.
- [ ] **The Play link on the landing page** (**build**) — `APP_URL` in
      `Landing.tsx` is empty, so *Download on Google Play* goes nowhere.

### 6. Product — finish what is in progress

- [x] **Chat quality** (**build**, with you for the failing turns) — done
      2026-10-10: 96% of cases and 99% of turns on Luna, and the eval gates
      every prompt change. `spec/done/chat-quality.md`.
- [x] **Onboarding** (**build**) — done 2026-10-10: the replay drawn with
      the app's own card parts, the step copy settled, a sixth step for what
      you pay every month. `spec/done/onboarding.md`.
- [ ] **The landing copy** (**build**, after a brainstorm with you). It says
      what Spica does; it should say what it does for you.
      `TODO.md` § Landing.
- [ ] **The Jamun redesign** (**build**) — in progress on the web, done on
      Android (`1f09ef4`).
- [ ] **Diet and workout suggestions from a cold start** (**build**) — a new
      person has no pantry and no history, and the suggestions assume both.
      `TODO.md`.
- [ ] **One full end-to-end run on the deployed stack** (**build**) — sign up,
      log a spend, a meal and a task, delete each, delete the account — and
      the eval (`backend/evals/n2n_eval`) against production's model settings.

### 7. Worth having on day one, not blocking

- Error alerts and uptime on Render, so a broken night is noticed before a
  user does.
- The `foods` and `measures` libraries filled (`TODO.md` § Data) — without
  them *"2 roti"* is asked about every time.

---

## After launch — deliberately later

Each is written down with its reason; none blocks going live.

| Item | Where |
|---|---|
| The morning brief — Spica prepares the day and speaks first; to brainstorm | `spec/in-progress/morning-brief.md` |
| Home-screen widgets (four, via Glance) | `spec/widgets.md` |
| Encrypted, restore-only backup of the phone's data | `spec/substrate.md`, `feature.json` § backup |
| Local-first storage on the phone, and the sync log it needs | `spec/notes.md` § Event log |
| Work sync live: Spica as a claude.ai connector and the cloud routine — a personal feature, ready the day the server is deployed | `spec/work-sync.md` |
| Spica's tools in Claude and other assistants | `spec/agent-everywhere.md` |
| Share-sheet capture, and enriching a shared link | `spec/capture.md` |
| Udhaar detection and reminders | `spec/udhaar.md` |
| Commitments replacing the fixed-cost flags | `spec/archive/commitments.md` |
| Gmail as a work source; moving Linear issues from Spica; deleting a task from chat | `spec/notes.md` |
| The call recorder; shared memory with Claude | `spec/archive/` |
