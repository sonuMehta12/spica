# Sign-in — the lock on the seam

> Status: built 2026-09-15, unverified against real Google — the route, the
> seam, the door and 16 tests are in; the first live sign-in has not happened. Supersedes `spec/api.md` § Auth (one shared
> token, one user) and closes the deferral in `spec/notes.md` § Auth and the
> `users` table.
> Surface: both. Backend: `app/auth.py`, one new table, three columns, three
> routes. Frontend: one screen in front of `Boot`, one header on every call, an
> avatar and a sign-out row.
> Pairs with `spec/done/onboarding.md`, which starts the moment this ends.

## The problem

Every request is trusted. `app/auth.py` returns the oldest row in `users` and
nothing reads a header, so the app is safe only while it is reachable from one
laptop. The release queue names this the first prerequisite: friends cannot use
localhost, and the day the API has a public address, whoever finds it owns the
ledger. The seam was built for exactly this — *"auth lands inside this one
function and no endpoint changes"* (`spec/done/deck-api.md`) — and the shared
bearer token `api.md` sketched dies with the second user, because a secret in
five friends' hands cannot be taken back from one of them.

## What it does

### One door: Continue with Google

The web prototype renders the Google Identity Services button. The tap returns
a signed **ID token** to the page; the page posts it to the API; the API
verifies it with Google's public keys and answers with a Spica session token.

The Android app does the same thing through Credential Manager. Its
`serverClientId` is the **same Web client ID** the page uses, so the ID token it
receives is verified by the same route with the same check. One Google Cloud
OAuth client, one route, two clients. That is the whole reason Google is the
door and not a convenience: it is the only sign-in that costs the Android app
nothing extra.

```
POST /auth/google   { credential }        → 200 { token, user }
                                          → 403 not invited
DELETE /auth/session                      → 204   (this device signs out)
GET /users/me                             → gains email, avatar_url
```

`POST /auth/google`, in order:

1. Verify the credential: signature against Google's keys, `aud` equals the Web
   client ID, `iss` is `accounts.google.com`, `exp` in the future,
   `email_verified` true. `google-auth`'s `id_token.verify_oauth2_token` does
   all of it in one call.
2. Find the user by `google_sub`. **`sub` is the identity, email is a label** —
   Google says so plainly: an account can change its email, `sub` never changes
   and is never reused.
3. No user yet → if the row with this email exists and has no `google_sub`,
   link it (this is how the owner's seeded row gets claimed). Otherwise, if the
   email is on the invite list, create the user: `display_name` from
   `given_name`, `avatar_url` from `picture`, `email`, timezone default.
   Otherwise 403.
4. Refresh `display_name`-independent facts that Google owns — `avatar_url`,
   `email` — on every sign-in. The picture URL rotates; the row should not hold
   a dead one.
5. Insert a session, return the raw token once.

### What this needs outside the repo

One thing, and it is free: a **Google Cloud project with an OAuth 2.0 Client
ID of type *Web application***, created once in the Cloud console. It needs no
billing account, no Firebase project, and no SDK beyond `google-auth` on the
server — Firebase Auth is a separate product that would wrap this same
mechanism in a third party holding the user list, which § Decided against
rejects.

What the client ID carries:

- **Authorized JavaScript origins** — where the button may render:
  `http://localhost:5173` and `http://127.0.0.1:5173` in dev, the real origin
  later. Origins only; **Authorized redirect URIs stays empty**, because the
  ID token is handed to the page by the button and never bounces through a
  redirect.
- **The LAN address cannot be an origin.** Google rejects raw IPs, and allows
  plain `http` only for localhost. So `http://192.168.1.33:5173` — how the
  phone reaches the laptop today (`data/api.ts`) — can never be authorized.
  The page and the API may sit on different origins (CORS already allows it),
  but the *page* must be served from localhost or a real domain for the button
  to work. Phone testing of sign-in therefore waits for either a tunnel with
  an `https` hostname or the hosting move, and the hosting move is a release
  prerequisite anyway. Desktop browser testing is unaffected.
- **The OAuth consent screen**, type *External*. It starts in *Testing* and is
  **published to Production before the app goes to anyone else**. In Testing,
  Google itself only lets listed test users through — a hundred of them, added
  by hand — so a friend who is not on the list is refused before the app is
  reached, and the invite list would then live in two places with the console
  winning. Publishing needs no Google review here, because sign-in asks for
  `openid`, `email` and `profile` only: non-sensitive scopes, the tier that
  skips verification. Testing's seven-day consent expiry does not reach this
  app, which requests no offline access and stores no refresh token, but the
  test-user list alone is reason enough to publish. Who may create an account
  then stays `ALLOWED_EMAILS`, in this repo, where it changes without a
  console.

No refresh token is ever requested, and no Google API is ever called on the
user's behalf. The ID token is read once, at the moment of sign-in, and
thrown away; what the app keeps afterwards is its own session token. That is
why Google's offline-access machinery — refresh tokens, their expiry, the
re-consent it forces — does not touch this app at all.

The same client ID goes in the backend's `GOOGLE_CLIENT_ID`, in the page that
renders the button, and later in the Android app's `serverClientId`. Android
additionally registers its own client ID with the app's SHA-1 in the same
project — but the token it sends is still audienced to the Web client ID,
which is why the backend check does not change.

### Claiming the seeded row

The database has one user row today, created by the `4b1c9e7d2a10` migration
and named *Sonu*, and every imported row in the ledger points at its id. A
first Google sign-in that created a *new* row would leave all of it stranded
on a user nobody can sign in as.

So the row is claimed by email, once: `scripts/claim_user.py --email <address>`
sets `email` on the sole existing row. The first sign-in from that Google
account then finds it by email, links `google_sub` to it (rule 3), and the
ledger is under the account from the first second. No migration hardcodes an
address, and the script refuses to run if more than one user exists.

### The session

An opaque random token, 32 bytes, base64url. The database stores its SHA-256;
the raw value exists in the response and on the client, nowhere else. Every
request carries it:

```
Authorization: Bearer <token>
```

`current_user` reads the header, hashes it, looks the session up, bumps
`last_used_at`, returns `user_id`. No header, unknown hash, or a session past
`expires_at` → **401** with `WWW-Authenticate: Bearer`. `GET /` and
`GET /health` stay open. Expiry is 90 days after last use — a phone that opens
the app every week never signs in again; one left in a drawer does.

Sign-out deletes the row. That is the entire revocation story, and why a
database session beats a signed token here: the server touches the database on
every request already, so a stateless token buys nothing, and a stateful one
makes "sign out everywhere" a `DELETE ... WHERE user_id`.

### Who gets in

**The door is meant to be open — any Google account — and the setting that
opens it is one line, not a rewrite.**

`ALLOWED_EMAILS` is a comma-separated setting with one special value:

| value | who may create an account |
|---|---|
| `sonu@…,friend@…` | only those addresses |
| `*` | anyone with a verified Google email |

Signing in is never gated differently from signing up: an existing user always
gets in, whatever the list says. The list decides who may be *created*.

**Why a switch and not simply an open door.** The model key is server-wide
(`app/llm.py`) — there is no per-user key and no column to hold one. Every
turn any user takes is billed to the owner, with no ceiling. So the app ships
with the list naming real people, is used, and is opened by changing one env
var the day the ceiling below exists and the bill is understood. Building it
open on day one and discovering the cost afterwards is the same mistake with
a worse recovery.

### The ceiling

Because the key is the owner's, an open door is an open tab. Two limits, both
per user per local day, both plain settings:

- `DAILY_TURN_LIMIT` — agent turns. Past it, the agent replies in its own
  voice that it is done for today and comes back tomorrow; every non-agent
  route keeps working, so the ledger, the cards and the deck never go down
  with it. A user who has hit it can still log, read and correct — they just
  cannot talk.
- `DAILY_SIGNUP_LIMIT` — new users created in a day. A door that can be opened
  by a link on the internet can also be walked through by a script; this caps
  the damage at a day's worth.

Neither is a quota screen and neither is sold. They exist so that opening the
door is a decision with a known worst case.

### Frontend

- **One client.** The ~20 bare `fetch` calls in `data/api.ts` collapse into one
  helper that sets the header and turns a 401 into a `signedOut` event. Today a
  401 is indistinguishable from a 500 at every call site; this is the change
  that makes it distinguishable.
- **Boot** grows one state in front of `loading`: no token → the sign-in
  screen. It is the door described in `onboarding.md`; this spec owns only
  the button on it.
- The token lives in `localStorage` under `cortex.session`. Signing out clears
  it and returns to the door.
- **Avatar.** `avatar_url` replaces the green initial in the Drawer and appears
  in the Profile header; the initial stays as the fallback when the URL is
  empty or fails to load.
- **The email is shown**, in mono under the display name in the Profile header,
  where the mono subtitle sits today. It is the only place in the app that
  answers *which account am I signed in as*, and that question has to be
  answerable before someone taps sign-out.
- **Sign out** is a row in the Drawer footer, under the wordmark. Nothing else
  moves.
- **The product name is a constant**, not a string in six components. `Spica`
  is the name; `frontend/src/brand.ts` is where it lives, and the door, the
  greeting and the Drawer wordmark read it from there. The `localStorage`
  namespace lives there too, fixed at the old name `cortex` so a rename never
  signs anyone out (`CLAUDE.md`). Renaming the product then costs one file. See
  `onboarding.md` § The name.

### Scripts and the cron

`sole_user_id` retires. `scripts/_user.py` holds `pick_user(session, arg)`:
`--user <id>` when given, the only user when there is exactly one, and a
refusal when there are two. Guessing between two would write into the wrong
person's ledger, which is the one mistake a script here must not make. The
nine maintenance and import scripts all go through it.

## Data

`users` gains:

| column | type | notes |
|---|---|---|
| `email` | text, unique, null | a label, refreshed on sign-in |
| `google_sub` | text, unique, null | the identity |
| `avatar_url` | text, null | Google's `picture`, refreshed on sign-in |
| `last_seen_at` | timestamptz, null | bumped with the session |

`sessions` — new, not an `Envelope`: a session is not the user's data, and its
deletion is the point.

| column | type | notes |
|---|---|---|
| `id` | ULID pk | |
| `user_id` | fk users | |
| `token_hash` | text, unique | SHA-256 of the raw token |
| `user_agent` | text, null | so a future "your devices" list can name them |
| `created_at`, `last_used_at`, `expires_at` | timestamptz | |

Settings: `GOOGLE_CLIENT_ID`, `ALLOWED_EMAILS` (`*` opens the door),
`DAILY_TURN_LIMIT`, `DAILY_SIGNUP_LIMIT`. `API_TOKEN`, which nothing ever
read, is removed. New runtime dependencies: `google-auth`, and `requests`
because its verifier's transport is synchronous — the one blocking call in the
app, run off the event loop with `asyncio.to_thread`, once per sign-in. No
password library, no JWT library.

Two things the draft did not say, decided while building:

- **The signature check and the claim checks are separate functions.** Only the
  network call runs in the thread; issuer, verified-email and the rest are
  ordinary async code. Putting them together meant the tests could only reach
  them by faking the network, which is how a stub ended up able to skip a real
  check.
- **Expiry slides.** `last_used_at` and `expires_at` both move forward on use,
  at most hourly so a read does not cost a write. Ninety days of silence ends
  a session; ninety days of use never does.

## Rules and edge cases

- **`user_id` is still never accepted from the client.** The header proves it;
  the body never carries it. `spec/done/ledger-writes.md` rule stands.
- **A row that is not yours is a 404, not a 403.** A 403 confirms the id
  exists. `live_or_404` already filters by user; this rule just names it.
- **Second user, tests.** `test_every_personal_row_belongs_to_the_one_user`
  becomes *belongs to some user*, and a new leak test signs in twice and
  asserts A's token cannot read, patch or delete B's row through any route.
  `conftest` signs in by inserting a session row and setting the header on the
  client; there is no dev bypass in production code.
- **An open door owes an exit.** The moment strangers can sign up, the owner
  is holding other people's money and health data, and *delete my account* is
  no longer optional — it is what the Play Store asks for and what the product
  already believes (per-item delete is the user-facing control; this is the
  same control at the account's scale). `DELETE /users/me` removes the user
  and every row that points at it, hard, and it is a prerequisite of setting
  `ALLOWED_EMAILS=*`, not of shipping sign-in. A privacy policy is the other
  prerequisite and belongs to hosting.
- **Deleting an account orphans shared rows rather than removing them.** A
  dish or a measure someone else has saved belongs to the library, not to its
  author, so `created_by_id` is nulled and the row stays. One consequence is
  not yet handled: `measures` is unique on phrase-per-definer, so nulling the
  author of a phrase that also exists globally would collide. It needs a
  delete-or-keep rule before `ALLOWED_EMAILS=*`.
- **The token is never logged.** Not in uvicorn access logs (the header is not
  in the line), not in an error, not in a card.
- **CORS is unchanged.** A bearer header needs no cookies, so
  `allow_credentials` stays off and the origin regex stays what it is.
- **HTTPS is hosting's job, not this spec's.** On the LAN a token travels in
  the clear; that is the status quo for the data too. It ends when the API
  gets a real address, which is the same day this ships for friends.
- **Clock.** ID-token `exp` is checked against the server clock; a host with a
  drifting clock rejects every sign-in. Hosting picks a host with NTP.
- **Prompt cache** is already partitioned by user (`cache_key=f"cortex-{user}"`).
- **Row-level security stays deferred** (`notes.md` § RLS). The app still
  connects as the table owner; the low-privilege role is a hosting-time change
  and RLS lands with it. This spec is the request-side lock only.
- **Rate limiting on `/auth/google`** is not built. Google already gates who
  can produce a credential, and a bad one costs a signature check.

## Decided against

| Option | Why not |
|---|---|
| Email + password | Hashing, a reset flow, and therefore a mail sender — three pieces of infrastructure for a door nobody prefers when Google is one tap, and every target user is on Android, where a Google account is a given. If a friend refuses Google, the answer is a magic link (a sender, no reset flow, no hash), not a password. Parked in `notes.md`. |
| JWT access token + refresh cookie | Two tokens, rotation, a refresh route and CSRF thinking, to get a revocation that one `DELETE` on a sessions row gives outright. Stateless verification helps a server that avoids its database; this one reads it on every call. |
| One shared bearer token (`api.md`) | Dies with the second user. A shared secret cannot be revoked for one person. |
| Firebase Auth, Supabase Auth, Clerk | A third party holding the user list of a privacy-first app; `spec/backend.md` already rejected Supabase for bundling exactly this. |
| Passkeys | The right door someday. Today a new app has no passkey on anyone's phone, and Google sign-in is already a passkey-shaped tap. Revisit when Credential Manager makes the two flows one call. |
| The session in an httpOnly cookie | The Android app has no cookie jar to share with a web origin. One bearer scheme serves both clients; the prototype's `localStorage` exposure is accepted because the prototype is thrown away and the keystore is the real store. |
| Downloading the Google picture | A new asset pipeline for a URL that refreshes itself on every sign-in. |
| An `invites` table | An env var is one line to change and needs no route; a table when the list outgrows an env var, or when someone other than the owner should invite. |
| Opening the door with no ceiling | The key is the owner's and the bill has no upper bound. `*` without the two limits is a stranger's chat session on the owner's card. |
| Asking each user for their own model key | The honest fix for an open door, and the wrong one for this product: pasting an API key is a harder ask than anything else in the app, and `llm.py` is deliberately the only module that knows a provider exists. Revisit if the bill, not the principle, forces it. |
| A dev-mode "no auth" switch | Every bypass ships eventually. Tests get a real session row; scripts take a user id. |

## Definition of done

`backend/tests/test_sign_in.py`.

| Check | Expected |
|---|---|
| `POST /auth/google` with a valid credential for an invited email, first time | 200, a `users` row with `google_sub`, `email`, `avatar_url`, `display_name` = given name; a `sessions` row whose `token_hash` is the SHA-256 of the returned token |
| Same credential again | 200, no second user, a second session |
| A credential whose email is not in `ALLOWED_EMAILS` | 403, no user row, no session |
| `ALLOWED_EMAILS=*`, an address nobody listed | 200, a user is created |
| An existing user whose email was removed from the list | 200, still signs in |
| `DAILY_TURN_LIMIT` reached | the agent says so in its own voice; `POST /transactions` and `GET /deck` still 200 |
| `DAILY_SIGNUP_LIMIT` reached | the next new email gets 403; existing users unaffected |
| `DELETE /users/me` | the user, their sessions and every row that names them are gone; another user's rows untouched |
| A credential for the seeded row's email, row has no `google_sub` | 200, the seeded row gains `google_sub`; no new row |
| An expired or wrong-`aud` credential | 401, nothing written |
| Any route except `/` and `/health` without a header | 401 with `WWW-Authenticate: Bearer` |
| A header whose token was signed out | 401 |
| A session past `expires_at` | 401 |
| `DELETE /auth/session` | 204; the row is gone; the token is 401 afterwards |
| User A's token on user B's transaction, meal, task, habit, place — GET, PATCH, DELETE | 404 on every route |
| `test_regression`: every personal row belongs to *some* user | passes with two users |
| `grep -rn sole_user_id backend/app backend/scripts` | nothing |
| `grep -rn "api_token\|API_TOKEN" backend` | nothing |
| Browser: no token → the door; sign in → the deck; sign out → the door; a forced 401 mid-session → the door | verified by hand |
| Browser: Drawer shows the Google picture; a blank `avatar_url` shows the initial | verified by hand |
| Browser: Profile header shows the signed-in email in mono under the name | verified by hand |
| `grep -rn "Spica" frontend/src --include=*.tsx` | only `brand.ts` defines it; components import it |
