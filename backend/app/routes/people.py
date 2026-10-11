"""
Who you pay, and what the ledger knows about them.
spec/in-progress/people.md.

A counterparty was only a match key — a name to recognise the next payment by.
This gives it the three things the key could never hold (`kind`, `relation`,
`note`) and reads the rest straight out of the ledger, per request.

Nothing here is stored twice. Sent, received, what is still out and how long
they usually take are arithmetic over `transactions`; delete a repayment and
every one of them corrects itself with no write.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select, text

from app.auth import CurrentUser
from app.db import SessionDep
from app.models.paisa import Counterparty
from app.routes.writes import apply, existing, live_or_404
from app.schemas.people import CounterpartyIn, CounterpartyPatch, PersonOut

router = APIRouter(tags=["people"])

# One statement, because every number is a different slice of the same rows.
#
# `lend` settles each loan against the repayments pointing at it, which is the
# only correct way round: a repayment carries the counterparty it inherited,
# so summing credits per person would count a repayment as money they gave you.
# `first_repaid` is MIN, not MAX — the clock stops when they start paying.
_PEOPLE_SQL = """
WITH tx AS (
    SELECT * FROM transactions WHERE user_id = :u AND deleted_at IS NULL
),
loans AS (
    SELECT l.counterparty_id, l.kind, l.amount_paise, l.local_day,
           COALESCE(SUM(r.amount_paise), 0) AS repaid,
           MIN(r.local_day) AS first_repaid
    FROM tx l
    LEFT JOIN tx r ON r.settles_id = l.id AND r.kind = 'repayment'
    WHERE l.kind IN ('lent', 'borrowed') AND l.counterparty_id IS NOT NULL
    GROUP BY l.id, l.counterparty_id, l.kind, l.amount_paise, l.local_day
),
owed AS (
    SELECT counterparty_id,
           SUM(amount_paise - repaid) FILTER (WHERE kind = 'lent')     AS still_out,
           SUM(amount_paise - repaid) FILTER (WHERE kind = 'borrowed') AS you_owe,
           -- Only settled loans have a gap to average. No repayment, no number.
           AVG(first_repaid - local_day) FILTER (
               WHERE kind = 'lent' AND first_repaid IS NOT NULL) AS days
    FROM loans GROUP BY counterparty_id
)
SELECT cp.id, cp.raw_name, cp.display_name, cp.kind, cp.relation, cp.note,
       cp.source, cp.confirmed_at, cp.is_peer, cp.in_contacts, cp.default_category,
       COALESCE(SUM(t.amount_paise) FILTER (WHERE t.direction = 'debit'), 0)::bigint
           AS sent_paise,
       COALESCE(SUM(t.amount_paise) FILTER (WHERE t.direction = 'credit'), 0)::bigint
           AS received_paise,
       COALESCE(o.still_out, 0)::bigint AS still_out_paise,
       COALESCE(o.you_owe, 0)::bigint   AS you_owe_paise,
       ROUND(o.days)::int               AS typical_days,
       COUNT(t.id)::int                 AS tx_count,
       MAX(t.local_day)                 AS last_day
FROM counterparties cp
LEFT JOIN tx t   ON t.counterparty_id = cp.id
LEFT JOIN owed o ON o.counterparty_id = cp.id
WHERE cp.user_id = :u AND cp.deleted_at IS NULL {extra}
GROUP BY cp.id, cp.raw_name, cp.display_name, cp.kind, cp.relation, cp.note,
         cp.source, cp.confirmed_at, cp.is_peer, cp.in_contacts, cp.default_category,
         o.still_out, o.you_owe, o.days
-- Money outstanding first, then whoever you deal with most.
ORDER BY (COALESCE(o.still_out, 0) + COALESCE(o.you_owe, 0)) DESC,
         COUNT(t.id) DESC, cp.raw_name
"""


async def _people(session, user: str, extra: str = "", **params) -> list[PersonOut]:
    rows = (await session.execute(
        text(_PEOPLE_SQL.format(extra=extra)), {"u": user, **params})).all()
    return [PersonOut(**dict(r._mapping)) for r in rows]


@router.get("/people")
async def people(
    session: SessionDep,
    user: CurrentUser,
    kind: Annotated[str | None, Query(pattern=r"^(person|shop|service|unsorted)$")] = None,
) -> list[PersonOut]:
    """Everyone the ledger has a row for. `?kind=unsorted` is the ones nobody
    has classified — a bucket, never a badge: a shop with no kind breaks
    nothing, so there is no count here to clear."""
    if kind == "unsorted":
        return await _people(session, user, extra="AND cp.kind IS NULL")
    if kind:
        return await _people(session, user, extra="AND cp.kind = :k", k=kind)
    return await _people(session, user)


@router.post("/counterparties", status_code=status.HTTP_201_CREATED)
async def add_counterparty(
    body: CounterpartyIn, session: SessionDep, user: CurrentUser, response: Response
) -> PersonOut:
    """Add someone the ledger has never seen.

    Almost every counterparty is born from a payment instead — that path stays
    the normal one. This is for the person who exists before the money does:
    cash you owe, or a friend you are about to lend to.

    Born confirmed, because the user typed every word of it. The risk is a
    twin: a hand-typed *Wasim* will not match a notification that says
    `MOHD WASIM`, and the two rows have to be merged later — the same merge
    problem `sunny` and `sunnny` already pose.
    """
    row = await existing(session, Counterparty, body.id, user)
    if row is not None:  # replay
        response.status_code = status.HTTP_200_OK
    else:
        # Matches the unique constraint, which does not exclude soft-deleted
        # rows — so this is a clean 409 rather than an IntegrityError.
        clash = await session.scalar(select(Counterparty).where(
            Counterparty.user_id == user, Counterparty.raw_name == body.raw_name))
        if clash is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "this name is already here")
        row = Counterparty(
            id=body.id, user_id=user, raw_name=body.raw_name,
            display_name=body.display_name, kind=body.kind, relation=body.relation,
            note=body.note, default_category=body.default_category,
            source="user", confirmed_at=datetime.now(UTC),
        )
        session.add(row)
    await session.commit()
    return (await _people(session, user, extra="AND cp.id = :id", id=row.id))[0]


@router.patch("/counterparties/{row_id}")
async def patch_counterparty(
    row_id: str, body: CounterpartyPatch, session: SessionDep, user: CurrentUser
) -> PersonOut:
    """The user filing a row. Stamps `source='user'` and `confirmed_at`, which
    is what removes the `· andaaza` mark and stops any later agent pass from
    overwriting it.

    `raw_name` is not here and never will be: it is how the next notification
    finds this row again.
    """
    row = await live_or_404(session, Counterparty, row_id, user)
    if apply(row, body):
        row.source = "user"
        row.confirmed_at = datetime.now(UTC)
    await session.commit()
    found = await _people(session, user, extra="AND cp.id = :id", id=row_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "counterparties: no such row")
    return found[0]
