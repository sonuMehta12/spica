"""
spec/in-progress/deploy.md — what the code changes so Spica runs on Vercel and
Neon: the pasted database string works, Vercel's instances hold no
connection, a bare database migrates, only a production build migrates, and
the tick's log on GitHub carries no ledger.
"""

import asyncio
import importlib.util
import logging
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from app.config import Settings, asyncpg_url
from app.db import make_engine
from tests.conftest import TEST_URL

# Only the async tests share the session's loop, where its fixtures live.
session_loop = pytest.mark.asyncio(loop_scope="session")

BACKEND = Path(__file__).resolve().parent.parent
NEON = ("postgresql://alex:AbC123dEf@ep-cool-darkness-123456.ap-southeast-1.aws.neon.tech"
        "/neondb?sslmode=require&channel_binding=require")


# ─── the database URL ────────────────────────────────────────────────────────

def test_neons_string_is_taken_as_pasted():
    assert Settings(_env_file=None, database_url=NEON).database_url == (
        "postgresql+asyncpg://alex:AbC123dEf@ep-cool-darkness-123456.ap-southeast-1.aws.neon.tech"
        "/neondb?ssl=require")


@session_loop
async def test_what_asyncpg_is_handed_has_only_keys_it_knows():
    """The reason for the rewrite: SQLAlchemy passes the query keys straight to
    `asyncpg.connect`, which has an `ssl` and neither `sslmode` nor
    `channel_binding`."""
    engine = create_async_engine(Settings(_env_file=None, database_url=NEON).database_url)
    _, kwargs = engine.dialect.create_connect_args(engine.url)
    await engine.dispose()
    assert kwargs["ssl"] == "require"
    assert "sslmode" not in kwargs and "channel_binding" not in kwargs


def test_postgres_and_postgresql_schemes_become_asyncpg():
    assert asyncpg_url("postgres://u:p@db.example.com:5432/spica") == (
        "postgresql+asyncpg://u:p@db.example.com:5432/spica")
    assert asyncpg_url("postgresql://u:p@db.example.com/spica?sslmode=verify-full") == (
        "postgresql+asyncpg://u:p@db.example.com/spica?ssl=verify-full")


def test_an_asyncpg_url_and_other_keys_are_left_alone():
    right = "postgresql+asyncpg://u:p%40ss@h/db?ssl=require&application_name=spica"
    assert asyncpg_url(right) == right
    assert asyncpg_url("postgresql://u:p@h/db?sslmode=require&options=-c%20statement_timeout%3D5000"
                       ) == "postgresql+asyncpg://u:p@h/db?ssl=require&options=-c%20statement_timeout%3D5000"


def test_the_local_default_still_works(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings(_env_file=None).database_url == (
        "postgresql+asyncpg://cortex:cortex@localhost:5434/cortex")


# ─── the pool ────────────────────────────────────────────────────────────────

@session_loop
async def test_db_null_pool_holds_no_connection_and_the_default_keeps_the_pool():
    """Built from fresh settings, never touching the engine the app shares."""
    held = make_engine(Settings(_env_file=None, database_url=TEST_URL, db_null_pool=True))
    pooled = make_engine(Settings(_env_file=None, database_url=TEST_URL))
    try:
        assert isinstance(held.pool, NullPool)
        assert isinstance(pooled.pool, AsyncAdaptedQueuePool)
        async with held.connect() as conn:      # it still connects, per use
            assert await conn.scalar(text("SELECT 1")) == 1
        assert held.pool.status() == "NullPool"
    finally:
        await held.dispose()
        await pooled.dispose()


# ─── the migrations ──────────────────────────────────────────────────────────

class _Op:
    """Stands in for `alembic.op` and records what a migration asks of it."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def __getattr__(self, name):
        return lambda *a, **_: self.calls.append((name, a))


def test_the_root_migration_creates_its_extensions_first():
    """A hosted database starts with none, and the first gin_trgm_ops index
    in this revision needs pg_trgm."""
    [path] = (BACKEND / "alembic" / "versions").glob("438d6393f4c2_*.py")
    spec = importlib.util.spec_from_file_location("root_migration", path)
    root = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(root)
    assert root.down_revision is None

    root.op = op = _Op()
    root.upgrade()
    assert op.calls[:3] == [
        ("execute", ("CREATE EXTENSION IF NOT EXISTS vector",)),
        ("execute", ("CREATE EXTENSION IF NOT EXISTS pg_trgm",)),
        ("execute", ("CREATE EXTENSION IF NOT EXISTS unaccent",)),
    ]


@session_loop
async def test_a_bare_database_migrates_with_its_extensions(db_session):
    """conftest creates cortex_test with nothing in it, so the extensions here
    are the migrations' own."""
    have = set((await db_session.scalars(text("SELECT extname FROM pg_extension"))).all())
    assert {"vector", "pg_trgm", "unaccent"} <= have


# ─── the build step ──────────────────────────────────────────────────────────

def _build(tmp_path, vercel_env: str | None, url: str = TEST_URL) -> subprocess.CompletedProcess:
    """Run scripts/vercel_build.py from somewhere else, as Vercel might."""
    env = {k: v for k, v in os.environ.items() if k != "VERCEL_ENV"}
    env["DATABASE_URL"] = url       # never the dev database, whatever happens
    if vercel_env is not None:
        env["VERCEL_ENV"] = vercel_env
    return subprocess.run([sys.executable, str(BACKEND / "scripts" / "vercel_build.py")],
                          cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("vercel_env", [None, "preview", "development"])
def test_the_build_step_skips_anything_but_production(tmp_path, vercel_env):
    run = _build(tmp_path, vercel_env)
    assert run.returncode == 0, run.stderr
    assert "no migration" in run.stdout
    assert "upgrade" not in run.stdout + run.stderr


@session_loop
async def test_a_first_production_build_migrates_and_loads_the_library(tmp_path):
    """The first deploy, on a database of its own — never cortex_test, which the
    library would leak into: from nothing to head, the extensions included,
    then the exercise library. A second build migrates nothing and only
    corrects the library. Run from elsewhere, so the paths resolve from the
    script."""
    fresh = "spica_first_deploy_check"
    admin = create_async_engine(TEST_URL.rsplit("/", 1)[0] + "/postgres",
                                isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with admin.connect() as c:
        await c.execute(text(f"DROP DATABASE IF EXISTS {fresh}"))
        await c.execute(text(f"CREATE DATABASE {fresh} TEMPLATE template0"))
    url = TEST_URL.rsplit("/", 1)[0] + "/" + fresh
    try:
        first = await asyncio.to_thread(_build, tmp_path, "production", url)
        assert first.returncode == 0, first.stderr
        assert "the database is at head" in first.stdout
        rows = sum(1 for _ in open(BACKEND / "data" / "workouts" / "exercises.csv")) - 1
        assert f"{rows} added, 0 updated" in first.stdout

        again = await asyncio.to_thread(_build, tmp_path, "production", url)
        assert again.returncode == 0, again.stderr
        assert f"0 added, {rows} updated" in again.stdout

        db = create_async_engine(url, poolclass=NullPool)
        async with db.connect() as c:
            seeded = await c.scalar(text("SELECT count(*) FROM exercises WHERE source = 'seed'"))
        await db.dispose()
        assert seeded == rows
    finally:
        async with admin.connect() as c:
            await c.execute(text(f"DROP DATABASE IF EXISTS {fresh} WITH (FORCE)"))
        await admin.dispose()


@session_loop
async def test_a_failed_migration_fails_the_build(tmp_path):
    """A non-zero exit is what stops Vercel promoting the release."""
    gone = TEST_URL.rsplit("/", 1)[0] + "/spica_no_such_database"
    run = await asyncio.to_thread(_build, tmp_path, "production", gone)
    assert run.returncode != 0


# ─── the tick's log ──────────────────────────────────────────────────────────

def _tick():
    spec = importlib.util.spec_from_file_location("run_due", BACKEND / "scripts" / "run_due.py")
    tick = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tick)
    return tick


def test_the_tick_on_github_says_counts_never_the_ledger():
    """GitHub keeps a run's log for months; a payment's lede or a nudge's
    line there would outlive the row, where per-item delete cannot reach."""
    tick = _tick()
    ran = [
        (SimpleNamespace(job="categorise", last_error=None),
         SimpleNamespace(text="₹180 ka Egg roll check kar lo", cards=[
             {"kind": "agent", "text": "₹180 ka Egg roll check kar lo"},
             {"kind": "confirm", "lede": "₹180 · Egg roll"}])),
        (SimpleNamespace(job="morning_brief", last_error=None),
         [SimpleNamespace(title="Your day", line="₹2,400 left to spend"),
          SimpleNamespace(title="Meals today", line=None)]),
    ]
    assert list(tick.lines(ran, quiet=True)) == [
        "Review payments: a turn, 1 card", "Your day: 2 nudges"]
    by_hand = "\n".join(tick.lines(ran, quiet=False))
    assert "Egg roll" in by_hand and "₹2,400" in by_hand, "by hand, the detail is the point"

    broke = SimpleNamespace(job="categorise",
                            last_error="IntegrityError: [parameters: ('Egg roll', 18000)]")
    failed = [(broke, None)]
    assert list(tick.lines(failed, quiet=True)) == ["Review payments: failed — IntegrityError"]

    workflow = (BACKEND.parent / ".github" / "workflows" / "tick.yml").read_text()
    assert "scripts/run_due.py --quiet" in workflow


def test_the_tick_on_github_logs_the_template_not_the_values():
    """A failed job logs its traceback, and a failed query's carries the row."""
    try:
        raise ValueError("Egg roll 18000")
    except ValueError:
        record = logging.getLogger("app.agent.plan").makeRecord(
            "app.agent.plan", logging.WARNING, __file__, 1, "plan unusable: %r",
            ("Egg roll",), sys.exc_info())
    assert _tick().Redacted().format(record) == (
        "WARNING app.agent.plan: plan unusable: %r (ValueError)")
