"""
GET /paisa/summary — the derived set, by name. spec/in-progress/agent-tools.md.

This is `paisa_report` over HTTP. The deck stays rows-only; the numbers the
Paisa card shows come from here, computed once in `app/paisa_summary.py`, so the
card, the report and the agent read the same figure.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.auth import CurrentUser
from app.db import SessionDep
from app.paisa_summary import FIELDS, ROWS_CAP, paisa_summary
from app.schemas.summary import PaisaSummaryOut

router = APIRouter(tags=["summary"])


# exclude_none: a field the caller did not name is absent from the JSON, not
# null — so nothing can be read off it, and the model spends no tokens on it.
@router.get("/paisa/summary", response_model_by_alias=True, response_model_exclude_none=True)
async def summary(
    session: SessionDep,
    user: CurrentUser,
    to: Annotated[date, Query()],
    fields: Annotated[str, Query(description="comma-separated: " + ", ".join(sorted(FIELDS)))],
    since: Annotated[date | None, Query(alias="from")] = None,
    category: Annotated[str | None, Query()] = None,
    counterparty_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=ROWS_CAP)] = ROWS_CAP,
    after: Annotated[str | None, Query()] = None,
) -> PaisaSummaryOut:
    """`from` defaults to the first of `to`'s month — the pool is the month."""
    frm = since or to.replace(day=1)
    if frm > to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "from is after to")
    wanted = {f.strip() for f in fields.split(",") if f.strip()}
    if not wanted:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "name at least one field")
    try:
        out = await paisa_summary(session, user, frm, to, wanted, category=category,
                                  counterparty_id=counterparty_id, rows_limit=limit,
                                  after=after)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    out["from_"] = out.pop("from")
    return PaisaSummaryOut.model_validate(out)
