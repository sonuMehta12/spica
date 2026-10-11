"""Shared wire bases."""

from pydantic import BaseModel, ConfigDict


class Row(BaseModel):
    """Reads straight off a SQLAlchemy object rather than a dict."""

    model_config = ConfigDict(from_attributes=True)
