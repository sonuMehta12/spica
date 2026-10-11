# backend

Empty on purpose. Nothing here is decided yet.

The API that the web version in `frontend/` will talk to, and that the Android
app will talk to later. Same API for both — the web version comes first so that
the mobile app is built against something already proven.

## Before any code lands here

Two things have to be settled first, and both are product questions rather than
technical ones:

1. **`spec/PRD.md`** — not written yet
2. **Where payments actually come from** — notification listener, RBI Account
   Aggregator, or manual entry. This shapes the entire Paisa ledger, so the
   schema should not harden before it is answered.

## What is already decided

From the **Substrate** design note, the data model these APIs serve:

- **Two stores, not one.** A *ledger* of things that happened (payments, meals,
  steps, sleep) — append-only, timestamped, never edited; corrections are new
  entries. And a *library* of things kept (articles, recipes, places, workouts) —
  curated, filed, mutable.
- **One envelope** on every record: `id`, `type`, `createdAt`, `source`,
  `confidence`, `tags[]`, `deletedAt`. Foreign shapes exist only inside adapters.
- **`localDay` stored alongside UTC.** India is UTC+5:30, so an 11:30pm entry
  lands on the wrong day if the local day is computed at read time.
- **An append-only event log** — `{seq, id, op}` — so any client syncs from its
  own cursor. This is what makes offline-first and incremental backup possible.
- **Local-first.** The device holds SQLite and is the source of truth for reads;
  this server is sync and compute, not the critical path.

No stack chosen yet. Whatever it is, it should be something the user can run on
their own infrastructure — the IP stays personal.

## Deploy

Where each piece runs, why, and what it costs: **`spec/in-progress/deploy.md`**.
The API and the web app are two Vercel projects, the database is Neon, the
hourly tick and the weekly backup are GitHub Actions
(`.github/workflows/tick.yml`, `backup.yml`). Every setting the API takes is
in `deploy.env.example`.

`<api>` and `<web>` below are the two production addresses, as
`https://<api>.vercel.app` and `https://<web>.vercel.app`. Each is what the
project's **Settings → Domains** shows — not the name typed when making it:
when a name's `.vercel.app` is taken, Vercel keeps the project name and gives
the address a suffix. The addresses go in six places, and all six must match:
`PUBLIC_URL`, `APP_URL` and `CORS_ORIGIN_REGEX` on the API project,
`VITE_API` on the web project, the Google client's JavaScript origin (step 9),
and `spica.apiBase` on the phone (step 13). A wrong one shows up only as a
sign-in that fails — or, pointed at a stranger's address, as a Google sign-in
token sent to them.

### First deploy — once, by the owner

1. **Repository.**
   - Commit everything on `claude/work-sync`. The personal rows in
     `backend/data` (diet, dishes, memory, work) are untracked and ignored —
     the commit records their removal, and the files stay on the laptop for
     the import scripts. The deploy files are new and
     untracked, and `git commit -a` leaves them out: `.github/`,
     `backend/vercel.json`, `backend/.vercelignore`,
     `backend/scripts/vercel_build.py`, `backend/deploy.env.example`,
     `backend/tests/test_deploy.py` and `frontend/vercel.json`. Without
     `vercel.json` the API still deploys — in the US, with every preview
     built and `backend/data` inside the function; without `.github/` there
     is no tick and no backup. `git status --short` must print nothing.
   - Merge `claude/work-sync` into `main`.
   - **Give GitHub a fresh history.** The old commits still hold those rows,
     so `main` is pushed as one new commit and the full history stays on the
     laptop, in a branch that is never pushed:
     ```bash
     git branch archive/full-history main
     git checkout --orphan fresh main
     git commit -m "Spica"
     git branch -M fresh main
     ```
     Nothing is lost: `archive/full-history` holds every old commit. Never
     push it, or any other old branch (`claude/*`) — they carry the rows.
   - Create a new **private** repository under the personal GitHub account
     (Vercel Hobby cannot import an organisation's). Check
     `git config user.email` is a verified email on that account — only the
     owner's commits deploy — then add the remote and push only `main`:
     `git push -u origin main`. Confirm on GitHub that `backend/data` holds
     only `workouts/exercises.csv` and that the history is one commit.
   - **Turn both workflows off straight away:** Actions → tick → its menu →
     Disable workflow, the same for backup (or `gh workflow disable tick` and
     `gh workflow disable backup`). Pushing `main` starts the hourly tick,
     whose secrets arrive in step 11 and whose tables arrive in step 5; until
     then every run fails and GitHub emails each one. Step 12 turns them on.
2. **Vercel account.** Sign up with GitHub, Hobby. Before anything deploys:
   Team Settings → Data Preferences → opt out of AI model training.
3. **Neon.** Sign up with GitHub and create a project: Postgres **18** (Neon's default; the laptop runs 17, and the migrations run on both), AWS
   **Singapore** (`aws-ap-southeast-1`), compute **0.25 to 0.25** CU, scale to
   zero left on. Connect → **connection pooling off** → copy the **direct**
   string (no `-pooler` in the host). It goes in as given, `sslmode` and all.
4. **Names.** Choose the two project names. Open `https://<name>.vercel.app`
   for each first: Vercel's `DEPLOYMENT_NOT_FOUND` page means the address is
   most likely free; anything else means it is someone's — choose another.
5. **API project.** Vercel → Add New → Project → the repository, Root
   Directory `backend` (FastAPI is detected), the API's name. Copy
   `deploy.env.example` to `deploy.env` (git ignores it), fill it in, and
   paste it into Environment Variables; then **delete `deploy.env`** — the
   password and the key live in Vercel and GitHub, nowhere else. Deploy: the
   build runs `scripts/vercel_build.py`, which migrates the empty database to
   head. Then Settings → Domains: that address is `<api>` from here on. If it
   is not the one `PUBLIC_URL` was given, fix `PUBLIC_URL` and redeploy.
   Deployment Protection stays on Standard.
6. **Check it.** In a private window, `https://<api>.vercel.app/health` says
   `"status": "ok"`, Postgres 18, and `vector`, `pg_trgm`, `unaccent` among
   the extensions. `curl -sI https://<api>.vercel.app/health` shows an
   `x-vercel-id` header naming `sin1`: the function runs in Singapore, so
   `vercel.json` made it into the commit. Until both hold, that address goes
   nowhere else.
7. **Claim the seeded user** — before anyone signs in. In Neon's SQL Editor
   (what `scripts/claim_user.py` does), with the address exactly as Google
   shows it on the account — Gmail's dots included, since the match is
   letter for letter:

   ```sql
   UPDATE users SET email = lower('<you>@gmail.com')
   WHERE google_sub IS NULL AND (SELECT count(*) FROM users) = 1
   RETURNING id, display_name, email;
   ```

   It must return **one row**, Sonu's. None means the table holds more than
   one user or the row is already signed in: stop and look
   (`SELECT id, display_name, email, google_sub FROM users`). Your address is
   not in `ALLOWED_EMAILS`, so a sign-in the claim does not match is refused
   as invite-only: run the same statement with the address corrected, and
   sign in again.
8. **Web project.** Add New → Project → the same repository, Root Directory
   `frontend` (Vite is detected), the web's name. Environment Variables:
   `VITE_API=https://<api>.vercel.app` (no trailing slash, the address step 6
   checked) and `VITE_GOOGLE_CLIENT_ID`, the same Web client ID as the API's.
   Deploy. Both are read at build time: a change needs a redeploy. Then
   Settings → Domains: that address is `<web>`. If it is not the one
   `APP_URL` and `CORS_ORIGIN_REGEX` were given, fix both on the API project
   and redeploy it.
9. **Google sign-in.** Google Cloud, project `cortex-508717` → Credentials →
   the Web OAuth client → Authorised JavaScript origins → add
   `https://<web>.vercel.app`.
10. **Who may sign in.** OAuth consent screen: add each friend's Gmail as a
    test user, or publish the app. Their addresses — not yours — go in
    `ALLOWED_EMAILS` on the API project (a change there needs a redeploy).
11. **GitHub secrets.** Repository → Settings → Secrets and variables →
    Actions: `DATABASE_URL` (the same Neon string, as given),
    `ANTHROPIC_API_KEY`, and `BACKUP_PASSPHRASE` — a long random one kept in a
    password manager; losing it loses every backup. Leave the log retention
    setting alone: it also caps the backup's 30 days.
12. **Turn the workflows on and run them once.** Actions → tick → Enable
    workflow (or `gh workflow enable tick`), then Run workflow. It ends with
    `nothing due` or a count per job — never what a job found. Enable and
    run backup the same way: an encrypted `spica-<day>.dump.gpg` artifact
    appears.
13. **The phone.** On the laptop, `android/local.properties` gets
    `spica.apiBase=https://<api>.vercel.app`, the address step 6 checked.
    Build and install the debug build (`./gradlew :app:installDebug`,
    `android/README.md`), and sign in with Google.
14. **Smoke test.** On mobile data (Jio, Airtel), open `/health`. Sign in on
    the web and on the phone; say one thing and see it logged; open Home.
    Vercel keeps logs for an hour — look while it is fresh. In Neon,
    `SELECT id, display_name, email, google_sub IS NOT NULL FROM users`
    returns one row, Sonu's, with `true` — the claim held and no second
    account was made.
15. **The first week.** Neon's Usage page: CU-hours on pace for well under
    100 a month. GitHub's Actions tab: the tick ran every hour, and no banner
    says a scheduled workflow was disabled.
