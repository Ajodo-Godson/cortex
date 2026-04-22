"""Core schema models for CORTEX constraints and correction events."""

from __future__ import annotations

from datetime import date as dt_date
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


class Scope(BaseModel):
    """Targeted code and service scope for a constraint."""

    language: str
    services: list[str] = Field(default_factory=list)
    ast_triggers: list[str] = Field(default_factory=list)
    error_codes: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    """Evidence supporting a constraint."""

    type: str
    reference: str | None = None
    date: dt_date | None = None
    commit_hash: str | None = None
    corrected_by: str | None = None


class Constraint(BaseModel):
    """Structured operational constraint stored in the library."""

    constraint_id: str
    meta_type: Literal["operational_constraint", "workflow_constraint", "architectural_constraint"]
    scope: Scope
    context: str
    constraint: str
    never_do: list[str] = Field(default_factory=list)
    because: str
    instead: str
    evidence: list[Evidence] = Field(default_factory=list)
    validation: str
    confidence: float = Field(ge=0.0, le=1.0)
    last_validated: dt_date | None = None
    source: Literal["observed", "inferred"] = "observed"

    @field_validator("constraint")
    @classmethod
    def constraint_must_be_prose(cls, value: str) -> str:
        if "```" in value:
            raise ValueError("constraint must be prose, not a fenced code block")
        return value

    @field_validator("never_do")
    @classmethod
    def never_do_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("never_do must include at least one forbidden action")
        return value


class CorrectionEvent(BaseModel):
    """Ground-truth correction event used by the Distiller."""

    event_id: str
    constraint_key: str
    sequence: int = Field(ge=1, le=999)
    meta_type: Literal["operational_constraint", "workflow_constraint", "architectural_constraint"]
    scope: Scope
    context: str
    failing_action: str
    correction: str
    because: str
    instead: str
    evidence: list[Evidence] = Field(default_factory=list)
    validation: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    source: Literal["observed", "inferred"] = "observed"
    last_validated: dt_date | None = None

    @property
    def constraint_id(self) -> str:
        return f"{self.constraint_key}-{self.sequence:03d}"
