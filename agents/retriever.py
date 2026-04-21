"""Retriever placeholder implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
    """Returns placeholder session constraints."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def retrieve(self, boost: str | None = None, verbose: bool = False) -> RetrievalResult:
        del verbose
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
