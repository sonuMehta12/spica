"""
Where the money was spent. spec/in-progress/places.md.

`places` has pointed at nothing since the paisa data model, because it waited
for a location source. It does not have to: the places that matter are known,
not discovered, and a pin dropped by hand is worth as much as one the phone
finds — and is a coordinate and a radius that detection matches against later.

Every number on a pin is counted per request. A place has a ledger under it —
the transactions pointing at it — so deleting a payment corrects the pin with
no write anywhere.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select, text

from app.auth import CurrentUser
from app.db import SessionDep
from app.models.paisa import Counterparty, Place
from app.routes.writes import apply, existing, live_or_404
from app.schemas.places import PlaceIn, PlaceOut, PlacePatch

router = APIRouter(tags=["places"])

# Two ways a payment counts as "here", OR'd: it points at the pin, or it was
# made to the counterparty the pin belongs to. The second is what lets Mohan
# Shyam's shop show its spend with nothing tagged by hand.
_PLACES_SQL = """
WITH tx AS (
    SELECT * FROM transactions WHERE user_id = :u AND deleted_at IS NULL
)
SELECT p.id, p.name, p.kind, p.lat, p.lng, p.radius_m, p.address, p.category,
       p.counterparty_id, c.raw_name AS counterparty_name, p.note, p.source,
       p.confirmed_at,
       COUNT(t.id)::int                                                AS payments,
       COALESCE(SUM(t.amount_paise) FILTER (WHERE t.direction = 'debit'), 0)::bigint
                                                                       AS spent_paise,
       MAX(t.local_day)                                                AS last_seen
FROM places p
LEFT JOIN counterparties c ON c.id = p.counterparty_id
LEFT JOIN tx t
       ON t.place_id = p.id
       OR (p.counterparty_id IS NOT NULL AND t.counterparty_id = p.counterparty_id)
WHERE p.user_id = :u AND p.deleted_at IS NULL {extra}
GROUP BY p.id, p.name, p.kind, p.lat, p.lng, p.radius_m, p.address, p.category,
         p.counterparty_id, c.raw_name, p.note, p.source, p.confirmed_at
ORDER BY COUNT(t.id) DESC, p.name
"""


async def _places(session, user: str, extra: str = "", **params) -> list[PlaceOut]:
    rows = (await session.execute(
        text(_PLACES_SQL.format(extra=extra)), {"u": user, **params})).all()
    return [PlaceOut(**dict(r._mapping)) for r in rows]


@router.get("/places")
async def places(
    session: SessionDep,
    user: CurrentUser,
    kind: Annotated[str | None, Query()] = None,
) -> list[PlaceOut]:
    """Your pins, busiest first."""
    if kind:
        return await _places(session, user, "AND p.kind = :k", k=kind)
    return await _places(session, user)


@router.post("/places", status_code=status.HTTP_201_CREATED)
async def create_place(
    body: PlaceIn, session: SessionDep, user: CurrentUser, response: Response
) -> PlaceOut:
    """A pin you dropped. Confirmed on arrival — you put it there, so there is
    nothing to mark as a guess. Only a `detected` pin waits to be approved."""
    row = await existing(session, Place, body.id, user)
    if row is not None:  # replay
        response.status_code = status.HTTP_200_OK
    else:
        if body.counterparty_id is not None:
            known = await session.scalar(select(Counterparty).where(
                Counterparty.id == body.counterparty_id, Counterparty.user_id == user,
                Counterparty.deleted_at.is_(None)))
            if known is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                    "no such counterparty")
        row = Place(
            **body.model_dump(), user_id=user,
            confirmed_at=None if body.source == "detected" else datetime.now(UTC),
        )
        session.add(row)
        await session.commit()
    return (await _places(session, user, "AND p.id = :id", id=row.id))[0]


@router.patch("/places/{row_id}")
async def patch_place(
    row_id: str, body: PlacePatch, session: SessionDep, user: CurrentUser
) -> PlaceOut:
    """Move it, rename it, file it, link it. Any edit is the user speaking, so
    it confirms a detected pin and the `· andaaza` mark goes."""
    row = await live_or_404(session, Place, row_id, user)
    if body.counterparty_id is not None:
        known = await session.scalar(select(Counterparty).where(
            Counterparty.id == body.counterparty_id, Counterparty.user_id == user,
            Counterparty.deleted_at.is_(None)))
        if known is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "no such counterparty")
    if apply(row, body):
        row.confirmed_at = datetime.now(UTC)
    await session.commit()
    return (await _places(session, user, "AND p.id = :id", id=row_id))[0]


@router.delete("/places/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_place(row_id: str, session: SessionDep, user: CurrentUser) -> None:
    """Soft. Payments keep their `place_id` — that the money moved there is
    still true; the pin just stops being one of yours."""
    row = await live_or_404(session, Place, row_id, user)
    row.deleted_at = datetime.now(UTC)
    await session.commit()
