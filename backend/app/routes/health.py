from fastapi import APIRouter
from sqlalchemy import text

from app.db import SessionDep

router = APIRouter(tags=["health"])


@router.get("/")
async def root() -> dict:
    return {"hello": "spica"}


@router.get("/health")
async def health(session: SessionDep) -> dict:
    """
    Reports what the database can actually do, not just that it answered.
    pgvector missing is the failure that would otherwise surface much later,
    as a confusing error inside `ask`.
    """
    version = (await session.execute(text("SHOW server_version"))).scalar_one()
    rows = (await session.execute(text("SELECT extname FROM pg_extension ORDER BY extname"))).all()
    extensions = [r[0] for r in rows]

    return {
        "status": "ok",
        "postgres": version,
        "extensions": extensions,
        "pgvector": "vector" in extensions,
    }
