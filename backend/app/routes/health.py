from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
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

    # Which model the agent is set to use, and whether its key is there — a
    # yes or no, never the key. A deploy with the provider, the model or the
    # key wrong otherwise shows only as every chat turn failing.
    cfg = settings()
    key = cfg.anthropic_api_key if cfg.llm_provider == "anthropic" else cfg.openai_api_key
    return {
        "status": "ok",
        "postgres": version,
        "extensions": extensions,
        "pgvector": "vector" in extensions,
        "llm": {"provider": cfg.llm_provider, "model": cfg.llm_model, "key_set": bool(key.strip())},
    }
