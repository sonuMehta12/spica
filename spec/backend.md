# Backend — stack and roadmap

> Status: decision doc, ready to act on
> Surface: backend
> Reads from: `spec/api.md` (endpoints), `spec/substrate.md` (data model)

## The DB question, answered from the specs rather than from taste

Postgres, MongoDB and Firebase are all *capable* of holding this data. The
decision is not capability, it is which one makes the queries this app actually
runs cheap. Four things in the specs settle it:

### 1. Embeddings — this is the decisive one

`spec/api.md` says "ask" is the only retrieval path that has to be excellent,
and `spec/substrate.md` says it runs over **meaning + tags + edges together**:

> *"Wo protein wala recipe kya tha jo sasta bataya tha?"*

With **pgvector**, that is one query — vector similarity `WHERE tags @> …` and a
join to the ledger, in a single statement. Without it, embeddings live in a
second system (Pinecone, Qdrant, Atlas Search), which means two databases to
keep in sync and no cheap way to filter a vector search by tag.

**One user does not need two databases.** This alone is enough to decide it.

### 2. The data is relational, and deliberately so

`spec/substrate.md` §8 is a list of joins: recipe→pantry, meal→recipe,
transaction→counterparty, transaction→commitment. The document literally calls
it a graph.

And the same spec fixes a **closed type list** — seven types, "the set is fixed",
"untyped records cannot be computed over". Schemaless is a benefit when the shape
is unknown. Here the shape is deliberately known, so a schema is a free
constraint rather than a cost.

### 3. Every report is an aggregation

The reports are `SUM` by category by day, medians per payee, counts within a
window. That is one line of SQL each. In Firestore it is app-side computation
over fetched documents, and you pay per document read — a 7-day report that
touches 500 rows costs 500 reads, every time it is opened.

### 4. The event log needs a monotonic sequence

`{seq, id, op}` with `seq` server-assigned and gap-free-enough to page through.
Postgres gives that with `BIGSERIAL`. Mongo needs a counter document and the
race conditions that come with it; Firestore has no server-side sequence at all.

### Verdict

| | |
| --- | --- |
| **Postgres + pgvector** | Chosen |
| MongoDB | Would work. But no in-DB vectors outside Atlas, more verbose aggregation, and schemaless buys nothing when the schema is fixed on purpose |
| Firebase / Firestore | No aggregation, no vectors, per-read pricing on exactly the access pattern this app has, and vendor lock-in against a project whose whole point is owning your own data |
| SQLite on the server | Genuinely tempting for one user — the DB is a file. Loses pgvector, and three writers (phone, plugin, web) on one file is a lock problem waiting to happen |

**Hosting:** Neon. Serverless Postgres, real free tier, scales to zero, pgvector
available, and the entire setup is one connection string. Supabase is the other
sane option but bundles auth and storage this app does not need — `spec/api.md`
settled auth as one bearer token for one user.

---

## The stack

| Layer | Choice | Why this one |
| --- | --- | --- |
| Language | **Python 3.12** | Your call, and the right one for the LLM side |
| Framework | **FastAPI** | Async, typed, and generates the OpenAPI doc the Android client will need |
| Validation | **Pydantic v2** | The "one envelope" from `spec/substrate.md` is literally a base model every type inherits |
| ORM | **SQLAlchemy 2.0**, typed style | Mature, and its 2.0 syntax is close enough to raw SQL that reports stay readable |
| Migrations | **Alembic** | Schema will change. Without migrations the seed becomes unreproducible by week three |
| Driver | **asyncpg** | |
| Vectors | **pgvector** + `pgvector-python` | |
| Deps | **uv** | Fast, lockfile-based, one tool instead of pip + venv + poetry |
| LLM | **OpenAI**, behind one module | See below |

### Keep the model behind one module

Not architecture astronomy — `spec/api.md` has an open question about running the
model **on-device** (Gemini Nano), which would delete `/categorise` and `/chat`
from the API entirely. That question is still open, so the code should not be
threaded with `openai.` calls in twenty places.

One `llm.py` with three functions — `categorise()`, `chat()`, `embed()` — and
nothing else in the codebase imports the SDK.

Use **structured outputs** (JSON schema mode) for `/categorise`. The validation
rules in `spec/paisa-categorise.md` §5.6 — reject unknown categories, cap
confidence on new payees — still apply, but "JSON parse failed" mostly stops
being a case you handle.

---

## Schema decisions worth making now

### One table per type, not one `records` table

The shared envelope tempts you toward a single table with a `type` column and a
JSONB body. Resist it: you lose typed columns, real indexes, and constraints, and
every report becomes JSONB extraction.

**Repeat the envelope columns in each table.** The repetition is honest and each
table indexes what it actually queries. One `events` table points at rows with
`(entity, entity_id)`.

### Money is an integer, never a float

`spec/paisa-categorise.md` and `spec/udhaar.md` both declare `amount: Double`.
**That is a bug waiting to happen** — floats do not represent decimal currency
exactly, and this app sums amounts constantly, so the error compounds.

Store **paise as `BIGINT`**. `₹98.00` is `9800`. Format at the edge. Fix it in
those specs while nothing is built.

### `localDay` is a `DATE` column

Not text. Postgres compares and indexes dates properly, and `spec/substrate.md`
makes `localDay` the key for every "aaj / is hafte" query in the app.

### Indexes that earn their place

```sql
transactions (local_day DESC)          -- every report window
transactions (category, local_day)     -- category breakdowns
transactions (counterparty_id)         -- "is cafe pe kitna gaya"
events (seq)                           -- the sync cursor
library USING GIN (tags)               -- tag filtering
library USING hnsw (embedding …)       -- ask
```

Nothing else until something is slow. The ledger is thousands of rows a year,
not millions.

---

## Roadmap

Your order — DB, then endpoints, then LLM — is right. One change to how it starts.

**Do not build all the endpoints before one works end to end.** Twenty endpoints
against a schema that turns out wrong is twenty rewrites. Get one vertical slice
working, then widen.

### Step 1 — the slice that proves the schema

Schema, seeded with the **real August data already in
`frontend/src/data/seed.ts`**, and one endpoint: `GET /deck`. Then the prototype
stops importing `seed.ts` and fetches instead.

The test is beautiful because it needs no new judgement: **the app should look
exactly the same.** Same rings, same numbers, same card notes. If anything moved,
the schema is wrong — and you find out on day one rather than after twenty
endpoints.

```
alembic migration  →  seed script from seed.ts  →  GET /deck  →  frontend fetch
                                                                      │
                                          app renders identically ◀────┘
```

### Step 2 — writes

`POST /tx`, `/meals`, `/workouts`, `/todos`, and `PATCH /todos/{id}`. Now logging
persists and survives a reload. Content-derived ids and the idempotency rule from
`spec/api.md` land here, because notification capture *will* deliver duplicates.

### Step 3 — reports

`GET /report/{mode}`. Mostly a matter of span maths; the row shapes are already
proven by step 1.

### Step 4 — the event log

`GET /events`, `POST /events`. Nothing consumes it until the Android app exists,
but it is much cheaper to write now than to retrofit — every write has to emit an
event, and adding that later means touching every handler.

### Step 5 — LLM orchestration

`POST /chat` first, because it is the premise. Then `/categorise`, which is where
`spec/paisa-categorise.md`'s tiering and skill file live.

This is also the first point where the specs get properly tested: you have
**27 days of labelled August data**, so `spec/paisa-categorise.md` §7 T2 can run
for real — train the skill file on the first 14 days, predict the last 13,
measure. If that lands under 70%, the skill-file approach is wrong and you learn
it before building the UI around it.

### Step 6 — capture and commitments

`/library`, `/enrich`, `/commitments`. Lower priority because the share door is
Android-only anyway.

---

## The first commit

```
backend/
├── pyproject.toml          uv, deps pinned
├── alembic/                migrations from empty
├── app/
│   ├── main.py             FastAPI, one bearer token
│   ├── db.py               engine, session
│   ├── models/             SQLAlchemy — envelope base + per-type
│   ├── schemas/            Pydantic — request/response
│   ├── routes/deck.py      GET /deck
│   └── llm.py              empty for now, one seam
└── scripts/seed.py         ports frontend/src/data/seed.ts
```

Nothing in `llm.py` yet. It exists so that when step 5 arrives there is one
obvious place for it and no temptation to scatter SDK calls.

## Open

- **Neon or self-hosted Postgres?** Neon is less work and free at this size. Self
  hosting is more control and more yak. Leaning Neon until there is a reason.
- **Does the prototype keep computing, or start trusting the server?**
  `spec/api.md` says the API serves rows and the client computes. Step 1 holds
  that line — the frontend keeps `metrics.ts` untouched and only swaps its data
  source. Worth confirming that is still what you want before writing it.
- Money as paise means changing `amount: Double` in two specs. Do that now or
  note it as known debt?
