"""
The API project's build step on Vercel. spec/in-progress/deploy.md.

Vercel runs it — `[tool.vercel.scripts] build` in pyproject.toml — after the
dependencies are installed and before the release serves. On a production
build it migrates the database to head, then loads the exercise library from
data/workouts/exercises.csv — nobody's data, and idempotent on name, so a
fresh database gets the library and a later build only corrects it. On
anything else it says so and does nothing, because a preview must never move
the schema production reads.

Any failure exits non-zero, which fails the build, and the release before it
keeps serving. The migration runs before the new code serves, which is why
migrations stay additive.

    VERCEL_ENV=production python scripts/vercel_build.py
"""

import asyncio
import os
import sys
from pathlib import Path

from alembic.config import Config

from alembic import command

BACKEND = Path(__file__).resolve().parent.parent


def main() -> None:
    env = os.environ.get("VERCEL_ENV")
    if env != "production":
        print(f"vercel_build: VERCEL_ENV is {env or 'unset'}, not production — no migration")
        return
    # alembic.ini's `prepend_sys_path = .` and the settings' `.env` are both
    # read from the working directory, so it is the backend, wherever Vercel
    # started us.
    os.chdir(BACKEND)
    print("vercel_build: production — alembic upgrade head", flush=True)
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    print("vercel_build: the database is at head")
    sys.path.insert(0, str(BACKEND))
    from scripts.import_exercises_csv import main as load_library
    print("vercel_build: the exercise library — ", end="", flush=True)
    asyncio.run(load_library())


if __name__ == "__main__":
    main()      # an exception leaves with its traceback and exit code 1
