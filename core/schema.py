"""Core schema placeholders."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field


class Constraint(BaseModel):
    """Minimal constraint schema placeholder."""

    constraint_id: str
    title: str
    never_do: list[str] = Field(default_factory=list)
    because: str
    instead: str
