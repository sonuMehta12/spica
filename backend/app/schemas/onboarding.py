"""Wire shapes for the first run's answers. spec/done/onboarding-goals.md § A turn."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Screen 3's questions, by the name the agent's prompt knows them by. The copy
#: lives in the client and in `skills/onboarding.md`; the picks that choose
#: among them stay on the client.
Question = Literal["about", "place", "health", "money", "habits"]


class OnboardingTurnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Question
    #: The answer as typed, or as the recogniser heard it and they sent it.
    text: str = Field(min_length=1, max_length=4000)
    #: The client's day, for the weigh-in: a server deciding "today" would put
    #: a late-night answer on the wrong one.
    local_day: date


class OnboardingTurnOut(BaseModel):
    #: The confirm cards for this turn's writes, one per write.
    cards: list[dict]
    #: A follow-up, or "Say that again?" — null once the question is done.
    reply: str | None
    #: The agent called `next_question`: the screen moves on.
    next: bool
