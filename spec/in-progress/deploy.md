# Deploy — Spica on Vercel, Neon and GitHub, for nothing

> Status: **settled 2026-10-11 — everything deploys: the web app, the API and
> the database.** The private repository exists (the owner's personal GitHub
> account) and holds one fresh commit; the rest is the runbook in
> `backend/README.md` § Deploy, run by the owner.
> Replaces the 2026-09-27 draft, which put everything on paid Render: the
> budget is zero, and Render's free tier is already in use elsewhere.
> Surface: backend · frontend · android (the API address it is built with).
> Needed by: the Android app away from the laptop's Wi-Fi, and
> `spec/work-sync.md` (a cloud routine reaches only a public URL).

## The problem

Spica runs on the laptop. The phone reaches it only on the same Wi-Fi, only
while the laptop is awake, and only at an address baked into the APK that
changes when the router hands out a new one. Two or three people will use it,
the owner every day, and there is no money for hosting.

## What runs where

| Piece | Where | Plan |
|---|---|---|
| API — FastAPI, the MCP server and OAuth, one ASGI app | **Vercel**, project root `backend/` | Hobby. One Fluid function in `sin1` (Singapore), up to 300 s a request |
| Postgres 17 | **Neon**, AWS Singapore (`aws-ap-southeast-1`) | Free. Compute fixed at 0.25 CU; scales to zero after 5 minutes |
| Migrations, then the exercise library | Vercel's build step on the API project | `alembic upgrade head`, then `data/workouts/exercises.csv` loaded (idempotent on name); production builds only |
| The schedules tick — `scripts/run_due.py` | **GitHub Actions**, private repo | Free. Hourly at minute 35 UTC (:05 past each hour IST) |
| Web app — landing at `/`, the app at `/app`, `/connect`, `/film` | **Vercel**, second project, root `frontend/` | Hobby, static, every path rewritten to `index.html` |
| Backup | **GitHub Actions**, weekly | `pg_dump`, encrypted with a passphrase, kept as a 30-day artifact |

Everything signs up with GitHub and none of it asks for a card. Over a limit,
each one stops rather than bills: Neon suspends compute until the next month
with the data kept, and Vercel pauses the deployment (a 503) for up to 30
days. API and database sit in the same AWS region, so a turn's 20–40
sequential queries stay at a few milliseconds each; from Delhi, Singapore adds
tens of milliseconds per request, which is nothing next to the model. The
unmeasured cost is the connection: without a pool (*Cold starts*), every
transaction opens its own — TCP, TLS and SCRAM through Neon's proxy — and a
turn commits several times.

**Expected use, 2–3 people.** Vercel: about 10–30 of 360 GB-hours of memory,
under 1 of 4 Active CPU-hours (waiting on the model or the database is not
Active CPU), about 15,000 of 1,000,000 invocations. Neon: about 30–40 of 100
CU-hours (the tick is about 16 of them), under 50 MB of 1 GB (the dev database
is 13 MB). GitHub Actions: about 750 of 2,000 minutes. The model bill is
OpenAI's and unchanged; `DAILY_TURN_LIMIT` and `ALLOWED_EMAILS` bound it.

## Cold starts

Neither the function nor the database is always on. Vercel pauses an instance
when its last request finishes; a new instance pays the Python import (0.6 s
measured) and the runtime's start, about 1–3 s. Neon wakes in a few hundred
milliseconds. The first open of the day can take 2–4 s once; the phone allows
10 s to connect and 120 s to read. With `DB_NULL_POOL=true` a paused instance
holds no database connection, so nothing goes stale and nothing keeps Neon
awake. The price is a connection per transaction rather than per request: a
session hands its connection back at every commit and `NullPool` closes it, so
the next query in the same request connects again. If that shows in a turn's
time after deploy, the next step is a pool of one per instance with
`pool_pre_ping` and a short `pool_recycle`, weighed against a connection
held through a pause.

What a new instance loses: the in-process plan cache (`app/agent/plan.py`) and
the ideas cache, so the first Home of a new instance recomputes the plan with a
model call.

## The tick is hourly, and why

Neon charges compute by the hour it is awake and sleeps 5 minutes after the
last query. Every tick opens a connection and reads `schedules`, so the
documented five-minute tick would keep the database awake all month — about
182 CU-hours against 100 — and stop it in the third week.

Hourly fits every job: the morning brief may run 08:00–10:59 IST, the
categoriser 20:30–23:59 IST, and both get three or four tries. `is_due` builds
the due time from today's date (`app/agent/jobs.py`), so a run's window closes
at midnight whatever its grace. A time a person edits in Profile is met within
the hour up to 23:05; **a time from 23:06 to 23:59 is never met** — the 23:05
tick is before it, and at 00:05 it belongs to the new day (*Open*). Each tick
costs about 5.5 minutes of 0.25 CU — about 16 CU-hours a month.

The tick's log says what ran and how many, never what it found
(`run_due.py --quiet`): GitHub keeps a run's log for 90 days, and a nudge's
line or a payment's lede would outlive the row it quoted, where per-item
delete cannot reach. Log lines keep their template and an exception its type,
not the values. The repository's log retention is left alone: the same
setting caps the backup's artifact.

There is no tick route, deliberately (`spec/in-progress/schedules.md`): GitHub
runs the existing script with the database URL and the model key as repo
secrets, so the app gains no public endpoint and no shared secret. **No uptime
pinger** may hit `/health` either: it would keep Neon awake for the same
reason.

## What the code changes

- **`app/config.py`** — `db_null_pool: bool = False`, and the database URL is
  normalised when it is read: `postgres://` and `postgresql://` become
  `postgresql+asyncpg://`, `sslmode=require` becomes `ssl=require`, and
  `channel_binding` is dropped. Neon (like every provider) hands out a string
  asyncpg cannot take — SQLAlchemy passes the query keys straight to
  `asyncpg.connect`, which has neither keyword — so a string pasted as given
  works.
- **`app/db.py`** — with `db_null_pool`, the engine uses `NullPool`: a
  connection per transaction, none held between requests. Set only on Vercel;
  local development, the tests and the tick keep the pool.
- **The root migration creates the extensions it and its successors need**
  (`CREATE EXTENSION IF NOT EXISTS` for `vector`, `pg_trgm` and `unaccent`).
  Until now only `backend/docker/init` and the tests created them, so a fresh
  database failed at the first `gin_trgm_ops` index. Databases already
  migrated never re-run it.
- **`[tool.vercel.scripts] build`** in `pyproject.toml` runs
  `scripts/vercel_build.py`: on a production build it migrates; on anything
  else it says so and does nothing. A failed migration fails the build, and the
  release before it keeps serving.
- **The production build loads the exercise library** after migrating:
  `data/workouts/exercises.csv` — forty general exercises, nobody's data, the
  one file in `backend/data` that stays tracked. The import is idempotent on
  name, so a fresh database gets the library with no extra step and a later
  build only corrects it; a person's own fields on an exercise are never
  reset. The import reads the settings' normalised URL, so Neon's string
  works there too.
- **`httpx` moves into the dependencies** — `app/images.py` imports it at
  runtime and it arrived only through another package.
- **`run_due.py` and `jobs.py` say hourly**, and why, where they said every
  five minutes. `run_due.py --quiet` prints counts only; `run_due` hands each
  row back with its result, so a failure reads as one.
- **`frontend/package.json` pins Node 22**, so Vercel's default does not decide
  the Vite build.

## Files that hold the setup

| File | What it says |
|---|---|
| `backend/vercel.json` | Region `sin1`; the function's 300 s; `excludeFiles` for `tests/`, `evals/`, `data/` and `docker/` — `backend/data` holds personal rows that must never ship inside the function; preview builds skipped |
| `backend/.vercelignore` | What a `vercel deploy` from `backend/` never uploads: `.env`, `deploy.env`, `data/`, the eval reports |
| `backend/scripts/vercel_build.py` | The migration on production builds |
| `backend/deploy.env.example` | Every setting the API project needs, with what to put in it; the filled copy is never committed |
| `frontend/vercel.json` | Every path to `/index.html` |
| `.github/workflows/tick.yml` | The hourly tick, quiet, and a button to run it by hand |
| `.github/workflows/backup.yml` | The weekly encrypted dump |

## Settings

**Vercel, API project** (`backend/deploy.env.example`):

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon's **direct** connection string (pooling off, no `-pooler` in the host), pasted as given |
| `DB_NULL_POOL` | `true` |
| `OPENAI_API_KEY` | the key — here and in GitHub's secrets, nowhere else |
| `GOOGLE_CLIENT_ID` | the existing Web client ID, unchanged |
| `ALLOWED_EMAILS` | the friends' Gmail addresses — never the owner's, who gets in by the claim (*Starting data*) |
| `PUBLIC_URL` | `https://<api>.vercel.app` — the OAuth issuer and the base of `/mcp` |
| `APP_URL` | `https://<web>.vercel.app` — where `/connect` lives |
| `CORS_ORIGIN_REGEX` | the web origin, escaped: `^https://<web>\.vercel\.app$` |
| `DAILY_TURN_LIMIT`, `DAILY_SIGNUP_LIMIT`, `ONBOARDING_TURN_LIMIT` | as now |

**Vercel, web project:** `VITE_API=https://<api>.vercel.app` (no trailing
slash) and `VITE_GOOGLE_CLIENT_ID` as now.

**GitHub, repo secrets:** `DATABASE_URL`, `OPENAI_API_KEY`, and
`BACKUP_PASSPHRASE` for the backup.

The two production addresses are baked into the web bundle and the APK.
Each is what the project's Settings → Domains shows, not its name: when a
name's `.vercel.app` is taken, Vercel keeps the name and suffixes the address.
The address goes in six places — `PUBLIC_URL`, `APP_URL`, `CORS_ORIGIN_REGEX`,
`VITE_API`, the Google client's JavaScript origin and `spica.apiBase` — and
nothing points the web app or the phone at an address until its `/health`
answers with this database: a wrong one sends a Google sign-in token to
whoever holds it.

## The phone

A debug build with `spica.apiBase=https://<api>.vercel.app` in
`android/local.properties` talks to the deployed API from any network; the
debug network rule allows the laptop's HTTP, and HTTPS needs nothing. It is
signed with this laptop's debug key, whose Android OAuth client for
`com.sonu.spica` exists in `cortex-508717` (made 2026-10-11).

A **release** build — for the Play Store — is signed with a release key, and
needs its own Android OAuth client with that key's SHA-1, and
`spica.apiBaseRelease`. Not part of this deploy.

## Starting data

Production starts empty (`spec/launch.md`). The migrations seed one user named
Sonu with no email, holding the default schedules; the owner's address is put
on that row once, before the first sign-in, exactly as Google gives it. The
owner's address is kept out of `ALLOWED_EMAILS`, so a claim missed or mistyped
is refused at sign-in as invite-only — fixed by claiming again — rather than
creating a second user while the schedules stay with the first. Accounts created after that get no
schedule rows — friends get no daily runs until they do
(`spec/in-progress/schedules.md`).

## Rules and edge cases

- **No personal rows on GitHub.** Production starts empty, so the repository
  holds no data: the personal CSVs in `backend/data` (diet, dishes, memory,
  work) are untracked and ignored, and stay on the laptop for the import
  scripts. Their old commits are not pushed either — GitHub's `main` begins
  as one fresh commit, and the full history stays in a local
  `archive/full-history` branch that is never pushed. Only the exercise
  library (`backend/data/workouts/exercises.csv`), which is nobody's data,
  remains tracked.

- **Vercel Hobby is non-commercial.** The day Spica charges or shows ads, the
  API moves (see *Decided against*: Cloud Run) or the plan changes.
- **Opt out of training before the first deploy.** Vercel Hobby accounts are
  opted in to AI model training on code and build data by default (March 2026
  terms): Team Settings → Data Preferences.
- **The repository is private, under the owner's personal GitHub account.**
  Vercel Hobby cannot import an organisation's repository, and only the
  owner's commits deploy: the local git email must be a verified email on
  that GitHub account.
- **Deployment Protection stays on Standard.** It leaves the production
  domains public — the phone and claude.ai must reach them — and protects
  every preview URL.
- **Keep migrations additive.** A production build migrates before the new code
  serves; a later build failure leaves the schema one step ahead of the code
  still running.
- **Vercel keeps logs for one hour** on Hobby and only the three newest
  production deployments: an error a tester saw yesterday is gone, and a
  rollback is to one of the last three.
- **Neon keeps 6 hours of history and no backups**: the weekly encrypted dump
  is the backup. `CLAUDE.md` allows an encrypted, restore-only backup and
  forbids an export; this is the former, kept where only the owner can read it.
- **Watch the first week**: Neon's Usage page (CU-hours well under 100) and
  GitHub's Actions tab (a scheduled workflow can be disabled after long
  inactivity — it shows a banner).
- **Day one, on mobile data**: open the API's `/health` on Jio or Airtel. ISP
  blocks of shared hosting domains happen (`*.supabase.co`, Feb–Mar 2026); if
  `*.vercel.app` is ever blocked, a custom domain is the fix.

## Decided against

| Option | Why not |
|---|---|
| Render | Its free tier is already used on another project, and paid is out of budget |
| Railway | No free tier left worth the name: the $1 monthly credit runs an always-on 0.5 GB service for days, and a card is required since March 2026 |
| Koyeb | Announced in Feb 2026 that its free Starter plan will be removed (its pricing page now lists only paid plans), it is joining Mistral, and the free instance has no Asian region |
| Fly.io | A card on file after the trial |
| Google Cloud Run | The runner-up. It runs uvicorn exactly as on the laptop, with up to 60 minutes a request, but needs a billing account with a card and Indian identity verification, and budgets only alert. **Switch to it** if Vercel cannot run the app — `/mcp` failing on lifespan, the build unable to migrate, cold starts making Home unusable, a turn hitting 300 s — or when Spica goes commercial |
| Supabase for the database | Close second: Mumbai, and always on. Lost on no backups at all on Free, a small session-pooler client cap, a Data API to switch off, and the India block of `*.supabase.co` from 24 Feb to 4 Mar 2026. With an hourly tick, always-on stops mattering |
| Oracle Cloud Always Free (one VM for everything) | A card, a VM to patch and run, and reports of idle instances being reclaimed |
| Vercel Cron for the tick | Hobby allows once a day at most |
| A tick route called by a free pinger | A public endpoint and a shared secret the app does not otherwise need |

## Open

- **Schedule times after 23:05** — Profile takes them and the hourly tick
  never meets them (*The tick is hourly*). Either the time is refused past
  23:05, or `is_due` also counts yesterday's window while its grace lasts —
  which reverses the tested rule that a run's window closes at midnight
  (`spec/in-progress/schedules.md`).
- **The two Vercel project names** — the owner's choice; they become the
  addresses.
- **A custom domain** — not needed now; the fix if an ISP ever blocks
  `*.vercel.app`, and a later polish.
- **Before deploying, the work on `claude/work-sync` is merged to `main`** and
  pushed to the new private repository.
