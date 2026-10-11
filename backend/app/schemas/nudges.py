"""What the bell's page reads and what it may say back. spec/in-progress/nudges.md."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.writes import Patch


class NudgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    title: str
    #: What was said at that hour — history, never a claim about now.
    line: str | None
    local_day: date
    created_at: datetime
    seen_at: datetime | None
    done_at: datetime | None
    dismissed_at: datetime | None
    #: The run that made it, for *Turn these off*.
    schedule_id: str | None
    #: Live ids the page reads rows by.
    refs: dict


class NudgePatch(Patch):
    """Each a switch: true stamps now, false clears. The server keeps the time;
    the phone says only what happened."""

    seen: bool | None = None
    done: bool | None = None
    dismissed: bool | None = None
