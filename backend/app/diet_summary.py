"""
The diet numbers, computed once, on the server.

`paisa_summary`'s twin: only the fields the caller names, each one the same
figure the Diet card shows, so the agent and the screen cannot disagree.

The one rule that matters here is the averages' denominator: **logged days, not
days in range.** Sixteen August was a fast, not a zero-calorie day, and dividing
by calendar days would quietly report a diet nobody ate. Unknown is null with
its count beside it. spec/agent-tools.md § diet_report.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diet import Day, Habit, HabitLog, MealLog
from app.models.users import User, WeighIn

FIELDS = frozenset({
    "avg_protein_g", "avg_kcal", "logged_days", "days_in_range",
    "protein_hit_days", "kcal_in_band_days", "today", "by_day", "by_meal_type",
    "top_dishes", "sleep", "weight", "habits_week", "pantry", "rows",
})
ROWS_CAP = 30
#: Calories count as "in band" within this fraction of the target either way —
#: the Diet card's own ring, so the number the agent quotes is the ring's.
KCAL_BAND = 0.10


def _f(x) -> float:
    return float(x) if isinstance(x, Decimal) else (x or 0)


async def _meals(session, user: str, lo: date, hi: date) -> list[MealLog]:
    return list((await session.scalars(
        select(MealLog).where(
            MealLog.user_id == user, MealLog.deleted_at.is_(None),
            MealLog.local_day >= lo, MealLog.local_day <= hi,
        ).order_by(MealLog.local_day, MealLog.id)
    )).all())


async def diet_summary(session: AsyncSession, user: str, frm: date, to: date,
                       fields: set[str], *, meal_type: str | None = None,
                       rows_limit: int = ROWS_CAP, after: str | None = None) -> dict:
    unknown = fields - FIELDS
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")

    meals = await _meals(session, user, frm, to)
    if meal_type:
        needle = meal_type.strip().lower()
        meals = [m for m in meals if m.meal_type.lower() == needle]
    profile = await session.get(User, user)
    out: dict = {"from": frm, "to": to}
    days_in_range = (to - frm).days + 1

    by_day_p: dict[date, float] = defaultdict(float)
    by_day_k: dict[date, int] = defaultdict(int)
    by_day_n: dict[date, int] = defaultdict(int)
    for m in meals:
        by_day_p[m.local_day] += _f(m.protein_g)
        by_day_k[m.local_day] += m.kcal or 0
        by_day_n[m.local_day] += 1
    logged = sorted(by_day_p)

    if "days_in_range" in fields:
        out["days_in_range"] = days_in_range
    if "logged_days" in fields:
        out["logged_days"] = len(logged)
    # Averaged over days that were logged. A day with no meals is unreported,
    # not a zero — dividing by calendar days invents a diet nobody ate.
    if "avg_protein_g" in fields:
        out["avg_protein_g"] = round(sum(by_day_p.values()) / len(logged), 1) if logged else None
    if "avg_kcal" in fields:
        out["avg_kcal"] = round(sum(by_day_k.values()) / len(logged)) if logged else None
    if "protein_hit_days" in fields:
        t = _f(profile.protein_g_target) if profile and profile.protein_g_target else None
        out["protein_hit_days"] = (
            sum(1 for d in logged if by_day_p[d] >= t) if t else None)
    if "kcal_in_band_days" in fields:
        t = profile.kcal_target if profile else None
        out["kcal_in_band_days"] = (
            sum(1 for d in logged if abs(by_day_k[d] - t) <= t * KCAL_BAND) if t else None)
    if "by_day" in fields:
        out["by_day"] = [
            {"local_day": d, "protein_g": round(by_day_p[d], 1), "kcal": by_day_k[d],
             "meals": by_day_n[d]} for d in logged
        ]
    if "by_meal_type" in fields:
        slots: dict[str, list[float]] = defaultdict(list)
        cals: dict[str, list[int]] = defaultdict(list)
        for m in meals:
            slots[m.meal_type].append(_f(m.protein_g))
            cals[m.meal_type].append(m.kcal or 0)
        out["by_meal_type"] = [
            {"meal_type": s, "n": len(v), "avg_protein_g": round(sum(v) / len(v), 1),
             "avg_kcal": round(sum(cals[s]) / len(cals[s]))}
            for s, v in sorted(slots.items(), key=lambda kv: -len(kv[1]))
        ]
    if "top_dishes" in fields:
        counts: dict[str, int] = defaultdict(int)
        for m in meals:
            counts[m.dish] += 1
        out["top_dishes"] = [{"name": n, "times": c} for n, c in
                             sorted(counts.items(), key=lambda kv: -kv[1])[:15]]

    if "today" in fields:
        # Only meaningful when the range ends today; otherwise "left" is a
        # number about a day that is already over.
        p = round(by_day_p.get(to, 0.0), 1)
        k = by_day_k.get(to, 0)
        pt = _f(profile.protein_g_target) if profile and profile.protein_g_target else None
        kt = profile.kcal_target if profile else None
        out["today"] = {
            "local_day": to, "protein_g": p, "kcal": k, "meals_logged": by_day_n.get(to, 0),
            "protein_left_g": round(max(0.0, pt - p), 1) if pt else None,
            "kcal_left": max(0, kt - k) if kt else None,
        }

    if "sleep" in fields or "weight" in fields:
        days = list((await session.scalars(
            select(Day).where(Day.user_id == user, Day.deleted_at.is_(None),
                              Day.local_day >= frm, Day.local_day <= to)
            .order_by(Day.local_day)
        )).all())
        if "sleep" in fields:
            hrs = [d.sleep_hours for d in days if d.sleep_hours is not None]
            out["sleep"] = {"avg_hours": round(sum(hrs) / len(hrs), 1) if hrs else None,
                            "days_logged": len(hrs)}
        if "weight" in fields:
            latest = await session.scalar(
                select(WeighIn).where(WeighIn.user_id == user, WeighIn.deleted_at.is_(None))
                .order_by(WeighIn.local_day.desc()).limit(1))
            month_ago = await session.scalar(
                select(WeighIn).where(WeighIn.user_id == user, WeighIn.deleted_at.is_(None),
                                      WeighIn.local_day <= to - timedelta(days=30))
                .order_by(WeighIn.local_day.desc()).limit(1))
            out["weight"] = {
                "latest_kg": _f(latest.weight_kg) if latest else None,
                "latest_day": latest.local_day if latest else None,
                # Said as a guess ("around 72"): the reply says so, until an
                # exact reading replaces it.
                "latest_estimated": latest.estimated if latest else None,
                "change_30d": (round(_f(latest.weight_kg) - _f(month_ago.weight_kg), 1)
                               if latest and month_ago else None),
                "target_kg": _f(profile.weight_target_kg) if profile
                and profile.weight_target_kg else None,
            }

    if "habits_week" in fields:
        rows = (await session.execute(
            select(Habit.name, HabitLog.local_day, HabitLog.amount, HabitLog.note)
            .join(HabitLog, HabitLog.habit_id == Habit.id)
            .where(HabitLog.user_id == user, HabitLog.deleted_at.is_(None),
                   Habit.deleted_at.is_(None),
                   HabitLog.local_day >= frm, HabitLog.local_day <= to)
            .order_by(Habit.name, HabitLog.local_day)
        )).all()
        grouped: dict[str, list] = defaultdict(list)
        for name, day, amount, note in rows:
            grouped[name].append({"local_day": day, "amount": amount, "note": note})
        out["habits_week"] = [{"habit": h, "days": v} for h, v in sorted(grouped.items())]

    if "pantry" in fields:
        # The pantry view's own query: stock counts from the last stock-take,
        # so a `opening` move resets the arithmetic rather than adding to it.
        rows = (await session.execute(text("""
            WITH last_take AS (
                SELECT DISTINCT ON (food_id) food_id, local_day, id FROM pantry_moves
                WHERE user_id = :u AND deleted_at IS NULL AND kind = 'opening'
                ORDER BY food_id, local_day DESC, id DESC
            )
            SELECT f.name, f.unit, p.staple, p.reorder_at_g,
                   COALESCE(SUM(m.quantity), 0)::int AS stock,
                   COUNT(*) FILTER (WHERE m.kind IN ('purchase','opening'))::int AS inbound
            FROM pantry p JOIN foods f ON f.id = p.food_id
            LEFT JOIN last_take t ON t.food_id = p.food_id
            LEFT JOIN pantry_moves m ON m.food_id = p.food_id AND m.user_id = p.user_id
                 AND m.deleted_at IS NULL
                 AND (t.food_id IS NULL OR (m.local_day, m.id) >= (t.local_day, t.id))
            WHERE p.user_id = :u AND p.deleted_at IS NULL
            GROUP BY f.name, f.unit, p.staple, p.reorder_at_g ORDER BY f.name
        """), {"u": user})).all()
        out["pantry"] = [
            {"food": r.name, "unit": r.unit, "stock": r.stock,
             # Words the client also uses. `unknown` is not zero: nothing has
             # ever been recorded arriving, so the number means nothing.
             "status": ("staple" if r.staple else "unknown" if not r.inbound
                        else "out" if r.stock <= 0
                        else "soon" if r.reorder_at_g and r.stock <= r.reorder_at_g else "ok")}
            for r in rows
        ]

    if "rows" in fields:
        cap = max(1, min(rows_limit, ROWS_CAP))
        ordered = sorted(meals, key=lambda m: (m.local_day, m.id), reverse=True)
        if after:
            a_day, _, a_id = after.partition("|")
            ordered = [m for m in ordered if (m.local_day.isoformat(), m.id) < (a_day, a_id)]
        page = ordered[:cap]
        items: dict[str, list] = defaultdict(list)
        if page:
            for mi in (await session.execute(text("""
                SELECT i.meal_log_id, i.said, i.servings, i.quantity,
                       COALESCE(d.name, f.name) AS name, i.dish_id, i.food_id
                FROM meal_items i
                LEFT JOIN dishes d ON d.id = i.dish_id
                LEFT JOIN foods f ON f.id = i.food_id
                WHERE i.meal_log_id = ANY(:ids) AND i.deleted_at IS NULL
            """), {"ids": [m.id for m in page]})).all():
                items[mi.meal_log_id].append({
                    "name": mi.name, "said": mi.said, "dish_id": mi.dish_id,
                    "food_id": mi.food_id,
                    "servings": _f(mi.servings) if mi.servings is not None else None,
                    "quantity": mi.quantity,
                })
        out["rows"] = [
            {"id": m.id, "local_day": m.local_day, "meal_type": m.meal_type, "dish": m.dish,
             "kcal": m.kcal, "protein_g": _f(m.protein_g), "carbs_g": _f(m.carbs_g),
             "fat_g": _f(m.fat_g), "note": m.note, "items": items.get(m.id, [])}
            for m in page
        ]
        out["total_matching"] = len(meals)
        if len(ordered) > cap:
            out["next_after"] = f"{page[-1].local_day.isoformat()}|{page[-1].id}"
    return out
