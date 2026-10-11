"""Wire shapes for the conversation. spec/agent.md."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Row


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    #: The user's local day. Only the client knows what day it is where they
    #: are — a server deciding "today" puts an 11:30pm chai on the wrong one.
    local_day: date
    #: And their wall clock, HH:MM:SS. Without it the agent has no idea what
    #: hour it is, cannot tell breakfast from dinner, and stamps every row it
    #: writes at midday.
    local_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}:\d{2}$")


class ActIn(BaseModel):
    """A tap: one tool, its arguments, no model. `POST /chat/act`."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=40)
    args: dict = {}
    #: Append the turn to the thread. Off for a tap — its confirmation is a
    #: receipt that flashes and goes, and the ledger already holds the fact.
    #: On for a shortcut the user asked for, whose card belongs in the
    #: scrollback.
    record: bool = False


class ChatOut(BaseModel):
    """Prose first, then the typed cards. `cards` always leads with the agent's
    own sentence, so a client that renders nothing else still works."""

    reply: str
    cards: list[dict]
    tokens_in: int
    tokens_out: int
    model: str


class MessageOut(Row):
    id: str
    seq: int
    role: str
    text: str
    cards: list[dict] | None
    created_at: datetime


class HistoryOut(BaseModel):
    messages: list[MessageOut]
    #: More messages sit before this page, within the same scope.
    has_more: bool = False
    #: What the user has cleared from view, 0 if never. With `has_more` false
    #: and this above 0, the client offers *Show older*.
    cleared_through_seq: int = 0
    #: What the model is told about everything before the window. Exposed
    #: because the fastest way to catch a wrong belief is to read it.
    summary: str | None
