"""
The pantry: what this house tracks, and every change to it.
spec/in-progress/pantry-view.md.

Two tables, two questions. `pantry` is *what I track and when do I re-buy it*;
`pantry_moves` is *how it got that way*. The stock is the SUM of the moves and
is never stored — delete a meal and its ingredients come back on their own.

Status words are not computed here. The server sends the numbers that decide
them (stock, the last inbound move, how many inbound moves exist at all) and
the client picks the word, because words are UI.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select, text

from app.auth import CurrentUser
from app.db import SessionDep
from app.models.diet import Food, MealLog, PantryItem, PantryMove
from app.routes.writes import apply, existing, live_or_404
from app.schemas.pantry import (
    PantryItemIn,
    PantryItemOut,
    PantryItemPatch,
    PantryMoveRow,
)

router = APIRouter(tags=["pantry"])

INBOUND = ("purchase", "opening")


@router.get("/pantry")
async def pantry(session: SessionDep, user: CurrentUser) -> list[PantryItemOut]:
    """
    Every tracked food with the numbers the status ladder needs.

    Stock counts from the last **stock-take**: an `opening` move is an
    observation — *I looked, there are 18* — so everything before it is history,
    not arithmetic (spec/done/diet-data-model.md). Summing across one would make
    a stock-take mean nothing, which is what it did until 2026-09-04.
    """
    rows = (await session.execute(text("""
        WITH last_take AS (
            SELECT DISTINCT ON (food_id) food_id, local_day, id
            FROM pantry_moves
            WHERE user_id = :u AND deleted_at IS NULL AND kind = 'opening'
            ORDER BY food_id, local_day DESC, id DESC
        )
        SELECT p.id, p.food_id, f.name, f.unit, p.reorder_at_g, p.shelf_life_days,
               p.note, p.staple,
               COALESCE(SUM(m.quantity), 0)::int AS stock_g,
               COUNT(*) FILTER (WHERE m.kind IN ('purchase','opening'))::int AS inbound,
               MAX(m.local_day) FILTER (WHERE m.kind IN ('purchase','opening')) AS last_in,
               (ARRAY_AGG(m.quantity ORDER BY m.local_day DESC, m.id DESC)
                FILTER (WHERE m.kind IN ('purchase','opening')))[1] AS last_in_g
        FROM pantry p
        JOIN foods f ON f.id = p.food_id
        LEFT JOIN last_take t ON t.food_id = p.food_id
        LEFT JOIN pantry_moves m
               ON m.food_id = p.food_id AND m.user_id = p.user_id AND m.deleted_at IS NULL
              -- at or after the last stock-take, or everything when there is none
              AND (t.food_id IS NULL OR (m.local_day, m.id) >= (t.local_day, t.id))
        WHERE p.user_id = :u AND p.deleted_at IS NULL
        GROUP BY p.id, p.food_id, f.name, f.unit, p.reorder_at_g, p.shelf_life_days,
                 p.note, p.staple
        ORDER BY f.name
    """), {"u": user})).all()
    return [PantryItemOut(**dict(r._mapping)) for r in rows]


async def resolve_food(session, name: str, unit: str = "g") -> str:
    """An existing food by name or alias, or a new one with no nutrition.

    Unknown nutrition stays NULL — there is no `origin` column and no zero to
    write. A zero here would be a fabricated number, and the whole pantry
    exists to avoid confident wrong figures.
    """
    clean = name.strip()
    found = await session.scalar(
        select(Food).where(
            Food.deleted_at.is_(None),
            or_(func.lower(Food.name) == clean.lower(), Food.aliases.any(clean.lower())),
        ).limit(1)
    )
    if found is not None:
        return found.id
    food = Food(name=clean, unit=unit)
    session.add(food)
    await session.flush()
    return food.id


@router.post("/pantry", status_code=status.HTTP_201_CREATED)
async def track_food(
    body: PantryItemIn, session: SessionDep, user: CurrentUser, response: Response
) -> PantryItemOut:
    """Start tracking a food. The opening stock, if any, is a separate move —
    so a failed second call leaves a tracked food, never a phantom quantity."""
    found = await existing(session, PantryItem, body.id, user)
    if found is not None:  # replay
        response.status_code = status.HTTP_200_OK
        row = found
    else:
        food_id = body.food_id or await resolve_food(session, body.food_name or "", body.unit)
        if not food_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "a food name or id is needed")
        clash = await session.scalar(select(PantryItem).where(
            PantryItem.user_id == user, PantryItem.food_id == food_id,
            PantryItem.deleted_at.is_(None)))
        if clash is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "this food is already tracked")
        row = PantryItem(id=body.id, user_id=user, food_id=food_id, staple=body.staple,
                         reorder_at_g=body.reorder_at_g, shelf_life_days=body.shelf_life_days,
                         note=body.note)
        session.add(row)
    await session.commit()
    name, unit = (await session.execute(
        select(Food.name, Food.unit).where(Food.id == row.food_id))).one()
    return PantryItemOut(
        id=row.id, food_id=row.food_id, name=name or "", reorder_at_g=row.reorder_at_g,
        shelf_life_days=row.shelf_life_days, note=row.note, staple=row.staple, unit=unit or "g",
        stock_g=0, inbound=0, last_in=None, last_in_g=None,
    )


@router.patch("/pantry/{row_id}")
async def patch_pantry(
    row_id: str, body: PantryItemPatch, session: SessionDep, user: CurrentUser
) -> PantryItemOut:
    """Reorder level, shelf life, note. Never a quantity: that is a move."""
    row = await live_or_404(session, PantryItem, row_id, user)
    apply(row, body)
    await session.commit()
    name, unit = (await session.execute(
        select(Food.name, Food.unit).where(Food.id == row.food_id))).one()
    stock = await session.scalar(
        select(func.coalesce(func.sum(PantryMove.quantity), 0)).where(
            PantryMove.user_id == user, PantryMove.food_id == row.food_id,
            PantryMove.deleted_at.is_(None))
    )
    return PantryItemOut(
        id=row.id, food_id=row.food_id, name=name or "", reorder_at_g=row.reorder_at_g,
        shelf_life_days=row.shelf_life_days, note=row.note, staple=row.staple, unit=unit or "g",
        stock_g=int(stock or 0), inbound=0, last_in=None, last_in_g=None,
    )


@router.delete("/pantry/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def stop_tracking(row_id: str, session: SessionDep, user: CurrentUser) -> None:
    """Stop tracking. The moves stay — that this food was once here is true."""
    row = await live_or_404(session, PantryItem, row_id, user)
    row.deleted_at = datetime.now(UTC)
    await session.commit()


@router.get("/pantry-moves")
async def pantry_moves(
    session: SessionDep,
    user: CurrentUser,
    food_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[PantryMoveRow]:
    """The ledger, newest first, each line carrying the meal that caused it."""
    clauses = [PantryMove.user_id == user, PantryMove.deleted_at.is_(None)]
    if food_id:
        clauses.append(PantryMove.food_id == food_id)
    rows = (await session.execute(
        select(PantryMove.id, PantryMove.food_id, Food.name, PantryMove.local_day,
               PantryMove.quantity, PantryMove.kind, PantryMove.note, Food.unit,
               MealLog.dish.label("dish"))
        .join(Food, Food.id == PantryMove.food_id)
        .outerjoin(MealLog, MealLog.id == PantryMove.meal_log_id)
        .where(*clauses)
        .order_by(PantryMove.local_day.desc(), PantryMove.id.desc())
        .limit(limit)
    )).all()
    return [PantryMoveRow(**dict(r._mapping)) for r in rows]
