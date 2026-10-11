"""
The tick. One crontab line, forever. spec/in-progress/schedules.md.

    35 * * * *  cd /path/to/backend && PYTHONPATH=. uv run python scripts/run_due.py

Hourly, not every five minutes: Neon's compute sleeps after five idle minutes
and every tick wakes it (spec/in-progress/deploy.md). Deployed, that line is
.github/workflows/tick.yml, which runs it `--quiet`.

It asks one question — which schedules are due? — and runs those. Adding the
morning brief later adds a ROW, not another crontab line; on Android the same
rows are read by WorkManager. That is the whole reason a schedule is data.

Safe to run by hand and safe to run twice: a job is stamped with the local day
it ran, so nothing runs twice in one day whatever fires the tick.

    PYTHONPATH=. uv run python scripts/run_due.py --list     what is due, run nothing
    PYTHONPATH=. uv run python scripts/run_due.py --at 20:40 pretend it is that time
    PYTHONPATH=. uv run python scripts/run_due.py --quiet    counts only, as on GitHub
"""

import argparse
import asyncio
import logging
from collections.abc import Iterator
from datetime import datetime, time

from app.agent.jobs import IST, JOBS, due, run_due
from app.db import SessionLocal


class Redacted(logging.Formatter):
    """A log record without its values: the message's template rather than its
    arguments, and an exception's type rather than its text or traceback —
    either can quote a row (a failed INSERT carries its parameters)."""

    def format(self, record: logging.LogRecord) -> str:
        exc = record.exc_info[0] if record.exc_info else None
        return f"{record.levelname} {record.name}: {record.msg}" + (
            f" ({exc.__name__})" if exc else "")


def lines(ran: list, quiet: bool) -> Iterator[str]:
    """What the tick says about each run. Quiet says what ran and how many,
    never what it found: a nudge's line and a payment's lede quote the ledger,
    and GitHub keeps a run's log for months — past any row deleted since."""
    for row, out in ran:
        label = JOBS[row.job].label
        if row.last_error:
            # The type alone when quiet: the message can quote a row.
            yield f"{label}: failed — {row.last_error.split(':')[0] if quiet else row.last_error}"
        elif isinstance(out, list):      # a nudges job: what the bell now holds
            yield f"{label}: {len(out)} nudge{'s' if len(out) != 1 else ''}"
            if not quiet:
                for n in out:
                    yield f"    · {n.title}" + (f" — {n.line}" if n.line else "")
        elif out is None:
            yield f"{label}: nothing to report"
        elif quiet:
            n = sum(c["kind"] != "agent" for c in out.cards)
            yield f"{label}: a turn, {n} card{'s' if n != 1 else ''}"
        else:
            yield f"{label}: {out.text}"
            for c in out.cards:
                if c["kind"] == "confirm":
                    yield f"    · {c['lede']}"


async def main(at: time | None, show: bool, quiet: bool) -> None:
    if quiet:
        handler = logging.StreamHandler()
        handler.setFormatter(Redacted())
        logging.basicConfig(level=logging.WARNING, handlers=[handler])
    when = datetime.now(IST)
    if at is not None:
        when = when.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    async with SessionLocal() as session:
        if show:
            rows = await due(session, when)
            print(f"{when:%Y-%m-%d %H:%M} — {len(rows)} due")
            for r in rows:
                print(f"  {r.job:<16} {r.at_local_time} {r.repeat:<7} "
                      f"grace {r.grace_hours}h  last run {r.last_run_local_day}")
            return
        ran = await run_due(session, when)
        if not ran:
            print(f"{when:%Y-%m-%d %H:%M} — nothing due")
        for line in lines(ran, quiet):
            print(line)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--list", action="store_true", help="what is due, run nothing")
    ap.add_argument("--at", type=time.fromisoformat, default=None,
                    help="HH:MM — pretend it is that time today")
    ap.add_argument("--quiet", action="store_true",
                    help="what ran and how many, never what it found")
    a = ap.parse_args()
    asyncio.run(main(a.at, a.list, a.quiet))
