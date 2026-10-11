# API

> **A reference guide, not a contract.** Written early to know what would need
> building, before any data model existed. The per-feature specs in `spec/` and
> `spec/done/` are authoritative where they disagree with this file — that is
> the point of writing them, and this file gets corrected as they land rather
> than defended.
>
> Status: draft · Surface: backend
> Serves: the web prototype now, the Android app later — the same API for both
> Superseded in part by: `spec/done/ledger-writes.md`,
> `spec/done/paisa-data-model.md`, `spec/done/diet-data-model.md`

## The decision this whole spec rests on

You asked for endpoints that "give finance data, work data, diet data for the
deck, and then many APIs for reports". The obvious reading is a dashboard API —
`GET /deck` returns `{ spentToday: 340, proteinLeft: 87, tasksOpen: 11 }`.

**That is the wrong shape, and it is worth ten minutes now rather than a rewrite
later.** Three reasons:

1. **The logic would exist twice.** The web prototype already computes all of it
   — [metrics.ts](../frontend/src/report/metrics.ts),
   [tasks.ts](../frontend/src/work/tasks.ts),
   [workouts.ts](../frontend/src/diet/workouts.ts). Move it server-side and
   Android needs its own Kotlin copy anyway, because of point 2.
2. **A glance cannot need the network.** Substrate settled local-first: the
   device holds SQLite and is the source of truth for reads. `Aaj ₹340` has to
   render on the metro with no signal.
3. **Computed numbers go stale the instant you log something.** A `/deck`
   response is wrong the moment a chai is added, so the client would have to
   recompute regardless — at which point the server's version was wasted work.

**So: the API serves rows and intelligence. Never views.**

```
rows  ──▶  device / prototype computes  ──▶  rings, bars, strips, notes
                     ▲
intelligence ────────┘   (LLM categorisation, chat, enrichment — server only)
```

The one concession to convenience is **`GET /deck`**, which is a single call so
app-open is one round trip instead of four — but it returns *rows*, scoped to
what the three cards need. One request, no duplicated maths.

## What runs where

| Job | Where | Why |
|---|---|---|
| Rings, bars, week strip, card notes | **Device** | Must be instant and offline |
| Report figures, comparisons, coverage | **Device** | Same code as the deck; rows are already local |
| Amount-band learning, signal scoring (Tiers 0–1) | **Device** | Deterministic, and the raw data never has to leave |
| Repayment matching | **Device** | Arithmetic on local rows |
| Monthly reconciliation gap | **Device** | Arithmetic |
| LLM categorisation (Tier 2) | **Server** | Needs a model |
| Agent replies | **Server** | Needs a model |
| Shared-URL enrichment | **Server** | Needs to fetch the page |
| Skill-file generation | **Server** | Cheap to do beside the model that reads it |
| Sync between devices | **Server** | Definitionally |

Notification raw text and the contacts list **never** reach the server —
`spec/paisa-categorise.md` §5.8 is binding on this API.

**Work data does not come through an adapter here.** It arrives from the Claude
routine in `spec/work-sync.md`, through Spica's MCP server — the only
integration Spica has for tasks. Linear and meeting transcripts connect to
Claude, not to this API.

## Auth

**Superseded 2026-09-15 by `spec/in-progress/sign-in.md`.** This section said
one user and one long-lived shared token; a second user is exactly what
happened, and a shared secret cannot be revoked for one person.

```
Authorization: Bearer <token>
```

The header is unchanged. What is behind it is not: the token is now per session,
issued by `POST /auth/google` after a Google ID token is verified, stored as its
SHA-256, and deleted by `DELETE /auth/session`. Every route except `GET /` and
`GET /health` answers 401 without one.

## Conventions

**Time.** Every timestamp is UTC ISO-8601. Every ledger row also carries
`localDay` as `YYYY-MM-DD`, computed at write time. India is UTC+5:30, so a
23:30 entry lands on the wrong day if the local day is derived at read time —
and every "aaj / is hafte" in the app is a `localDay` comparison.

**Envelope.** Responses are the bare object or array. No `{ data: … }` wrapper.

**Errors.**

```json
{ "error": "validation_failed", "message": "amount must be > 0", "field": "amount" }
```

Status codes carry the category; the body carries the detail. `4xx` is the
client's fault and will not succeed on retry. `5xx` may.

**Idempotency is mandatory on writes, not optional.** Notification capture will
deliver the same payment twice — two banks' apps, a retry, a re-read. `POST` of
an existing id returns **200 with the existing row**, not 409 and not a
duplicate.

*Corrected:* ids are **ULIDs supplied by the client**, with a separate
`dedupe_key` for capture — not content-derived. A hash-as-id binds identity to
the dedupe rule, so changing the rule breaks every reference. See
`spec/done/ledger-writes.md`.

**Pagination** is cursor-based, never offset: `?after=<cursor>&limit=100`. Offsets
shift under an append-only log.

**Soft delete.** `deletedAt` is set; rows are never removed. Sync cannot converge
on a row that vanished.

---

## Sync — the spine

Everything else is a convenience over these three.

### `GET /events?since=<seq>&limit=200`

The append-only log from the Substrate note. A client syncs by reading from its
own cursor.

```json
{
  "events": [
    { "seq": 4812, "op": "upsert", "entity": "tx",  "id": "tx_9f2a", "at": "2026-08-27T14:22:09Z" },
    { "seq": 4813, "op": "delete", "entity": "tx",  "id": "tx_71bd", "at": "2026-08-27T14:25:00Z" }
  ],
  "next": "4813",
  "head": 4813
}
```

`seq` is monotonic and server-assigned. The event carries the id, not the body —
the client fetches what it does not have. That keeps the log small enough to
never need pruning.

### `POST /events`

Batch push of local writes, for a device that was offline.

```json
{ "events": [ { "op": "upsert", "entity": "workout", "body": { … } } ] }
```

Conflict rule: **last write wins per field**, with the local clock as tiebreak.
Good enough for one user on two devices, and the alternative — CRDTs — is a
month of work for a problem that does not exist yet.

### `GET /entity/{type}/{id}`

Fetch one row by id, for filling gaps the event log announced.
`type ∈ tx | meal | todo | workout | commitment | library`.

---

## Reads

### `GET /deck`

Everything the three cards need, one call. Rows, not numbers.

```json
{
  "asOf": "2026-08-27T09:14:00Z",
  "localDay": "2026-08-27",
  "settings": { "salary": 95000, "fixed": 53000, "bankBalance": 41000,
                "savingsTarget": 20000, "proteinTarget": 135, "kcalTarget": 2050,
                "carbTarget": 220, "sleepTargetMin": 450, "stepTarget": 8000 },
  "tx":       [ /* current month */ ],
  "meals":    [ /* today */ ],
  "todos":    [ /* all open, plus closed today */ ],
  "workouts": [ /* current calendar week */ ],
  "projects": [ { "id": "novacart", "name": "novacart-chan", "color": "#C98A16" } ],
  "commitments": [ /* inside their reminder window only */ ]
}
```

Scoping notes, each of which is a real decision:

- **`tx` is the whole month, not today.** The Paisa card's outer ring is the
  month; sending only today would make the card impossible to draw.
- **`todos` includes tasks closed *today*.** The Kaam card holds a ticked task in
  place for the rest of the day (`doneDay`), so those rows are still needed.
- **`workouts` is the calendar week, Monday-first**, matching the strip.
- **`commitments` is filtered to the reminder window.** Sending all of them would
  mean shipping years of renewals to draw one greeting line.

### `GET /report/{mode}?range={7din|14din|mahina}`

`mode ∈ paisa | diet | kaam`. Returns rows for the requested span **and the
previous span**, because every report in this app compares against the window
immediately before it.

```json
{
  "span":     { "from": "2026-08-21", "to": "2026-08-27", "days": 7 },
  "prevSpan": { "from": "2026-08-14", "to": "2026-08-20", "days": 7 },
  "rows":     { "tx": [ … ], "prevTx": [ … ] },
  "coverage": { "loggedDays": 6, "spanDays": 7 }
}
```

`coverage` is server-computed because it is a fact about the data, not a view of
it — and the app's honesty rule requires showing it.

For `diet` the payload carries `meals`, `sleep`, `steps`, `workouts`; for `kaam`,
`todos` and `projects`. Same envelope.

### `GET /library?type=&path=&tag=&q=&after=`

Your data. `type ∈ recipe | article | place | workout | pantry | note`.

```json
{ "items": [ { "id": "r_88", "type": "recipe", "title": "Soya keema",
              "path": "Recipes/Dinner", "tags": ["soya","20-min"],
              "confidence": 0.96, "source": "share",
              "medium": "video", "sourceUrl": "…",
              "keptAt": "…", "keptFrom": "share" } ],
  "next": null }
```

`medium` is separate from `type` — the fix for the bug noted in Substrate, where
`video` is currently a type and so a recipe that arrived as a video gets filed as
a video.

### `GET /library/inbox`

Items below the confidence threshold, awaiting confirmation. Sorted freshest
first.

### `GET /commitments?window=30d&includeOverdue=true`

Upcoming and overdue, sorted by date, overdue first.

---

## Writes

### `POST /transactions`  *(was `/tx`)*

Single or batch. From notification capture, or the composer.

**The shape below is the early sketch and is out of date.** The built contract
is in `spec/done/ledger-writes.md`; the differences are `amount_paise`
instead of rupees, `counterparty_name` instead of `rawPayee`, and motion and
location living in `predictions.signals` rather than on the row — a signal is
what the model saw, not a fact about the payment.

```json
{ "txns": [ {
  "txnId": "hash…", "occurredAt": "2026-08-27T14:22:09Z", "localDay": "2026-08-27",
  "amount": 98, "direction": "DEBIT", "rawPayee": "MOHAN LAL",
  "category": "Health/Diet", "description": "chai aur samosa",
  "confidence": 0.92, "predictedBy": "DICTIONARY", "confirmed": false,
  "motionState": "WALKING", "locationHash": "tdr1v", "sessionId": "s_442"
} ] }
```

`rawText` is accepted and **discarded server-side** — it exists so the device can
parse, not so the server can store it. Sending it is allowed; keeping it is not.

### `POST /tx/{id}/correct` *(superseded — edits are `PATCH /transactions/{id}`, see `ledger-writes.md`)*

A correction is a **new row that supersedes**, never an edit. Preserves the audit
trail, and preserves the `(signals, predicted, actual)` triple that
`spec/paisa-categorise.md` §5.7 needs as its future training set.

```json
{ "category": "Khana", "description": "phal — apple", "reason": "user_correction" }
```

Returns both the superseding row and the corrected one.

### `POST /meals` · `POST /habit-logs` · `POST /tasks`

Same shape family. `PATCH /tasks/{id}` for the done toggle — a task is state,
not an event, so it is the one place an in-place update is right. `done_at` is
set server-side; the card's *stays visible today* behaviour derives from it.

*Corrected:* `POST /workouts` became `POST /habit-logs` — a workout is one
habit among several (`spec/done/diet-data-model.md`).

### `POST /library`

Bookmark from chat, or a share from another app.

```json
{ "sourceUrl": "https://instagram.com/reel/…", "hint": "paneer recipe",
  "keptFrom": "share", "suggestedBy": null }
```

Returns immediately with a stored item, `type: null`, `confidence: 0`, queued for
enrichment. **The share must never fail** — see `spec/capture.md`. Duplicate
`sourceUrl` (normalised) returns the existing item.

### `POST /library/{id}/confirm` · `DELETE /library/{id}`

Confirm clears the doubt without changing the item. Delete is the per-item
control that stands in for the export feature we are not building.

### `POST /commitments` · `PATCH /commitments/{id}`

Create from a capture follow-up or a spoken line. `PATCH` closes, gifts, or rolls
a repeating one forward. Udhaar rows live here — see the merge question at the
top of `spec/udhaar.md`.

---

## Intelligence

The only endpoints that genuinely cannot run on the device.

### `POST /categorise`

> **Not built as a route — decided 2026-09-15.** The batch is one function with
> two doors, the `categorise_now` tool and `scripts/categorise.py`; the phone
> talks to the agent. `payeeHash` is not sent either — `notes.md` § Payee names.
> `spec/in-progress/categorise.md` is current; the shape below is kept as the
> record of what was drawn.

Tier 2 from `spec/paisa-categorise.md`. **One batched call per day**, carrying
the day's uncertain transactions with their pre-computed signals.

```json
{ "skillFileVersion": 41,
  "items": [ { "id": 1, "amount": 98, "payeeHash": "a91f…", "seenCount": 5,
               "hourOfDay": 19, "dayOfWeek": 1, "isWorkingDay": true,
               "motionBefore": "WALKING", "minsSinceLastTxn": 12,
               "amountBandMatch": "Health/Diet" } ] }
```

```json
{ "predictions": [ { "id": 1, "category": "Health/Diet",
                     "description": "chai aur samosa", "confidence": 0.88,
                     "why": "known payee, amount in band" } ] }
```

Server-side validation before returning, so a bad model response never reaches
the ledger:

- Category outside the known set → drop the prediction
- `confidence > 0.85` on a payee with `seenCount == 0` → cap at `0.84`
- Unparseable → return the item with `confidence: 0` so it falls to the user

`payeeHash` rather than the name is the default. The mapping stays on device.

### `GET /skill-file` · `POST /skill-file/regenerate`

> **Deferred 2026-09-15.** The skill file is generated from rows on every run
> (`scripts/categorise.py --skill` prints it); a route returns when there is a
> screen to show it on.

The markdown from §5.6, versioned. Regenerated nightly, or on demand after a run
of corrections. `GET` exists so the device can show the user what the agent
believes about them — which is also the fastest way to spot that it has learned
something wrong.

### `POST /enrich`

Resolve a shared URL to `{ type, title, tags, medium }`. Allowed to fail: returns
`204` and the item stays in the Inbox. Never retried more than three times, and
never overwrites a field the user has set.

### `POST /chat`

The agent. Returns typed cards, not just prose — `spec/capture.md` depends on
this, because a suggestion can only be bookmarked if it is an object.

```json
{ "message": "aaj kitna bacha hai", "localDay": "2026-08-27" }
```

```json
{ "reply": [
  { "kind": "agent", "title": "₹191 bacha hai", "body": "…" },
  { "kind": "table", "source": "paisa", "ids": ["tx_1","tx_2"] },
  { "kind": "suggestion", "items": [ { "type": "recipe", "ref": "r_88", "saved": true } ] }
] }
```

Cards reference rows **by id**, never by value. The app's live-id rule: deleting a
row has to update every card that showed it.

---

## Build order

Not one job. In this order, each step useful on its own:

| # | Ship | Unblocks |
|---|---|---|
| 1 | `GET /deck`, `GET /report/*` returning seeded rows | Prototype stops importing `seed.ts` |
| 2 | `POST` for tx / meals / workouts / todos | Logging actually persists |
| 3 | `/events` sync | Two devices, and backup |
| 4 | `/library`, `/library/inbox`, `/enrich` | Your data, and the share door |
| 5 | `/chat` | The premise |
| 6 | `/categorise`, `/skill-file` | Auto-categorisation |
| 7 | `/commitments` | The future tense |

Step 1 is worth doing early even though it changes nothing visible: it forces the
row shapes to be real, and every later step assumes them.

## Deliberately not building

| Not building | Why |
|---|---|
| `GET /export` or any bulk download | Settled: the largest leak in a personal-data app. Per-item delete is the control |
| Server-computed dashboard numbers | Duplicates logic, needs network for a glance, stale on the next write |
| A bank-balance or Account Aggregator endpoint | `spec/paisa-categorise.md` §4.4 — balance is never asked, only the monthly gap |
| Multi-user, sharing, permissions | One user. Pretending otherwise costs auth complexity for nothing |
| Webhooks or a public API | No third party is integrating. Adds a surface to secure |
| Storing notification `rawText` | Accepted for parsing, discarded on arrival |
| Sending contacts anywhere | Only a local yes/no check ever leaves the contacts API |
| Offset pagination | Shifts under an append-only log |
| `409` on duplicate writes | Capture *will* deliver duplicates; that is normal, not an error |

## Open questions

- **Where does the LLM run?** On-device Gemini Nano would remove `/categorise`
  and `/chat` from this API entirely — a much smaller backend and a much stronger
  privacy story, at the cost of quality. Worth benchmarking before committing to
  the server path, because it changes what this spec even needs to contain.
- **Does the prototype get its own SQLite, or stay in-memory?** If it stays
  in-memory, `/events` cannot be exercised until the Android app exists, and sync
  is the least testable part of the design.
- Should `/deck` accept an `If-None-Match` so a warm app-open is a `304`? Cheap,
  and app-open happens more than anything else.
- Rate limits: pointless for one user, but `/enrich` fetches third-party URLs and
  should not be usable as an open proxy. A per-token cap is probably enough.
