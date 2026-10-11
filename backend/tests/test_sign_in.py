"""
spec/in-progress/sign-in.md — Definition of done.

Google's half is stubbed at exactly one seam: `_verify_blocking`, the function
that does the signature check. Everything after it — who is found, who is
created, who is refused, what the token then unlocks — is the real code path,
because that is where every decision in the spec lives.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

pytestmark = pytest.mark.asyncio(loop_scope="session")

# App imports are deliberately local to each test. `app.db` builds its engine
# from `settings()` at import time, and `settings()` is cached — importing it
# at module scope happens during collection, before the fixture points
# DATABASE_URL at cortex_test, and alembic would then migrate the dev database.


def claims(email: str, sub: str = "google-sub-1", **extra) -> dict:
    return {
        "sub": sub, "email": email, "email_verified": True,
        "iss": "https://accounts.google.com", "given_name": "Asha",
        "name": "Asha Verma", "picture": "https://lh3.googleusercontent.com/a/x",
        **extra,
    }


def a_payment(row_id: str, description: str, paise: int) -> dict:
    return {
        "id": row_id, "occurred_at": "2026-09-15T10:00:00Z", "local_day": "2026-09-15",
        "amount_paise": paise, "direction": "debit", "kind": "expense",
        "category": "Khana/Grocery", "description": description, "source": "manual",
    }


@pytest.fixture
def google(monkeypatch):
    """Stand in for Google. The route still runs its own issuer, email and
    verified-email checks against whatever this returns."""
    def install(payload):
        monkeypatch.setattr("app.routes.auth._verify_blocking", lambda _c: payload)
    return install


@pytest.fixture
def invite(monkeypatch):
    def install(value: str):
        from app.config import settings
        monkeypatch.setattr(settings(), "allowed_emails", value, raising=False)
    return install


async def test_an_invited_email_gets_a_user_and_a_session(client, db_session, google, invite):
    from app.auth import hash_token
    from app.models.users import Session, User
    google(claims("asha@gmail.com"))
    invite("asha@gmail.com")

    r = await client.post("/auth/google", json={"credential": "x"})
    assert r.status_code == 200, r.text
    body = r.json()

    row = await db_session.scalar(select(User).where(User.google_sub == "google-sub-1"))
    assert row is not None
    assert (row.email, row.display_name) == ("asha@gmail.com", "Asha")
    assert row.avatar_url == "https://lh3.googleusercontent.com/a/x"
    assert body["user"]["email"] == "asha@gmail.com"

    # The row keeps the hash; the raw token exists only in the response.
    stored = await db_session.scalar(
        select(Session).where(Session.token_hash == hash_token(body["token"])))
    assert stored is not None and stored.user_id == row.id


async def test_signing_in_again_is_a_second_session_not_a_second_user(
    client, db_session, google, invite
):
    google(claims("asha@gmail.com"))
    invite("asha@gmail.com")
    await client.post("/auth/google", json={"credential": "x"})
    before = await db_session.scalar(text("SELECT count(*) FROM users"))

    r = await client.post("/auth/google", json={"credential": "x"})
    assert r.status_code == 200
    assert await db_session.scalar(text("SELECT count(*) FROM users")) == before
    assert await db_session.scalar(
        text("SELECT count(*) FROM sessions WHERE user_id = (SELECT id FROM users "
             "WHERE google_sub = 'google-sub-1')")) >= 2


async def test_an_uninvited_email_is_refused_and_writes_nothing(
    client, db_session, google, invite
):
    google(claims("stranger@gmail.com", sub="google-sub-stranger"))
    invite("asha@gmail.com")
    before = await db_session.scalar(text("SELECT count(*) FROM users"))

    r = await client.post("/auth/google", json={"credential": "x"})
    assert r.status_code == 403
    assert await db_session.scalar(text("SELECT count(*) FROM users")) == before


async def test_a_star_opens_the_door_to_anyone(client, db_session, google, invite):
    from app.models.users import User
    google(claims("anyone@gmail.com", sub="google-sub-anyone"))
    invite("*")

    r = await client.post("/auth/google", json={"credential": "x"})
    assert r.status_code == 200
    assert await db_session.scalar(
        select(User).where(User.google_sub == "google-sub-anyone")) is not None


async def test_an_existing_user_signs_in_even_when_the_list_no_longer_names_them(
    client, google, invite
):
    """Removing an address must never lock someone out of their own ledger."""
    google(claims("asha@gmail.com"))
    invite("asha@gmail.com")
    assert (await client.post("/auth/google", json={"credential": "x"})).status_code == 200

    invite("somebody-else@gmail.com")
    assert (await client.post("/auth/google", json={"credential": "x"})).status_code == 200


async def test_a_row_that_carries_the_email_is_claimed_not_duplicated(
    client, db_session, google, invite
):
    """The seeded row, and every imported row pointing at it, comes under the
    account instead of being stranded on a user nobody can sign in as."""
    from app.models.users import User
    seeded = await db_session.scalar(select(User).order_by(User.created_at).limit(1))
    seeded.email = "owner@gmail.com"
    await db_session.commit()
    before = await db_session.scalar(text("SELECT count(*) FROM users"))

    google(claims("owner@gmail.com", sub="google-sub-owner"))
    invite("")  # not on the list — claiming is not creating

    r = await client.post("/auth/google", json={"credential": "x"})
    assert r.status_code == 200
    assert await db_session.scalar(text("SELECT count(*) FROM users")) == before
    await db_session.refresh(seeded)
    assert seeded.google_sub == "google-sub-owner"


async def test_an_unverified_google_email_is_refused(client, google, invite):
    google(claims("asha@gmail.com", email_verified=False))
    invite("*")
    assert (await client.post("/auth/google", json={"credential": "x"})).status_code == 401


async def test_a_credential_google_rejects_is_a_401(client, monkeypatch, invite):
    def boom(_c):
        raise ValueError("Token expired")
    monkeypatch.setattr("app.routes.auth._verify_blocking", boom)
    invite("*")
    assert (await client.post("/auth/google", json={"credential": "x"})).status_code == 401


# ─── the lock itself ─────────────────────────────────────────────────────────

async def test_health_is_open_and_everything_else_is_not(anon):
    assert (await anon.get("/health")).status_code == 200
    r = await anon.get("/deck", params={"to": "2026-09-15"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


async def test_an_unknown_token_is_a_401_not_a_500(anon):
    """A stale token in a browser must read as *sign in*, not as a dead API."""
    r = await anon.get("/deck", params={"to": "2026-09-15"},
                       headers={"Authorization": "Bearer nonsense"})
    assert r.status_code == 401


async def test_a_malformed_header_is_a_401(anon):
    for value in ("", "Bearer", "Basic abc", "token-without-scheme"):
        r = await anon.get("/deck", params={"to": "2026-09-15"},
                           headers={"Authorization": value})
        assert r.status_code == 401, value


async def test_an_expired_session_is_refused_and_removed(anon, db_session):
    from app.auth import hash_token
    from app.models.users import Session, User
    user_id = await db_session.scalar(select(User.id).order_by(User.created_at).limit(1))
    raw = "expired-token"
    db_session.add(Session(user_id=user_id, token_hash=hash_token(raw),
                           expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    await db_session.commit()

    r = await anon.get("/deck", params={"to": "2026-09-15"},
                       headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 401
    assert await db_session.scalar(
        select(Session).where(Session.token_hash == hash_token(raw))) is None


async def test_signing_out_kills_that_token_and_no_other(client, db_session, google, invite):
    google(claims("asha@gmail.com"))
    invite("asha@gmail.com")
    first = (await client.post("/auth/google", json={"credential": "x"})).json()["token"]
    second = (await client.post("/auth/google", json={"credential": "x"})).json()["token"]

    r = await client.delete("/auth/session", headers={"Authorization": f"Bearer {first}"})
    assert r.status_code == 204

    auth = {"Authorization": f"Bearer {first}"}
    assert (await client.get("/users/me", headers=auth)).status_code == 401
    # The phone keeps working when the laptop signs out.
    assert (await client.get("/users/me",
                             headers={"Authorization": f"Bearer {second}"})).status_code == 200


async def test_one_users_token_cannot_reach_another_users_rows(
    client, db_session, google, invite
):
    """The leak test. Every route filters by the seam, so a row that is not
    yours is a 404 — a 403 would confirm the id exists."""
    mine = (await client.post("/transactions", json=a_payment(
        "01TESTMINETX0000000000000", "Chai", 5000))).json()

    google(claims("other@gmail.com", sub="google-sub-other"))
    invite("*")
    theirs = (await client.post("/auth/google", json={"credential": "x"})).json()["token"]
    auth = {"Authorization": f"Bearer {theirs}"}

    assert (await client.get("/transactions", params={"ids": mine["id"]},
                             headers=auth)).json() == []
    assert (await client.patch(f"/transactions/{mine['id']}", json={"description": "stolen"},
                               headers=auth)).status_code == 404
    assert (await client.delete(f"/transactions/{mine['id']}", headers=auth)).status_code == 404


async def test_deleting_the_account_takes_the_rows_and_leaves_everyone_else(
    client, db_session, google, invite
):
    from app.models.users import User
    google(claims("leaving@gmail.com", sub="google-sub-leaving"))
    invite("*")
    token = (await client.post("/auth/google", json={"credential": "x"})).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    gone = await db_session.scalar(select(User).where(User.google_sub == "google-sub-leaving"))
    gone_id = gone.id

    await client.post("/transactions",
                      json=a_payment("01TESTTHEIRSTX00000000000", "Auto", 900), headers=auth)

    assert (await client.delete("/users/me", headers=auth)).status_code == 204
    assert (await client.get("/users/me", headers=auth)).status_code == 401
    assert await db_session.scalar(select(User).where(User.id == gone_id)) is None
    assert await db_session.scalar(
        text("SELECT count(*) FROM transactions WHERE user_id = :u"), {"u": gone_id}) == 0
    # The seeded user is untouched.
    assert await db_session.scalar(text("SELECT count(*) FROM users")) >= 1


async def test_the_agent_stops_talking_at_the_limit_and_the_ledger_does_not(
    client, monkeypatch, fake
):
    from app.config import settings
    monkeypatch.setattr(settings(), "daily_turn_limit", 0, raising=False)
    r = await client.post("/chat", json={"message": "kitna bacha hai",
                                         "local_day": "2026-09-15"})
    assert r.status_code == 200
    assert r.json()["model"] == "limit"

    # Everything that is not the agent keeps working.
    assert (await client.get("/deck", params={"to": "2026-09-15"})).status_code == 200
    assert (await client.post(
        "/transactions",
        json=a_payment("01TESTLIMITTX00000000000A", "Paani", 100))).status_code in (200, 201)
