"""Retriever placeholder implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.storage import load_constraints


@dataclass
class RetrievedConstraint:
    constraint_id: str
    title: str
    never_do: str
    because: str
    instead: str


@dataclass
class RetrievalResult:
    constraints: list[RetrievedConstraint]


class Retriever:
    """Returns stored constraints, falling back to scaffold placeholders."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def retrieve(self, boost: str | None = None, verbose: bool = False) -> RetrievalResult:
        del verbose
        stored_constraints = load_constraints(self.repo_root)
        if stored_constraints:
            filtered = self._apply_boost(stored_constraints, boost=boost)
            selected = filtered[:5]
            return RetrievalResult(
                constraints=[
                    RetrievedConstraint(
                        constraint_id=constraint.constraint_id,
                        title=constraint.context,
                        never_do=constraint.never_do[0],
                        because=constraint.because,
                        instead=constraint.instead,
                    )
                    for constraint in selected
                ]
            )

        boost_suffix = f" in {boost}" if boost else ""
        constraints = [
            RetrievedConstraint(
                constraint_id="scaffold-session-001",
                title=f"Session lifecycle management{boost_suffix}",
                never_do="Never lose session state without warning the user",
                because="Session logs are the backbone of later distillation and recovery",
                instead="Persist session metadata and handle orphan recovery explicitly",
            ),
            RetrievedConstraint(
                constraint_id="scaffold-cli-001",
                title="CLI-first architecture",
                never_do="Never hide core lifecycle behavior behind an implicit background flow",
                because="The README requires explicit start and stop boundaries for debuggability",
                instead="Keep session start, stop, status, and recovery as first-class commands",
            ),
        ]
        return RetrievalResult(constraints=constraints)

    def _apply_boost(self, constraints: list, boost: str | None) -> list:
        if not boost:
            return constraints

        normalized = boost.lower()
        matching = [
            constraint
            for constraint in constraints
            if normalized in constraint.context.lower()
            or any(normalized in service.lower() for service in constraint.scope.services)
        ]
        non_matching = [constraint for constraint in constraints if constraint not in matching]
        return matching + non_matching
