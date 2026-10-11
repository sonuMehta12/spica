# Backend tests

One file per shipped spec, named `test_<spec>.py`, asserting that spec's
Definition of done against the real API. `test_regression.py` is the
cross-cutting sweep — invariants that must hold whatever feature moved: the
audit trail, soft deletes, the single-user seam, no orphans.

**Frontend is a throwaway prototype and is not tested** (see CLAUDE.md); the
backend is what the Android app will keep, so it is.

## Running

    cd backend && uv run pytest              # all of it
    uv run pytest tests/test_dishes.py       # one spec

Each run builds a **fresh, isolated database** (`cortex_test`), migrates it to
head, and seeds one user. Tests share nothing and never touch the dev data on
`cortex`. A test that needs rows creates them through the API, the same path the
app uses, so a test passing means the endpoint works, not just the table.
