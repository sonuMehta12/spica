from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import mcp_server
from app.config import settings
from app.db import engine
from app.routes import (
    auth,
    chat,
    commitments,
    deck,
    dishes,
    habits,
    health,
    nudges,
    oauth,
    onboarding,
    pantry,
    people,
    places,
    plan,
    projects,
    schedules,
    summary,
    users,
    workouts,
    writes,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # A mounted app's own lifespan never runs, so the MCP server's session
    # manager is started here, for the life of the process.
    async with mcp_server.server.session_manager.run():
        yield
    await engine.dispose()


app = FastAPI(
    title="Spica",
    version="0.1.0",
    description=(
        "Rows and intelligence, never views — the client computes. "
        "See spec/api.md for why."
    ),
    lifespan=lifespan,
)

# The prototype runs on a different origin in dev, so the browser needs this.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings().cors_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(onboarding.router)
app.include_router(deck.router)
app.include_router(habits.router)
app.include_router(schedules.router)
app.include_router(nudges.router)
app.include_router(commitments.router)
app.include_router(writes.router)
app.include_router(users.router)
app.include_router(pantry.router)
app.include_router(dishes.router)
app.include_router(people.router)
app.include_router(places.router)
app.include_router(summary.router)
app.include_router(workouts.router)
app.include_router(oauth.router)
app.include_router(projects.router)
app.include_router(plan.router)

# Last, and at the root: the MCP server and the OAuth routes the SDK owns
# (`/mcp`, `/authorize`, `/token`, `/register`, `/revoke`, `/.well-known/…`).
# Everything above is matched first; this answers only what they do not.
# spec/work-sync.md § The MCP server.
app.mount("/", mcp_server.app)
