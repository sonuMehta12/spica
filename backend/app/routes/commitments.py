"""
What you still owe, and the verbs to change it. spec/done/commitments.md.

The list reads `paisa_summary` — the same function the limit and the agent read
— so the page, the Money widget and a chat answer cannot disagree. The writes
are small: make, change, skip, delete. There is no *mark as paid*: a payment is
logged (and links itself), or the line is skipped; hand-settling would leave
money in the pool that has actually left.
"""

import calendar
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app import commitments as K
from app.auth import CurrentUser
from app.db import SessionDep
from app.models.commitments import Commitment
from app.models.paisa import Transaction
from app.paisa_summary import paisa_summary
from app.routes.writes import existing, live_or_404, now
from app.schemas.commitments import CommitmentIn, CommitmentPatch, CommitmentsPageOut
from app.schemas.summary import CommitmentOut

router = APIRouter(tags=["commitments"])


def _editable(c: Commitment) -> None:
    """Past months are what was recorded, and are read-only."""
    if c.local_month < K.month_of(K.today_local()):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "past months are read-only — a commitment can be changed this month")


async def _item(session, user: str, row_id: str) -> CommitmentOut:
    """One line as the page shows it, so a write answers with the new owed."""
    month = (await session.get(Commitment, row_id)).local_month
    page = await _page(session, user, month)
    for it in page.items:
        if it.id == row_id:
            return it
    raise HTTPException(status.HTTP_404_NOT_FOUND, "commitments: no such row")


async def _page(session, user: str, month: date) -> CommitmentsPageOut:
    month = K.month_of(month)
    current = K.month_of(K.today_local())
    to = K.today_local() if month == current else month.replace(
        day=calendar.monthrange(month.year, month.month)[1])
    data = await paisa_summary(session, user, month, to, {"commitments", "limit_today"})
    lim, com = data["limit_today"], data["commitments"]
    own = [i for i in com["items"] if i["source"] == "commitment"]
    live = [i for i in own if not i["skipped"]]
    return CommitmentsPageOut(
        month=month, editable=month == current, owed_paise=com["owed_paise"],
        pool_paise=lim["pool_paise"], savings_target_paise=lim["savings_target_paise"],
        limit_paise=lim["limit_paise"], days_left=lim["days_left"],
        paid_count=sum(1 for i in live if i["settled"]), open_count=len(live),
        items=com["items"])


@router.get("/commitments", response_model=CommitmentsPageOut)
async def list_commitments(
    session: SessionDep, user: CurrentUser,
    month: Annotated[date | None, Query(description="any day in the month")] = None,
):
    """The month's commitments, then borrowings worked out live. The current
    month is rolled forward first, once."""
    current = K.month_of(K.today_local())
    month = K.month_of(month) if month else current
    if month > current:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "a future month has no commitments yet")
    page = await _page(session, user, month)
    await session.commit()          # rolling wrote rows
    return page


@router.post("/commitments", response_model=CommitmentOut, status_code=status.HTTP_201_CREATED)
async def create_commitment(body: CommitmentIn, session: SessionDep, user: CurrentUser,
                            response: Response):
    """Make one, for this month. A name already in use is allowed — two loans can
    both be called EMI — but the same id again is a replay."""
    found = await existing(session, Commitment, body.id, user)
    if found is not None:
        response.status_code = status.HTTP_200_OK
        return await _item(session, user, found.id)
    row = Commitment(
        id=body.id, user_id=user, name=body.name.strip(), category=body.category.strip(),
        amount_paise=body.amount_paise, amount_source="stated",
        local_month=K.month_of(K.today_local()), due_day=body.due_day, repeats=body.repeats)
    session.add(row)
    await session.flush()
    for tx_id in body.link_transaction_ids:
        tx = await existing(session, Transaction, tx_id, user)
        if tx is None or tx.deleted_at is not None or tx.kind != "expense":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"no payment with id {tx_id!r} to link")
        tx.commitment_id = row.id
        tx.commitment_inferred = False
    await session.commit()
    return await _item(session, user, row.id)


@router.patch("/commitments/{row_id}", response_model=CommitmentOut)
async def patch_commitment(row_id: str, body: CommitmentPatch, session: SessionDep,
                           user: CurrentUser):
    row = await live_or_404(session, Commitment, row_id, user)
    _editable(row)
    changes = body.model_dump(exclude_unset=True)
    skipped = changes.pop("skipped", None)
    for key, value in changes.items():
        if value is None and key != "due_day":
            continue                      # a name or an amount cannot be cleared
        setattr(row, key, value)
    if "amount_paise" in changes and changes["amount_paise"] is not None:
        row.amount_source = "stated"      # the user said it: no longer a guess
    if skipped is not None:
        row.skipped_at = now() if skipped else None
    await session.commit()
    return await _item(session, user, row.id)


@router.delete("/commitments/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_commitment(row_id: str, session: SessionDep, user: CurrentUser):
    """Soft delete. Its payments become ordinary spending again; the ledger is
    never touched. Deleting ends a repeating line — it will not roll next
    month; *skip* is how to leave only this month out."""
    row = await live_or_404(session, Commitment, row_id, user)
    _editable(row)
    await K.unlink_payments(session, row.id)
    row.deleted_at = now()
    await session.commit()
