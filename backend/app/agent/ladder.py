"""
A spoken meal, resolved into lines. spec/done/dishes.md § how a spoken meal
becomes lines.

*"2 roti aur dal, protein shake bhi"* has to become rows pointing at ids. Each
part is matched against the pool cheapest-first and stops at the first
confident hit:

    1  exact name          Whey shake
    2  alias               protein shake → Whey shake
    3  trigram similarity  sattu drnk → Sattu drink
    4  embedding           peanut keema → Moongphali keema   (phase B, not yet)
    5  nothing confident   the line stays unresolved

**Matching never creates a dish.** An unresolved line is shown on the card and
fixed by the user; inventing one is how a library fills with typos.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Where a sentence breaks into items — the separators the logs already use.
SPLIT = re.compile(r"\s*(?:\+|,|/|\baur\b|\band\b|\bwith\b|\bke saath\b)\s*", re.I)
#: Leading quantity: "2 roti", "1.5 katori dal", "2 ande ki".
QTY = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:x\s*)?", re.I)
#: Filler between a count and the food: "1 katori **ka** dal", "2 roti **ki**".
JOIN = re.compile(r"^(?:ka|ki|ke)\b\s*", re.I)
#: Noise that carries no food: "bhi", "tha", "khaya", "khai", "liya", "piya" —
#: and the English equivalents, because the composer takes both. Without them
#: "I eat 2 roti" never reaches the quantity parser (which wants the count at
#: the front), so the line goes unresolved and the pantry never spends.
NOISE = re.compile(
    r"\b(bhi|tha|thi|the|khaya|khai|khaye|liya|piya|kiya|hai|maine|mai|main"
    r"|i|ate|eat|had|have|having|today|just|some)\b", re.I)
#: Below this a trigram hit is a coincidence, not a match. Tuned against the
#: real library: "sattu drnk" scores ~0.55 on Sattu drink, unrelated pairs <0.2.
TRIGRAM_FLOOR = 0.35


def split_items(said: str) -> list[tuple[str, float | None]]:
    """The sentence, cut into candidate items with any leading quantity."""
    out: list[tuple[str, float | None]] = []
    for part in SPLIT.split(said or ""):
        clean = NOISE.sub(" ", part).strip(" .!-")
        clean = re.sub(r"\s+", " ", clean)
        if not clean:
            continue
        qty = None
        if (m := QTY.match(clean)):
            qty = float(m.group(1))
            clean = clean[m.end():].strip()
        if clean:
            out.append((clean, qty))
    return out


async def measure_in(session: AsyncSession, said: str) -> tuple[int | None, str]:
    """A spoken unit at the front of an item — *katori*, *glass*, *chammach* —
    resolved to grams, and the rest of the phrase.

    `measures` holds these because *1 katori dal* is a food plus a unit, not a
    dish. Longest phrase first, so *bada katora* beats *katora*.
    """
    rows = (await session.execute(text(
        "SELECT phrase, grams FROM measures WHERE deleted_at IS NULL"))).all()
    needle = said.lower()
    best: tuple[int, str] | None = None
    for phrase, grams in rows:
        # Stored as "1 katori"; the count is already parsed off the front.
        word = re.sub(r"^\d+\s*", "", phrase.lower()).strip()
        core = re.split(r"\s*\(", word)[0].strip()
        for form in {word, core}:
            if form and needle.startswith(form) and (best is None or len(form) > len(best[1])):
                best = (grams, form)
    if best is None:
        return None, said
    rest = JOIN.sub("", said[len(best[1]):].strip())
    return best[0], rest.strip()


async def resolve_one(session: AsyncSession, user: str, said: str) -> dict:
    """One item against the pool. Dishes first, then foods — *dal* is a dish
    you eat, and only falls back to the raw food when no dish matches."""
    needle = said.lower().strip()
    row = (await session.execute(text("""
        WITH hit AS (
            SELECT id, name, 'dish' AS kind, 1 AS rung, 1.0 AS score
            FROM dishes
            WHERE deleted_at IS NULL AND (visibility = 'public' OR created_by_id = :u)
              AND lower(name) = :n
            UNION ALL
            SELECT id, name, 'dish', 2, 0.95 FROM dishes
            WHERE deleted_at IS NULL AND (visibility = 'public' OR created_by_id = :u)
              AND EXISTS (SELECT 1 FROM unnest(aliases) a WHERE lower(a) = :n)
            UNION ALL
            SELECT id, name, 'food', 1, 1.0 FROM foods
            WHERE deleted_at IS NULL AND lower(name) = :n
            UNION ALL
            SELECT id, name, 'food', 2, 0.95 FROM foods
            WHERE deleted_at IS NULL
              AND EXISTS (SELECT 1 FROM unnest(aliases) a WHERE lower(a) = :n)
            UNION ALL
            SELECT id, name, 'dish', 3, similarity(lower(name), :n) FROM dishes
            WHERE deleted_at IS NULL AND (visibility = 'public' OR created_by_id = :u)
              AND similarity(lower(name), :n) >= :floor
            UNION ALL
            SELECT id, name, 'food', 3, similarity(lower(name), :n) FROM foods
            WHERE deleted_at IS NULL AND similarity(lower(name), :n) >= :floor
        )
        SELECT * FROM hit ORDER BY rung, score DESC LIMIT 1
    """), {"u": user, "n": needle, "floor": TRIGRAM_FLOOR})).first()

    if row is None:
        # Rung 5. Deliberately not a guess — the card shows the gap.
        return {"said": said, "matched": False, "name": None, "dish_id": None,
                "food_id": None, "confidence": 0.0, "rung": "unresolved"}
    return {
        "said": said, "matched": True, "name": row.name,
        "dish_id": row.id if row.kind == "dish" else None,
        "food_id": row.id if row.kind == "food" else None,
        "confidence": round(float(row.score), 2),
        "rung": {1: "exact", 2: "alias", 3: "similar"}[row.rung],
    }


async def resolve(session: AsyncSession, user: str, said: str) -> list[dict]:
    """The whole sentence. Every line comes back, matched or not — nothing is
    dropped for being unrecognised, and nothing is invented to fill a gap.

    The quantity rules, which are where a wrong number would come from:

    * a **dish** takes the count as servings — *2 omelette* is two of them;
    * a **food with a spoken measure** takes count × the measure's grams —
      *2 katori dal* is 300 g;
    * a **food sold in pieces** takes the count directly — *3 ande*;
    * a **food weighed in grams with no measure** takes **nothing**. *2 roti*
      is not two grams of atta, and guessing forty would be inventing a number
      the user never said. The line is marked `needs_quantity` and the card
      asks — `diet-logging.md` §1: flag rather than silently guess.
    """
    lines = []
    for part, qty in split_items(said):
        grams, rest = (await measure_in(session, part)) if qty else (None, part)
        line = await resolve_one(session, user, rest or part)
        line["said"] = part
        line["servings"] = qty if line["dish_id"] else None
        line["quantity"] = None
        line["needs_quantity"] = False
        if line["food_id"] and qty:
            food = (await session.execute(text(
                "SELECT unit, grams_per_unit FROM foods WHERE id = :i"),
                {"i": line["food_id"]})).first()
            if grams is not None:
                line["quantity"] = int(qty * grams)
            elif food and (food.unit != "g" or food.grams_per_unit):
                line["quantity"] = int(qty)
            else:
                line["needs_quantity"] = True
        lines.append(line)
    return lines
