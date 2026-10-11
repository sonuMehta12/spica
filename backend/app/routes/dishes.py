"""
Dishes — what you eat, described once. spec/in-progress/dishes.md.

The pool is global; your library is your slice of it. Two relationships, and
only one of them is stored: **saved** is a bookmark row, **tried** is counted
from the ledger's meal lines. Derive the measurement, store the declaration —
the same rule the pantry settled on.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import Integer, func, or_, select

from app.auth import CurrentUser
from app.db import SessionDep
from app.models.diet import Dish, DishItem, DishSave, Food, MealItem, MealLog
from app.routes.writes import apply
from app.schemas.dishes import DishIn, DishItemOut, DishOut, DishPatch

router = APIRouter(tags=["dishes"])


async def _rows(session, user: str, *, mine_only: bool, q: str | None, with_items: bool):
    """Dishes with this user's saved flag and tried count attached.

    The count is a correlated subquery over meal_items joined to the user's own
    meals — a dish is tried if it appears on any of your bills, even one where
    it shared the plate with two other things.
    """
    tried = (
        select(func.count().cast(Integer))
        .select_from(MealItem)
        .join(MealLog, MealLog.id == MealItem.meal_log_id)
        .where(MealItem.dish_id == Dish.id, MealItem.deleted_at.is_(None),
               MealLog.user_id == user, MealLog.deleted_at.is_(None))
        .correlate(Dish).scalar_subquery()
    )
    last = (
        select(func.max(MealLog.local_day))
        .select_from(MealItem)
        .join(MealLog, MealLog.id == MealItem.meal_log_id)
        .where(MealItem.dish_id == Dish.id, MealItem.deleted_at.is_(None),
               MealLog.user_id == user, MealLog.deleted_at.is_(None))
        .correlate(Dish).scalar_subquery()
    )
    saved = (
        select(DishSave.id).where(
            DishSave.dish_id == Dish.id, DishSave.user_id == user,
            DishSave.deleted_at.is_(None))
        .correlate(Dish).exists()
    )

    stmt = (
        select(Dish, saved.label("saved"), tried.label("tried"), last.label("last_tried"))
        .where(Dish.deleted_at.is_(None))
        .order_by(Dish.name)
    )
    if mine_only:
        # Your library: what you saved, or what you have actually eaten.
        stmt = stmt.where(or_(saved, tried > 0))
    else:
        # The pool: everything public, plus your own private ones.
        stmt = stmt.where(or_(Dish.visibility == "public", Dish.created_by_id == user))
    if q:
        stmt = stmt.where(or_(Dish.name.ilike(f"%{q}%"), Dish.aliases.any(q.lower())))

    found = (await session.execute(stmt)).all()
    items: dict[str, list[DishItemOut]] = {}
    if with_items and found:
        # Every dish's lines, once — components are resolved from this same map
        # rather than a query per level.
        all_items: dict[str, list] = {}
        names: dict[str, str] = {}
        for it, food_name, unit in (await session.execute(
            select(DishItem, Food.name, Food.unit)
            .outerjoin(Food, Food.id == DishItem.food_id)
            .where(DishItem.deleted_at.is_(None))
        )).all():
            all_items.setdefault(it.dish_id, []).append(it)
            if food_name:
                names[it.food_id] = (food_name, unit)

        def flatten(dish_id: str, servings: float = 1.0, depth: int = 0) -> list[DishItemOut]:
            """The foods a dish really needs, with component dishes expanded.

            Ghar ka dinner is roti-sabzi plus dal; without this the atta and the
            sabzi were never checked and the dish claimed to be cookable on the
            strength of the dal alone.
            """
            if depth > 5:  # a dish that contains itself is a data error
                return []
            out: list[DishItemOut] = []
            for it in all_items.get(dish_id, []):
                if it.component_dish_id:
                    out += flatten(it.component_dish_id, float(it.servings) * servings, depth + 1)
                else:
                    out.append(DishItemOut(
                        id=it.id, food_id=it.food_id,
                        food_name=(names.get(it.food_id) or (None, 'g'))[0],
                        unit=(names.get(it.food_id) or (None, 'g'))[1],
                        component_dish_id=None,
                        quantity=round(it.quantity * servings) if it.quantity else None,
                        servings=it.servings, note=it.note,
                        from_dish=dish_id if depth else None,
                    ))
            return out

        for r in found:
            items[r[0].id] = flatten(r[0].id)
    return [
        DishOut(
            **{c: getattr(d, c) for c in (
                "id", "name", "aliases", "meal_type", "serving_label", "kcal", "protein_g",
                "carbs_g", "fat_g", "fibre_g", "minutes", "needs_prep_ahead", "steps",
                "image_url", "tags", "note")},
            mine=d.created_by_id == user,
            saved=is_saved, tried=n, last_tried=when,
            items=items.get(d.id, []),
        )
        for d, is_saved, n, when in found
    ]


@router.get("/dishes")
async def dishes(
    session: SessionDep,
    user: CurrentUser,
    mine: bool = True,
    q: str | None = Query(default=None, description="name or alias contains"),
    items: bool = True,
) -> list[DishOut]:
    """`mine=true` (the default) is your library — saved or tried. `mine=false`
    is the pool, for searching before you save something."""
    return await _rows(session, user, mine_only=mine, q=q, with_items=items)


@router.post("/dishes", status_code=status.HTTP_201_CREATED)
async def create_dish(
    body: DishIn, session: SessionDep, user: CurrentUser, response: Response
) -> DishOut:
    """Deliberate, always — nothing creates a dish as a side effect of logging."""
    found = await session.scalar(select(Dish).where(Dish.id == body.id))
    if found is not None:
        response.status_code = status.HTTP_200_OK
    else:
        session.add(Dish(**body.model_dump(), created_by_id=user))
        await session.commit()
    rows = await _rows(session, user, mine_only=False, q=None, with_items=True)
    return next(r for r in rows if r.id == body.id)


@router.patch("/dishes/{dish_id}")
async def patch_dish(
    dish_id: str, body: DishPatch, session: SessionDep, user: CurrentUser
) -> DishOut:
    """Only your own. Changing someone else's means forking it."""
    row = await session.scalar(select(Dish).where(Dish.id == dish_id, Dish.deleted_at.is_(None)))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such dish")
    if row.created_by_id != user:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not yours — fork it to change it")
    apply(row, body)
    await session.commit()
    rows = await _rows(session, user, mine_only=False, q=None, with_items=True)
    return next(r for r in rows if r.id == dish_id)


@router.put("/dishes/{dish_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def save_dish(dish_id: str, session: SessionDep, user: CurrentUser) -> None:
    """Star it. Idempotent: saving twice is one row."""
    dish = await session.scalar(select(Dish).where(Dish.id == dish_id, Dish.deleted_at.is_(None)))
    if dish is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such dish")
    found = await session.scalar(select(DishSave).where(
        DishSave.user_id == user, DishSave.dish_id == dish_id, DishSave.deleted_at.is_(None)))
    if found is None:
        session.add(DishSave(user_id=user, dish_id=dish_id))
        await session.commit()


@router.delete("/dishes/{dish_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_dish(dish_id: str, session: SessionDep, user: CurrentUser) -> None:
    """Unstar. History survives — a dish you have eaten stays in the library as
    tried."""
    found = await session.scalar(select(DishSave).where(
        DishSave.user_id == user, DishSave.dish_id == dish_id, DishSave.deleted_at.is_(None)))
    if found is not None:
        found.deleted_at = datetime.now(UTC)
        await session.commit()


@router.delete("/dishes/{dish_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dish(dish_id: str, session: SessionDep, user: CurrentUser) -> None:
    """Only your own, and only if nothing points at it."""
    row = await session.scalar(select(Dish).where(Dish.id == dish_id, Dish.deleted_at.is_(None)))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such dish")
    if row.created_by_id != user:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not yours")
    used = await session.scalar(select(func.count()).select_from(MealItem).where(
        MealItem.dish_id == dish_id, MealItem.deleted_at.is_(None)))
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"eaten {used} time{'s' if used > 1 else ''} — unstar it instead of deleting",
        )
    row.deleted_at = datetime.now(UTC)
    await session.commit()
