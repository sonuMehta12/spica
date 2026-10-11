"""
The cron door onto the nightly batch. spec/in-progress/categorise.md.

    PYTHONPATH=. uv run python scripts/categorise.py            # everything pending
    PYTHONPATH=. uv run python scripts/categorise.py --day 2026-09-15
    PYTHONPATH=. uv run python scripts/categorise.py --dry      # decide, write nothing
    PYTHONPATH=. uv run python scripts/categorise.py --skill    # print the skill file and stop

Idempotent: a row the batch has looked at has an open prediction and is not
looked at again until the user answers it — so running it twice is safe.

**Nothing runs this automatically yet.** A crontab line would work
(`30 20 * * *`, IST) but the schedule belongs to the user, not to a machine
they never see: `spec/in-progress/schedules.md` puts the time in a row and has
one dispatcher read it. Until that ships, this is a command and the agent's
`categorise_now` is the other door.

The same function the `categorise_now` tool calls — one function, two doors.
"""

import argparse
import asyncio
from datetime import date

from app.agent.categorise import categorise, learn, skill_file
from app.db import SessionLocal
from scripts._user import pick_user


def _rupees(p: int) -> str:
    return f"₹{round(p / 100):,}"


async def main(day: date | None, dry: bool, show_skill: bool, no_model: bool) -> None:
    async with SessionLocal() as session:
        user = await pick_user(session)
        if show_skill:
            print(skill_file(await learn(session, user)))
            return
        r = await categorise(session, user, day, dry=dry, use_model=not no_model)
        tiers = r["by_tier"]
        print(f"examined {r['examined']} · learned from {r['labelled_rows']} labelled rows"
              f"{' · DRY' if dry else ''}")
        print(f"tiers — dictionary {tiers['dictionary']} · rules {tiers['rules']} · "
              f"model {tiers['llm']} · unsure {tiers['unsure']}")
        print(f"written {len(r['written'])} · agreed {len(r['agreed'])} · "
              f"asked {len(r['proposed'])}")
        if r["written"]:
            print(f"\nwritten ({len(r['written'])}):")
            for w in r["written"]:
                g = w["guess"]
                print(f"  {w['local_day']}  {_rupees(w['amount_paise']):>8}  {w['payee'][:28]:<28}"
                      f"  {w['was']} → {g['category']}  {g['confidence']:.2f}  "
                      f"[{g['by']}] {g['why']}")
        if r["agreed"]:
            print(f"\nagreed ({len(r['agreed'])}) — the category already there, now better held:")
            for w in r["agreed"]:
                g = w["guess"]
                print(f"  {w['local_day']}  {_rupees(w['amount_paise']):>8}  {w['payee'][:28]:<28}"
                      f"  {g['category']}  {g['confidence']:.2f}  [{g['by']}] {g['why']}")
        if r["proposed"]:
            print(f"\nproposed ({len(r['proposed'])}) — the user is asked:")
            for w in r["proposed"]:
                g = w["guess"]
                print(f"  {w['local_day']}  {_rupees(w['amount_paise']):>8}  {w['payee'][:28]:<28}"
                      f"  {w['was']} → {g['category']}?  {g['confidence']:.2f}  "
                      f"[{g['by']}] {g['why']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--day", type=date.fromisoformat, default=None)
    ap.add_argument("--dry", action="store_true", help="decide, write nothing")
    ap.add_argument("--skill", action="store_true", help="print the generated skill file")
    ap.add_argument("--no-model", action="store_true", help="free tiers only")
    a = ap.parse_args()
    asyncio.run(main(a.day, a.dry, a.skill, a.no_model))
