"""
The cross-cutting sweep: invariants that must hold whatever feature moved.

These are not one spec's rules. They are the promises the whole backend makes,
and each one exists because breaking it would be quiet — a wrong number rather
than an error.
"""

import pytest
from sqlalchemy import text

from tests.helpers import make_meal, make_transaction

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_the_schema_matches_the_models(client):
    """`alembic check` in a test: a model changed without a migration is how a
    dev database and a phone quietly disagree."""
    import asyncio

    from alembic.config import Config

    from alembic import command
    from tests.conftest import TEST_URL

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_URL)
    await asyncio.to_thread(command.check, cfg)  # raises if there is drift


async def test_every_personal_row_belongs_to_a_real_user(client, db_session):
    """user_id is never read from the body, so nothing can be written into
    someone else's rows even by accident.

    This asserted *the one user* until sign-in landed (2026-09-15). There can
    be many now, so the invariant is the one that actually matters: no row is
    orphaned, and none points at a user that does not exist. The rule that a
    request cannot reach another user's rows is asserted end-to-end in
    test_sign_in.py, where two real sessions exist to try it with.
    """
    tables = [r[0] for r in (await db_session.execute(text("""
        SELECT table_name FROM information_schema.columns
        WHERE table_schema = 'public' AND column_name = 'user_id' ORDER BY 1"""))).all()]
    for t in tables:
        orphans = (await db_session.execute(text(
            f"SELECT count(*) FROM {t} WHERE user_id IS NULL "
            f"OR user_id NOT IN (SELECT id FROM users)"))).scalar()
        assert orphans == 0, f"{t} has rows belonging to nobody"


async def test_no_row_says_me(client, db_session):
    """'me' was a placeholder that leaked into every table; the seam returns a
    real id now, and nothing may drift back."""
    cols = (await db_session.execute(text("""
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND column_name IN ('user_id', 'created_by_id')"""))).all()
    for table, col in cols:
        n = (await db_session.execute(
            text(f"SELECT count(*) FROM {table} WHERE {col} = 'me'"))).scalar()
        assert n == 0, f"{table}.{col} still says 'me'"


async def test_deletes_are_soft_everywhere(client, db_session):
    """Per-item delete is the user-facing control, but a hard delete would
    break sync and take the audit trail with it."""
    tables = [r[0] for r in (await db_session.execute(text("""
        SELECT table_name FROM information_schema.columns
        WHERE table_schema = 'public' AND column_name = 'deleted_at' ORDER BY 1"""))).all()]
    for t in ("transactions", "meal_logs", "pantry_moves", "dishes", "tasks"):
        assert t in tables


async def test_nothing_is_orphaned(client, db_session):
    """Soft deletes make orphans possible in a way foreign keys cannot catch:
    a live child pointing at a dead parent."""
    checks = {
        "pantry rows on dead foods":
            "SELECT count(*) FROM pantry p JOIN foods f ON f.id = p.food_id "
            "WHERE p.deleted_at IS NULL AND f.deleted_at IS NOT NULL",
        "meal lines on dead dishes":
            "SELECT count(*) FROM meal_items mi JOIN dishes d ON d.id = mi.dish_id "
            "WHERE mi.deleted_at IS NULL AND d.deleted_at IS NOT NULL",
        "consumption for dead meals":
            "SELECT count(*) FROM pantry_moves m JOIN meal_logs ml ON ml.id = m.meal_log_id "
            "WHERE m.deleted_at IS NULL AND ml.deleted_at IS NOT NULL",
        "repayments on dead lendings":
            "SELECT count(*) FROM transactions r JOIN transactions l ON l.id = r.settles_id "
            "WHERE r.kind = 'repayment' AND r.deleted_at IS NULL AND l.deleted_at IS NOT NULL",
    }
    for what, sql in checks.items():
        assert (await db_session.execute(text(sql))).scalar() == 0, what


async def test_a_replayed_write_is_never_a_second_row(client):
    """Every POST takes a client id. An offline retry must not double a
    payment or a meal."""
    from tests.helpers import ulid
    tid, mid = ulid(), ulid()
    for _ in range(2):
        await make_transaction(client, id=tid, description="Retry me")
        await make_meal(client, id=mid, dish="Retry me too")
    rows = (await client.get("/deck?to=2026-08-28")).json()
    assert len([t for t in rows["paisa"]["transactions"] if t["id"] == tid]) == 1
    assert len([m for m in rows["diet"]["meals"] if m["id"] == mid]) == 1


async def test_unknown_is_never_stored_as_zero(client, db_session):
    """The app's oldest rule. A 0 for a macro nobody measured is a fabricated
    number, and it reads exactly like a measured one."""
    r = await make_meal(client, dish="Unknown macros")
    meal = r.json()["meal"]
    assert meal["carbs_g"] is None and meal["fat_g"] is None
    # And the columns allow it, so no future write can be forced to invent one.
    nullable = (await db_session.execute(text("""
        SELECT is_nullable FROM information_schema.columns
        WHERE table_name = 'meal_logs' AND column_name = 'carbs_g'"""))).scalar()
    assert nullable == "YES"


async def test_every_write_endpoint_refuses_an_unknown_field(client):
    """extra='forbid' everywhere, so a typo in a client is a 422 rather than a
    silently ignored value."""
    from tests.helpers import ulid
    probes = [
        ("/transactions", {"id": ulid(), "occurred_at": "2026-08-20T12:00:00+05:30",
                           "local_day": "2026-08-20", "amount_paise": 100, "direction": "debit",
                           "kind": "expense", "category": "Other", "description": "x",
                           "source": "manual", "nonsense": 1}),
        ("/memories", {"id": ulid(), "slug": "x", "kind": "reference", "text": "x",
                       "source": "user", "nonsense": 1}),
    ]
    for path, body in probes:
        assert (await client.post(path, json=body)).status_code == 422, path


def test_a_reply_is_said_once():
    """2026-09-27: a turn reached the thread as one sentence twice, glued —
    `output_text` joins every message part. The final answer, once."""
    from types import SimpleNamespace as N

    from app.agent.runner import final_text

    def msg(text, phase=None):
        return N(type="message", phase=phase, content=[N(type="output_text", text=text)])

    s = "Kaunse do tasks? Naam bata do."
    assert final_text(N(output=[msg(s + s)])) == s
    assert final_text(N(output=[msg(s), msg(s)])) == s
    assert final_text(N(output=[msg("thinking aloud", "commentary"),
                                msg(s, "final_answer")])) == s
    assert final_text(N(output=[msg("One."), msg("Two.")])) == "One.\n\nTwo."
    assert final_text(N(output=[], output_text=" plain ")) == "plain"
