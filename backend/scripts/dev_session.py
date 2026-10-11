"""
A session for the Android debug build, minted without Google.

The emulator has no Google account and the Android OAuth client is not set up,
so the debug app accepts a token pushed into its private storage instead
(`android/app/src/debug/.../DevLogin.kt`). This writes one to a file (0600) and
never prints it — the token is as good as a password for the account.

    PYTHONPATH=. uv run python scripts/dev_session.py --user <id> --out /path/token

Then hand it to the app without it touching a command line:

    adb shell "run-as com.sonu.spica sh -c 'cat > files/dev_token'" < /path/token

Development only: it writes to whatever DATABASE_URL points at, and refuses a
database whose name does not look like a dev one.
"""

import argparse
import asyncio
import os
from pathlib import Path

from app.auth import issue_session
from app.config import settings
from app.db import SessionLocal
from scripts._user import pick_user


async def main(user: str | None, out: Path) -> None:
    url = settings().database_url
    if "prod" in url.rsplit("/", 1)[-1]:
        raise SystemExit("refusing: this looks like a production database")
    async with SessionLocal() as session:
        uid = await pick_user(session, user)
        token = await issue_session(session, uid, "cortex-android-debug")
        await session.commit()
    out.write_text(token)
    os.chmod(out, 0o600)
    print(f"session for {uid} written to {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user", default=None)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    asyncio.run(main(a.user, a.out))
