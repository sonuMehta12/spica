"""
What a plate is worth. spec/in-progress/meal-estimates.md.

The ladder answers *what is this* — which foods, which pantry rows to spend.
This answers *what is it worth*, and the two were conflated: a plate the
library had never seen was logged at 0 kcal, because the library was the only
thing that produced a number. It was never meant to be:
`spec/done/dishes.md` says a dish exists so the agent can suggest the next one,
30 of 41 foods record no `nutrition_source`, and a dish's serving count
multiplies the whole bundle — so *"3 roti"* against *"2 roti + sabzi"* is six
rotis.

So the model prices the plate, with the ladder's findings and the person's own
corrected portions as **context, never as an answer**. Measured before it was
built (`scripts/estimate_eval.py`): 22% median error on kcal against their own
tracker, and calibration on their portions moves the *tail* — within-35% goes
60% to 70% — which is what matters, because a day's total is a sum.

Nothing here is ever silent. The write lands below full confidence with the
amber dot, and `estimated_*` freezes what was said before the user touched it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import llm

log = logging.getLogger(__name__)

SKILL_FILE = Path(__file__).with_name("skills") / "estimate.md"

#: An estimate is a guess and the card must say so. The same number
#: `log_payment` stamps on a category the user did not state.
ESTIMATED = 0.6
#: How many of their own entries go into the context. Enough to calibrate,
#: small enough that the corrected ones are not drowned.
RECENT = 30
#: Corrections outrank everything else in the file, so they are listed apart
#: and never trimmed away by the recent-portions cap.
CORRECTIONS = 20


#: The ladder rungs a name must reach before its food may leave a shelf. The
#: model supplies the *amount*; identity stays a database lookup, so an
#: ingredient it invented resolves to nothing and spends nothing.
SPENDABLE = ("exact", "alias")


@dataclass
class Ingredient:
    """One raw food the model believes went into the plate, already resolved
    to a row and converted into that food's own unit."""

    food_id: str
    name: str
    said: str
    #: In the food's own unit — grams for atta, pieces for eggs.
    quantity: int
    rung: str


@dataclass
class Estimate:
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fibre_g: float
    why: str = ""
    #: The one thing the model had to decide that the user did not say, in
    #: their register — shown under the number so they can disagree with it.
    assumption: str = ""
    #: What the plate was made of, as the model named it. Unresolved until
    #: `resolve_ingredients` turns names into rows.
    raw_ingredients: list[dict] = field(default_factory=list)


async def _context(session: AsyncSession, user: str, lines: list[dict]) -> str:
    """The generated half of the skill file: what this person's food has been
    worth, built from rows at call time and never stored.

    A stored sentence about their data starts lying the day a row changes, so
    this is rebuilt every call — the same rule the paisa skill file follows.
    """
    out: list[str] = []

    fixed = (await session.execute(text("""
        SELECT dish, kcal, protein_g, estimated_kcal
        FROM meal_logs
        WHERE user_id = :u AND deleted_at IS NULL AND corrected_at IS NOT NULL
        ORDER BY corrected_at DESC LIMIT :n
    """), {"u": user, "n": CORRECTIONS})).all()
    if fixed:
        out.append("## They corrected these — their number is the right one")
        for r in fixed:
            was = f" (we had said {r.estimated_kcal})" if r.estimated_kcal else ""
            out.append(f"- {r.dish}: {r.kcal} kcal, {float(r.protein_g):g} g protein{was}")
        out.append("")

    recent = (await session.execute(text("""
        SELECT dish, kcal, protein_g, count(*) n
        FROM meal_logs
        WHERE user_id = :u AND deleted_at IS NULL AND kcal > 0
        GROUP BY dish, kcal, protein_g
        ORDER BY count(*) DESC, max(occurred_at) DESC LIMIT :n
    """), {"u": user, "n": RECENT})).all()
    if recent:
        out.append("## Their usual portions")
        for r in recent:
            often = f" · eaten {r.n}×" if r.n > 1 else ""
            out.append(f"- {r.dish}: {r.kcal} kcal, {float(r.protein_g):g} g protein{often}")
        out.append("")

    # What the ladder matched, labelled as evidence about a *different* plate.
    hits = [x for x in lines if x.get("dish_id") or x.get("food_id")]
    if hits:
        out.append("## Rows their ledger already holds that look related")
        out.append("Calibrate against these. They are not the plate in front of "
                   "you unless they plainly are, and never scale one by a count.")
        for h in hits:
            if h.get("dish_id"):
                d = (await session.execute(text(
                    "SELECT name, serving_label, kcal, protein_g FROM dishes WHERE id = :i"),
                    {"i": h["dish_id"]})).first()
                if d:
                    out.append(f'- dish "{d.name}", one serving is {d.serving_label or "?"}: '
                               f"{d.kcal or '?'} kcal, {float(d.protein_g):g} g protein "
                               f'(matched from their words "{h["said"]}")')
            else:
                f = (await session.execute(text(
                    "SELECT name, unit, grams_per_unit, kcal_100g, protein_g_100g "
                    "FROM foods WHERE id = :i"), {"i": h["food_id"]})).first()
                if f:
                    per = (f"one {f.unit} is {float(f.grams_per_unit):g} g, "
                           if f.grams_per_unit else "")
                    out.append(f'- food "{f.name}": {per}'
                               f"{f.kcal_100g or '?'} kcal and "
                               f"{float(f.protein_g_100g or 0):g} g protein per 100 g "
                               f'(matched from their words "{h["said"]}")')
        out.append("")

    return "\n".join(out) if out else "(nothing logged yet — estimate from the words alone)"


def parse(raw: str) -> Estimate | None:
    """What stands between the model and the ledger. Unparseable, or a plate
    with no calories at all, is treated as no answer — the caller falls back
    rather than writing a zero the card would read as *"no calories"*."""
    try:
        body = raw.strip()
        if body.startswith("```"):
            body = body.strip("`")
        data = json.loads(body[body.find("{"):body.rfind("}") + 1])
    except (ValueError, AttributeError):
        return None

    def num(key: str) -> float:
        try:
            return max(0.0, float(data.get(key) or 0))
        except (TypeError, ValueError):
            return 0.0

    kcal = int(num("kcal"))
    if kcal <= 0:
        # The skill file forbids zero; a zero here means it did not answer.
        return None
    raw = data.get("ingredients")
    ingredients = [x for x in raw if isinstance(x, dict) and x.get("food")] \
        if isinstance(raw, list) else []
    return Estimate(
        kcal=kcal, protein_g=round(num("protein_g"), 1),
        carbs_g=round(num("carbs_g"), 1), fat_g=round(num("fat_g"), 1),
        fibre_g=round(num("fibre_g"), 1),
        why=str(data.get("why") or "")[:200],
        assumption=str(data.get("assumption") or "")[:120],
        raw_ingredients=ingredients[:12],
    )


async def resolve_ingredients(session: AsyncSession, user: str,
                              said: list[dict]) -> list[Ingredient]:
    """Turn the model's ingredient *names* into rows it may actually spend.

    Names, never ids — that is what makes this safe. Each is matched by the
    same ladder the rest of the app uses and accepted only at `exact` or
    `alias`, so an ingredient the model invented resolves to nothing and takes
    nothing off a shelf. Grams are converted into the food's own unit: 100 g of
    eggs is 2 pieces, because `foods.grams_per_unit` says an egg is 50 g.
    """
    from app.agent.ladder import resolve_one

    out: list[Ingredient] = []
    for item in said:
        name = str(item.get("food") or "").strip()
        try:
            grams = float(item.get("grams") or 0)
        except (TypeError, ValueError):
            grams = 0
        if not name or grams <= 0:
            continue
        hit = await resolve_one(session, user, name)
        if not hit["matched"] or hit["rung"] not in SPENDABLE or not hit["food_id"]:
            continue
        row = (await session.execute(text(
            "SELECT unit, grams_per_unit FROM foods WHERE id = :i"),
            {"i": hit["food_id"]})).first()
        qty = grams
        if row and row.unit != "g" and row.grams_per_unit:
            qty = grams / float(row.grams_per_unit)
        qty = int(round(qty))
        if qty <= 0:
            continue
        out.append(Ingredient(food_id=hit["food_id"], name=hit["name"], said=name,
                              quantity=qty, rung=hit["rung"]))
    return out


async def price(session: AsyncSession, user: str, said: str, meal_type: str,
                lines: list[dict]) -> Estimate | None:
    """One call for the whole plate.

    Priced whole rather than per item on purpose: *"chicken fried rice jisme
    chicken na ke barabar thi"* is one judgement, and splitting it into items
    loses the clause that carries it.

    Returns None when the model fails or answers with nothing usable. The
    caller keeps the log either way — losing a meal because a number could not
    be produced would be the worst outcome available.
    """
    system = SKILL_FILE.read_text() + "\n" + await _context(session, user, lines)
    payload = json.dumps({
        "text": said, "meal": meal_type,
        "what_the_matcher_found": [
            {"said": x["said"], "matched": x["name"], "rung": x["rung"],
             "needs_quantity": x.get("needs_quantity", False)}
            for x in lines
        ],
    }, ensure_ascii=False)
    try:
        raw, _ = await llm.categorise(system, payload)
    except Exception:  # noqa: BLE001 — the log matters more than the number
        log.exception("meal estimate failed for %r", said[:60])
        return None
    got = parse(raw)
    if got is None:
        log.warning("meal estimate unusable for %r: %r", said[:60], raw[:200])
    return got
