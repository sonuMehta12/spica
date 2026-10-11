"""
Test harness: a fresh, migrated, single-user database per run, and an ASGI
client bound to it.

The dev data on `cortex` is never touched — tests build `cortex_test` from the
migrations, so a schema drift breaks a test rather than hiding. Everything a
test needs it creates through the API, which is the point: a green test means
the endpoint behaves, not merely that the row shape compiles.
"""

import asyncio
import os

import asyncpg
import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command

DEV_URL = "postgresql+asyncpg://cortex:cortex@localhost:5434/cortex"
TEST_DB = "cortex_test"
TEST_URL = f"postgresql+asyncpg://cortex:cortex@localhost:5434/{TEST_DB}"

# Before any test module is collected. `settings()` is cached, and `app.db`
# reads it on import — so a test file importing app code at module level used
# to freeze the *dev* URL into it, and `alembic/env.py` then migrated the dev
# database while the test one stayed empty (found 2026-09-27). Set here, the
# first `settings()` anyone builds already points at the test database. Every
# setting a test run depends on belongs here for the same reason — the turn
# ceiling went missing the same way, and the agent went quiet after 100 turns.
os.environ["DATABASE_URL"] = TEST_URL
# The scripted model (tests/helpers.py FakeLLM) speaks the Responses API, so
# the agent's tests run on that path whatever the default provider is; the
# Anthropic translation has its own tests (test_llm_provider.py).
os.environ["LLM_PROVIDER"] = "openai"
# One database and one user for the whole run, so turns accumulate across
# every test that talks to the agent. The ceiling is a production setting;
# the test that asserts it sets it to zero itself.
os.environ["DAILY_TURN_LIMIT"] = "1000000"
# The same for sign-ups: tests that need an account of their own create one,
# and every one counts as a sign-up today. Past twenty, the sign-in tests met
# "invite-only" for a reason that had nothing to do with them (2026-10-11).
os.environ["DAILY_SIGNUP_LIMIT"] = "1000000"


async def _recreate_database() -> None:
    """Drop and remake cortex_test, so every run starts from nothing."""
    admin = await asyncpg.connect("postgresql://cortex:cortex@localhost:5434/cortex")
    await admin.execute(
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{TEST_DB}' AND pid <> pg_backend_pid()"
    )
    await admin.execute(f'DROP DATABASE IF EXISTS {TEST_DB}')
    await admin.execute(f'CREATE DATABASE {TEST_DB}')
    await admin.close()
    # Bare on purpose: no extensions made here. The root migration creates
    # them, as it must on a hosted database, so every run proves a database
    # with nothing in it migrates (spec/in-progress/deploy.md).


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _database():
    """Build the test database once, migrate it, seed the one user."""
    await _recreate_database()

    from app.config import settings
    assert settings().database_url == TEST_URL, (
        "settings() was built before the test URL was set — migrations would run "
        "against the dev database")
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_URL)
    await asyncio.to_thread(command.upgrade, cfg, "head")

    # One user with known targets — the seam's only row, and the denominator
    # behind every "kitna bacha" a test asserts on.
    #
    # Two mistakes were made here, both on 2026-09-12, and the shape of the fix
    # is the lesson: the users migration seeds a row of its own, so inserting a
    # second made `SELECT id FROM users LIMIT 1` a coin flip on heap order; and
    # inserting only when none existed left the migration's target-less row in
    # place, so every diet figure quietly read null. **Ensure one row, then set
    # the targets on it** — neither create-always nor create-never.
    from app.models.base import new_id
    engine = create_async_engine(TEST_URL)
    async with async_sessionmaker(engine)() as s:
        from sqlalchemy import text
        if (await s.execute(text("SELECT count(*) FROM users"))).scalar() == 0:
            await s.execute(text(
                "INSERT INTO users (id, display_name) VALUES (:id, 'Test')"),
                {"id": new_id()})
        await s.execute(text(
            "UPDATE users SET savings_target_paise = 1200000, protein_g_target = 135, "
            "kcal_target = 2050, sleep_target_min = 450, step_target = 8000"))
        await s.commit()
    # One session row for that user, created with the database. Tests
    # authenticate the way the app does; there is no test-only bypass in
    # production code, because every bypass ships eventually.
    await _sign_in(engine)
    await engine.dispose()
    yield


TEST_TOKEN = "test-session-token"


async def _sign_in(engine) -> str:
    """A real session row for the seeded user, and the raw token for it.

    Tests authenticate the way the app does — a token in a header against a row
    in `sessions`. There is no test-only bypass in production code, because
    every bypass ships eventually.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.auth import hash_token
    from app.models.users import Session, User

    digest = hash_token(TEST_TOKEN)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        if await s.scalar(select(Session).where(Session.token_hash == digest)) is None:
            uid = await s.scalar(select(User.id).order_by(User.created_at).limit(1))
            s.add(Session(user_id=uid, token_hash=digest,
                          expires_at=datetime.now(UTC) + timedelta(days=90)))
            await s.commit()
    return TEST_TOKEN


@pytest_asyncio.fixture(loop_scope="session")
async def client(_database):
    """An ASGI client whose app talks to the test database, signed in.

    app.db is imported fresh with DATABASE_URL already pointing at cortex_test,
    and every request carries a bearer token for the seeded user — the seam
    reads the header, so a client without one gets 401 like anyone else.
    """
    import app.db as db

    engine = create_async_engine(TEST_URL)
    db.engine = engine
    db.SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    token = await _sign_in(engine)  # re-ensured: a test may have signed it out

    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t",
                           headers={"Authorization": f"Bearer {token}"}) as c:
        yield c
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def anon(_database, client):
    """The same app with no credentials — for asserting the lock is on."""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(_database):
    """Direct DB access for the few assertions that read state the API hides."""
    engine = create_async_engine(TEST_URL)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


# ─── the agent's fixtures ────────────────────────────────────────────────────

@pytest.fixture
def fake(monkeypatch):
    """Install a scripted model in place of the real one (tests/helpers.py)."""
    from tests.helpers import FakeLLM

    def install(*script):
        llm = FakeLLM(script)
        # Every model call goes through `app.llm.respond`, which reads
        # `client()` and `model()` from its own module at call time — so that
        # is where the fake is installed, whoever the caller is.
        monkeypatch.setattr("app.llm.client", lambda: llm)
        monkeypatch.setattr("app.llm.model", lambda: "fake-model")
        monkeypatch.setattr("app.agent.runner.model", lambda: "fake-model")
        return llm
    return install


@pytest_asyncio.fixture(loop_scope="session")
async def library(client, db_session):
    """A dish, three foods and a measure. The test database is built from
    migrations, and the real library arrives from import scripts — so the
    ladder's fixtures have to be made here."""
    from sqlalchemy import text
    rows = [
        ("INSERT INTO dishes (id, name, aliases, serving_label, protein_g, kcal, "
         "visibility, created_at, updated_at) VALUES (:i, 'Whey shake', "
         "ARRAY['protein shake'], '1 glass', 24, 120, 'public', now(), now())",
         {"i": "t-dish-whey"}),
        ("INSERT INTO foods (id, name, aliases, unit, created_at, updated_at) "
         "VALUES (:i, 'Atta (whole wheat)', ARRAY['roti'], 'g', now(), now())",
         {"i": "t-food-atta"}),
        ("INSERT INTO foods (id, name, aliases, unit, created_at, updated_at) "
         "VALUES (:i, 'Dal (family stock)', ARRAY['dal'], 'g', now(), now())",
         {"i": "t-food-dal"}),
        ("INSERT INTO foods (id, name, aliases, unit, grams_per_unit, created_at, "
         "updated_at) VALUES (:i, 'Egg', ARRAY['anda','ande'], 'piece', 50, now(), now())",
         {"i": "t-food-egg"}),
        ("INSERT INTO measures (id, phrase, grams, created_at, updated_at) "
         "VALUES (:i, '1 katori', 150, now(), now())", {"i": "t-measure-katori"}),
    ]
    for sql, params in rows:
        await db_session.execute(text(sql + " ON CONFLICT (id) DO NOTHING"), params)
    await db_session.commit()
