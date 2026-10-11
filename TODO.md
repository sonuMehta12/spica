# TODO

Small, concrete jobs. **`feature.json` is the roadmap** — that holds features,
their status and their spec. This file holds the work that does not deserve a
feature entry: one-off scripts, data collection, chores.

A line moves out of here when it is done, not into a "done" section — git
remembers.

---

## Agent

- [ ] **Nudges: walk through how they work end to end, then finish them.**
      Built 2026-10-08 and seen live on the emulator: the bell, the Nudges
      page, Your day, Meals today, Workout today, and the `morning_brief` job
      that writes them (`spec/in-progress/nudges.md`). Built in one day across
      three branches, so first a walkthrough of the path a nudge takes — the
      schedule row, the dispatcher (`scripts/run_due.py`, `app/agent/jobs.py`),
      the brief (`app/agent/brief.py`), the `nudges` row, `GET /nudges`, the
      bell's dot, the card, the page — as a diagram, with one brief run by
      hand and followed through. Then what is still owed:
      (1) **every account gets its default Daily runs at sign-up** — the
      categoriser and brief migrations seed only the oldest user, so the
      account the phone signs in with had none until a one-off script added
      them;
      (2) the brief stays silent on Workout when a workout is already logged
      (rule 2 — today it writes "A workout is already recorded");
      (3) phone notifications (WorkManager, two channels, quiet hours);
      (4) the reminder card with *Done* and *Tomorrow*, and `POST
      /nudges/{id}/snooze`;
      (5) `dinner_check`, and the categoriser writing a `review` nudge;
      (6) Workout today's *Do this instead* — the plan returns no alternative;
      (7) Daily runs says "Nothing runs on its own yet" when its fetch fails —
      unknown shown as zero;
      (8) merge `nudges-android-fix2` into `claude/android`.

- [ ] **Notifications: review the notification spec end to end.** The bell,
      the Nudges page and the phone's channels were built in a day
      (`spec/in-progress/nudges.md`); read the spec thoroughly before the
      phone side grows. Fold in: a **notification when a commitment is due**
      (`spec/done/commitments.md` — `due_day`, a line owed above 0, not
      skipped) and the evening brief (`spec/in-progress/schedules.md`).

- [ ] **Money: why the phone said ₹0 left with nothing spent shown.** On
      2026-10-09 the phone's Money widget showed *Left to spend today ₹0*,
      everything committed, while another screen showed *Today ₹529 /
      ₹1,180*. Build `7b0d97d` already flags spend over the limit, so the
      phone must have read today's spend as 0 — a different account, a
      different day, or the app's live rows disagreeing with the server's
      `spent_today_paise`. Find which, and make the phone and the web agree on
      today's limit. `money-over` (`34e029a`) now shows the overage as −₹ in
      red. Also: logging money lent out adds the row to `tx` at once
      (`SpicaViewModel.kt` ~1113), which may count it as today's spend until
      the next reload.

- [ ] **Design the diet suggestions properly, then test them on real data.**
      *Home's half is built* — `spec/in-progress/today-plan.md`: the rest of the
      day planned to the targets, ideas beyond the library, pictures. The chat's
      `suggest_dishes` still only filters; it should read the same plan.
      Today `suggest_dishes` only offers what the dish library and the pantry
      hold, so a new account with an empty pantry gets nothing ("dish
      suggestions bhi nahi mile"). Wanted: a fallback to plain suggestions
      from the model when the library and pantry are empty, said as an idea,
      not from their dishes; and a ranking that weighs what is left of today's
      protein and calories against the targets, their eating pattern, and
      what is in the pantry. Dish extraction from what they say, and pantry
      moves, belong to the same pass. Test it on its own, on an account whose
      profile, pantry and history are filled in properly.

- [ ] **Workout suggestions from a cold start, then personal ones.**
      *Home's half is built* — the plan's Workout widget suggests from the week
      with ideas on a thin library. The chat's `exercises` still only filters.
      `exercises` only filters the library, so a new account hears "library
      mein nahi mila" and nothing else. Wanted: sensible suggestions with no
      history (a muscle group and minutes are enough to start), then ones
      shaped by what they have done and how often.

- [ ] **Places: scope and tools before building more.** Pinning needs
      coordinates the agent cannot get ("coordinates bhi chahiye"). Two jobs
      to design: places read from payments in the background (a payee seen
      at one spot again and again becomes a pin), and naming a place by
      saying it ("this location is Blue Tokai") so the agent updates the
      pin. Decide the scope and the tool calls first; `spec/in-progress/
      places.md` is where it goes.

- [ ] **Project colours from the Work hue, not the old palette.** The bars on
      To-do and Reports draw each project's stored colour, which the server
      picks from the pre-Jamun palette (`PALETTE` in `backend/app/projects.py`:
      greens and ambers — amber is the estimate dot's alone). New colours
      come from the work hue's family (`THEME.md` § Colour), and existing
      rows are migrated.

## Data

- [ ] **Populate `foods` with commercial and packaged food sold in Delhi.**
      Write a scraper or extraction script rather than typing rows. Scope it to
      what is actually eaten — the pantry, the Nutrition Ref sheet and the brands
      in `Purchases` are the starting list, not the whole Indian market.
      Every row lands as `origin = 'cortex'`, `nutrition_source = 'label'` where
      a label was read and `'reference'` where a database was.
      Blocks nothing, but the recipe and portion features are thin without it.
      See `spec/done/diet-data-model.md` § `foods`.

- [ ] **Fill `measures` with the portions an Indian plate is spoken in.**
      It has *katori*, *muththi*, *chammach*, *glass*; it needs *roti*,
      *chapati*, *paratha*, *anda*, *slice*, *bowl*, *plate*, *thali*. Until it
      does, "2 roti" resolves to the food but carries no weight, so the agent
      asks how much every time — correct, and tiring. One row each, with the
      grams the user actually eats rather than a textbook figure.
      See `spec/agent.md` § Open.

## Chores

- [ ] **Finish the Spica rename: the Google client, then the old app.**
      Cortex became Spica on 2026-10-09 (`CLAUDE.md`); the
      app is `com.sonu.spica`. Google sign-in on Android is tied to the
      package, so the `cortex-508717` project needs a new OAuth client of
      type *Android* — package `com.sonu.spica`, the same debug SHA-1 as the
      old one — before the phone can sign in. Then uninstall the old
      `com.sonu.cortex` from the phone and the emulator; the server holds
      the data, so nothing is lost.

- [ ] **Publish the Google consent screen before anyone else signs in.**
      The OAuth client `cortex-508717` is in *Testing*, where **only addresses
      on the test-user list can sign in at all**, up to 100 of them, added by
      hand in the console. A friend who is not on that list is refused by
      Google before the app is ever reached. Publishing to Production removes
      the list and needs no Google review, because sign-in asks only for
      `openid`, `email` and `profile`. Who may then create an account stays
      `ALLOWED_EMAILS`, which is in this repo and needs no console.
      (Testing's seven-day consent expiry is about stored refresh tokens and
      does not reach this app — it asks for none.)
      See `spec/in-progress/sign-in.md` § What this needs outside the repo.

- [ ] **Phone testing of sign-in needs an https origin.**
      Google rejects raw IPs as authorized JavaScript origins and allows plain
      http only for localhost, so `http://192.168.1.33:5173` — how the phone
      reaches the laptop — can never be authorized. Either tunnel the page to
      an https hostname or wait for the hosting move, which is the next release
      prerequisite anyway. The laptop browser is unaffected.

- [ ] **Delete the downloaded `client_secret_*.json`.**
      The ID-token flow never exchanges a code, so the secret in it is unused
      and only the client ID was taken. A secret nothing reads is a secret
      waiting to leak.

- [ ] **When the domain and hosting land, three things change together.**
      Vercel serves the page; it is the wrong host for this API — FastAPI holds
      a connection pool, runs alembic on deploy and has a nightly categoriser,
      none of which fit a serverless function. Page on Vercel, API on a host
      that runs a process (Fly, Railway, Render), Postgres on Neon as
      `spec/backend.md` already decided. Then:
      (1) add `https://<domain>` to the OAuth client's authorized JavaScript
      origins — the port-less https origin, not the localhost one;
      (2) widen `cors_origin_regex` in `backend/app/config.py`, which today
      matches `http://` and private ranges only, so the deployed page would be
      refused by its own API;
      (3) set `VITE_API` on Vercel, since the API is no longer on the host that
      served the page.

---

## Landing

- [ ] **Rewrite the landing page's copy — brainstorm first, then write.**
      The page explains what Spica does; it should say what it does *for you*.
      Handcrafted, marketing-grade, short (the page's "less text" rule stands).
      The brief, in the user's words: save far more without giving up your
      lifestyle, because you finally see where the money goes and what your
      habits are; eat better because tracking stops being a chore; stay on
      top of work, with your next priority and top three tasks always on
      screen; and ask from anywhere — ChatGPT, Claude, WhatsApp, the app —
      against the same memory.
      To settle in the brainstorm, before a word is written: whether a figure
      like "3× more saved" can appear, and on what footing (the page's honest-
      copy rule: no number the product has not measured); and how "from anywhere" is
      said while only Claude is built.

- [ ] **Measure the landing page's numbers before it is deployed.** `RESULTS`
      (3×, 5×, 90%) and `GUESS_RATE` (9 in 10) in
      `frontend/src/landing/Landing.tsx` are placeholders. What each means: 3× —
      months the savings goal is hit, against the months before Spica; 5× —
      days a week on the calorie and protein targets, against the first two
      weeks; 90% — fewer tasks passing their due date undone. The
      categoriser's last evaluation was 74–83%; meals were never measured.

- [ ] **Set the Google Play link on the landing page.** `APP_URL` in
      `frontend/src/landing/Landing.tsx` is empty, so *Download on Google Play*
      goes nowhere yet. Paste the listing's URL there — it is the one line.
