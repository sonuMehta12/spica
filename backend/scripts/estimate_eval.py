"""
Can the model estimate a meal's macros from the words alone?
spec/diet-logging.md §2 — the estimation stub, measured before it is built.

The ladder resolves *identity* (which foods, which pantry rows to spend) and
that is not in question here. What is in question is *worth*: the library's
numbers have no recorded provenance (30 of 41 foods carry a NULL
`nutrition_source`, and `dishes` has no such column at all), and a dish is a
fixed combination whose `servings` multiplies the whole bundle — so "3 roti"
against a "2 roti + sabzi" row is 6 rotis. This asks whether estimating from
the sentence does better.

**Ground truth is the user's own tracker**, so this measures *agreement with
how they already count*, not absolute truth. Agreement is the right target: if
the estimator matches their accounting, switching to it is invisible to them.

    PYTHONPATH=. uv run python scripts/estimate_eval.py            # 30 meals, one call
    PYTHONPATH=. uv run python scripts/estimate_eval.py -n 60
    PYTHONPATH=. uv run python scripts/estimate_eval.py --probes   # also the known failures

Dry by construction: nothing is written.
"""

import argparse
import asyncio
import json
import statistics

from sqlalchemy import text

from app import llm
from app.db import SessionLocal

# A draft of the real instruction — what the estimating rung would carry.
SYSTEM = """\
You estimate the nutrition of meals an Indian person logged in their own words.

For each item you are given the exact text they typed and which meal it was.
Return kcal, protein_g, carbs_g, fat_g and fibre_g for the WHOLE entry as
described — if they wrote "3 roti", estimate three rotis, not one.

How to read what they write:
- Counts mean pieces: "2 roti", "3 ande", "2 egg omelette" (an omelette made
  of the eggs stated, cooked in a little oil).
- "ghar ka" / "ghar ka khana" means home-cooked: less oil than a restaurant,
  normal household portions.
- A katori is about 150 g, a glass about 200 ml, a plate is one full serving.
- Where a quantity is written in grams, use it exactly.
- North Indian home cooking unless the words say otherwise.

Estimate the portion a normal adult actually eats when the text does not say.
Do not refuse and do not return zero — a considered estimate is the point. Be
calibrated rather than generous: a wrong number the person believes is the
failure mode that matters.

Return ONE JSON array, nothing else, one object per input id:
[{"id": 1, "kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fibre_g": 0}]
"""

#: The cases the current library-lookup path gets wrong, from the session that
#: prompted this. No ground truth — printed for judgement, not scored.
PROBES = [
    "2 roti and 2 egg omletes",
    "3 roti",
    "2 egg omelette",
    "omelette",
    "1 katori dal aur 2 roti",
    "chai aur 2 biscuit",
]


def err(got: float, want: float) -> float | None:
    """Absolute percentage error, undefined when the truth is zero."""
    return None if not want else abs(got - want) / want * 100


async def main(n: int, probes: bool, calibrated: bool) -> None:
    async with SessionLocal() as s:
        user = (await s.execute(text(
            "SELECT id FROM users ORDER BY created_at LIMIT 1"))).scalar()
        rows = (await s.execute(text("""
            SELECT dish, meal_type, kcal, protein_g, carbs_g, fat_g
            FROM meal_logs
            WHERE user_id = :u AND deleted_at IS NULL
              AND confidence >= 1.0 AND kcal > 0
            ORDER BY md5(id) LIMIT :n
        """), {"u": user, "n": n})).all()

        # The user's OWN past portions, as calibration — spec/diet-logging.md §2:
        # "using **this user's** logged portions as the default — not generic
        # serving sizes. A thali means what their thalis have meant." Excludes
        # the meals being scored, or it would be answering with the answer.
        calib = ""
        if calibrated:
            held = {r.dish for r in rows}
            past = (await s.execute(text("""
                SELECT dish, kcal, protein_g FROM meal_logs
                WHERE user_id = :u AND deleted_at IS NULL AND confidence >= 1.0
                  AND kcal > 0 GROUP BY dish, kcal, protein_g
                ORDER BY count(*) DESC LIMIT 60
            """), {"u": user})).all()
            lines = [f"- {r.dish}: {r.kcal} kcal, {float(r.protein_g):g} g protein"
                     for r in past if r.dish not in held][:40]
            calib = ("\n\nWhat this person's own past entries were worth. Their "
                     "portions are the default, not generic serving sizes:\n"
                     + "\n".join(lines))

        items = [{"id": i, "text": r.dish, "meal": r.meal_type}
                 for i, r in enumerate(rows)]
        base = len(items)
        if probes:
            items += [{"id": base + j, "text": p, "meal": "Breakfast"}
                      for j, p in enumerate(PROBES)]

        raw, used = await llm.categorise(SYSTEM + calib, json.dumps(items, ensure_ascii=False))
        body = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        got = {g["id"]: g for g in json.loads(body[body.find("["):body.rfind("]") + 1])}

        print(f"{base} meals, one call, {used}"
              f"{'  · CALIBRATED on their own portions' if calibrated else ''}\n")
        print(f"{'meal':<40}{'kcal':>14}{'protein':>14}{'carbs':>12}")
        errs = {"kcal": [], "protein_g": [], "carbs_g": [], "fat_g": []}
        for i, r in enumerate(rows):
            g = got.get(i)
            if not g:
                continue
            truth = {"kcal": r.kcal, "protein_g": float(r.protein_g),
                     "carbs_g": float(r.carbs_g or 0), "fat_g": float(r.fat_g or 0)}
            for k in errs:
                e = err(float(g.get(k) or 0), truth[k])
                if e is not None:
                    errs[k].append(e)
            print(f"  {r.dish[:38]:<38}{g.get('kcal'):>6}/{truth['kcal']:<6}"
                  f"{float(g.get('protein_g') or 0):>7.0f}/{truth['protein_g']:<6.0f}"
                  f"{float(g.get('carbs_g') or 0):>7.0f}/{truth['carbs_g']:<5.0f}")

        print(f"\n{'':<12}{'median err':>12}{'mean err':>11}{'within 20%':>13}{'within 35%':>13}")
        for k, xs in errs.items():
            if not xs:
                continue
            near = sum(1 for x in xs if x <= 20) / len(xs) * 100
            ok = sum(1 for x in xs if x <= 35) / len(xs) * 100
            print(f"  {k:<10}{statistics.median(xs):>11.0f}%{statistics.mean(xs):>10.0f}%"
                  f"{near:>12.0f}%{ok:>12.0f}%")

        if probes:
            print("\nthe cases the library path gets wrong today "
                  "(no ground truth — judge these by eye):")
            for j, p in enumerate(PROBES):
                g = got.get(base + j)
                if g:
                    print(f"  {p:<28} {g.get('kcal'):>5} kcal  "
                          f"{float(g.get('protein_g') or 0):>4.0f} p  "
                          f"{float(g.get('carbs_g') or 0):>4.0f} c  "
                          f"{float(g.get('fibre_g') or 0):>4.0f} fibre")
        await s.rollback()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-n", type=int, default=30, help="how many logged meals to score")
    ap.add_argument("--probes", action="store_true", help="also run the known failures")
    ap.add_argument("--calibrated", action="store_true",
                    help="pass this user's own past portions as context")
    a = ap.parse_args()
    asyncio.run(main(a.n, a.probes, a.calibrated))
