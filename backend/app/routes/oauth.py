"""
The person's answer to an OAuth request. spec/work-sync.md § Auth.

`/authorize` (the SDK's) parks the request and sends the browser to the app's
`/connect` page. The app is where the person is already signed in, so these
routes take the app's own session: approving a client is something only the
signed-in person can do, and a registered client alone gets nothing.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app import oauth
from app.auth import CurrentUser
from app.db import SessionDep
from app.models.oauth import OAuthClient

router = APIRouter(tags=["oauth"])

GONE = HTTPException(status.HTTP_404_NOT_FOUND,
                     "this request has expired or was already answered — start again from Claude")


class RequestOut(BaseModel):
    client_name: str
    redirect_host: str
    scopes: list[str]


class AnswerOut(BaseModel):
    redirect: str


@router.get("/oauth/requests/{request}")
async def read_request(request: str, session: SessionDep, _: CurrentUser) -> RequestOut:
    """What the consent page shows: who is asking, and where the answer goes."""
    from urllib.parse import urlparse

    row = await oauth.pending(session, request)
    if row is None:
        raise GONE
    client = await session.scalar(select(OAuthClient).where(
        OAuthClient.client_id == row.client_id))
    return RequestOut(client_name=(client.name if client and client.name else "An app"),
                      redirect_host=urlparse(row.redirect_uri).netloc or row.redirect_uri,
                      scopes=row.scopes)


@router.post("/oauth/requests/{request}/approve")
async def approve(request: str, session: SessionDep, user: CurrentUser) -> AnswerOut:
    row = await oauth.pending(session, request)
    if row is None:
        raise GONE
    return AnswerOut(redirect=await oauth.approve(session, row, user))


@router.post("/oauth/requests/{request}/deny")
async def deny(request: str, session: SessionDep, _: CurrentUser) -> AnswerOut:
    row = await oauth.pending(session, request)
    if row is None:
        raise GONE
    return AnswerOut(redirect=await oauth.deny(session, row))
