"""
Does the skill-file approach work? Measured before a card is drawn.
spec/in-progress/categorise.md § The evaluation · spec/agent.md Phase C.

Ground truth: expense rows the user categorised at confidence 1.0, not
*Other*. Split by date — everything is learned from rows before the cutoff,
then every row from the cutoff on is predicted blind and scored.

    PYTHONPATH=. uv run python scripts/categorise_eval.py                 # tiers 0–2
    PYTHONPATH=. uv run python scripts/categorise_eval.py --no-model      # free tiers only (T3)
    PYTHONPATH=. uv run python scripts/categorise_eval.py --cutoff 2026-08-20
    PYTHONPATH=. uv run python scripts/categorise_eval.py --misses        # print every wrong guess
    PYTHONPATH=. uv run python scripts/categorise_eval.py --model gpt-5.6-terra --effort medium

Dry by construction: nothing is written, the session is never committed.

Two bars, from agent.md: ≥ 70% correct overall or the approach is wrong;
≥ 95% correct where confidence ≥ 0.85 or the threshold rises.
"""

import argparse
import asyncio
from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import select

from app.agent.categorise import (
    SILENT,
    Guess,
    _item,
    decide,
    learn,
    signals_for,
    tier_model,
)
from app.db import SessionLocal
from app.models.paisa import Transaction
from scripts._user import pick_user


async def main(cutoff: date, use_model: bool, misses: bool, model_id: str | None,
               effort: str | None) -> None:
    async with SessionLocal() as session:
        user = await pick_user(session)
        learned = await learn(session, user, before=cutoff)
        truth = list((await session.scalars(
            select(Transaction).where(
                Transaction.user_id == user, Transaction.deleted_at.is_(None),
                Transaction.kind == "expense", Transaction.confidence >= 1.0,
                Transaction.category != "Other", Transaction.local_day >= cutoff)
            .order_by(Transaction.occurred_at))).all())
        # The previous row for the session signal comes from the whole ledger,
        # as it would at run time.
        everything = list((await session.scalars(
            select(Transaction).where(Transaction.user_id == user,
                                      Transaction.deleted_at.is_(None))
            .order_by(Transaction.occurred_at))).all())
        prev_of = {}
        last = None
        for t in everything:
            prev_of[t.id] = last
            last = t

        guess: dict[str, Guess] = {}
        to_model = []
        sig = {}
        for t in truth:
            s = signals_for(t, learned, prev_of.get(t.id))
            sig[t.id] = s
            g = decide(t, s, learned)
            if g is not None:
                guess[t.id] = g
            else:
                to_model.append(_item(t, s))
        used = ""
        if use_model and to_model:
            from_model, used = await tier_model(to_model, learned, model_id=model_id,
                                                effort=effort)
            guess.update(from_model)

        by_tier: dict[str, Counter] = defaultdict(Counter)
        auto_n = auto_ok = ok = 0
        wrong = []
        for t in truth:
            g = guess.get(t.id)
            tier = g.by if g else "none"
            right = bool(g and g.category == t.category)
            by_tier[tier]["n"] += 1
            by_tier[tier]["ok"] += right
            ok += right
            if g and g.confidence >= SILENT:
                auto_n += 1
                auto_ok += right
            if not right:
                wrong.append((t, g))

        n = len(truth)
        print(f"learned from {learned.rows} rows before {cutoff}; "
              f"predicting {n} rows from {cutoff} on"
              + (f"; model {used}" if used else "; free tiers only"))
        print(f"{'tier':<12}{'rows':>6}{'right':>7}{'acc':>7}")
        for tier in ("dictionary", "rules", "llm", "none"):
            c = by_tier.get(tier)
            if c:
                acc = c["ok"] / c["n"]
                print(f"{tier:<12}{c['n']:>6}{c['ok']:>7}{acc:>7.0%}")
        print(f"{'overall':<12}{n:>6}{ok:>7}{ok / n if n else 0:>7.0%}"
              f"   ← bar 70%")
        print(f"{'auto ≥0.85':<12}{auto_n:>6}{auto_ok:>7}"
              f"{(auto_ok / auto_n) if auto_n else 0:>7.0%}"
              f"   ← bar 95% · {auto_n / n if n else 0:.0%} of rows decided without asking")
        if misses and wrong:
            print("\nmisses:")
            for t, g in wrong:
                got = f"{g.category} {g.confidence:.2f} [{g.by}] {g.why}" if g else "—"
                print(f"  {t.local_day}  ₹{round(t.amount_paise / 100):>6}  "
                      f"{(t.counterparty_name or t.description)[:30]:<30}  "
                      f"truth {t.category:<16} got {got}")
        await session.rollback()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cutoff", type=date.fromisoformat, default=date(2026, 8, 15),
                    help="learn from rows before this day; predict from it on")
    ap.add_argument("--no-model", action="store_true", help="free tiers only")
    ap.add_argument("--misses", action="store_true", help="print every wrong guess")
    ap.add_argument("--model", default=None, help="override CATEGORISE_MODEL for this run")
    ap.add_argument("--effort", default=None, help="override CATEGORISE_EFFORT for this run")
    a = ap.parse_args()
    asyncio.run(main(a.cutoff, not a.no_model, a.misses, a.model, a.effort))
