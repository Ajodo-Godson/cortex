"""Retriever placeholder implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from core.schema import Constraint
from core.storage import load_constraints


@dataclass
class RetrievedConstraint:
    constraint_id: str
    title: str
    never_do: str
    because: str
    instead: str
    score: float = 0.0
    reasons: list[str] | None = None


@dataclass
class RetrievalResult:
    constraints: list[RetrievedConstraint]


class Retriever:
    """Returns stored constraints, falling back to scaffold placeholders."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def retrieve(self, boost: str | None = None, verbose: bool = False) -> RetrievalResult:
        stored_constraints = load_constraints(self.repo_root)
        if stored_constraints:
            branch_name = self._get_branch_name()
            ranked = self._rank_constraints(stored_constraints, branch_name=branch_name, boost=boost)
            selected = ranked[:5]
            return RetrievalResult(
                constraints=[
                    RetrievedConstraint(
                        constraint_id=constraint.constraint_id,
                        title=constraint.context,
                        never_do=constraint.never_do[0],
                        because=constraint.because,
                        instead=constraint.instead,
                        score=score,
                        reasons=reasons if verbose else None,
                    )
                    for constraint, score, reasons in selected
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
                score=1.0,
                reasons=["fallback scaffold"] if verbose else None,
            ),
            RetrievedConstraint(
                constraint_id="scaffold-cli-001",
                title="CLI-first architecture",
                never_do="Never hide core lifecycle behavior behind an implicit background flow",
                because="The README requires explicit start and stop boundaries for debuggability",
                instead="Keep session start, stop, status, and recovery as first-class commands",
                score=0.9,
                reasons=["fallback scaffold"] if verbose else None,
            ),
        ]
        return RetrievalResult(constraints=constraints)

    def _rank_constraints(
        self,
        constraints: list[Constraint],
        branch_name: str,
        boost: str | None,
    ) -> list[tuple[Constraint, float, list[str]]]:
        ranked: list[tuple[Constraint, float, list[str]]] = []
        branch_tokens = self._tokenize(branch_name)
        boost_tokens = self._tokenize(boost or "")

        for constraint in constraints:
            score = 0.0
            reasons: list[str] = []

            score += constraint.confidence
            reasons.append(f"confidence={constraint.confidence:.2f}")

            branch_matches = self._matches_tokens(constraint, branch_tokens)
            if branch_matches:
                score += 2.0 * len(branch_matches)
                reasons.append(f"branch match: {', '.join(branch_matches)}")

            boost_matches = self._matches_tokens(constraint, boost_tokens)
            if boost_matches:
                score += 3.0 * len(boost_matches)
                reasons.append(f"boost match: {', '.join(boost_matches)}")

            if constraint.source == "observed":
                score += 0.5
                reasons.append("observed source")

            if constraint.meta_type == "operational_constraint":
                score += 0.25
                reasons.append("operational constraint")

            ranked.append((constraint, score, reasons))

        ranked.sort(key=lambda item: (-item[1], item[0].constraint_id))
        return ranked

    def _matches_tokens(self, constraint: Constraint, tokens: set[str]) -> list[str]:
        searchable = " ".join(
            [
                constraint.constraint_id,
                constraint.context,
                constraint.because,
                constraint.instead,
                " ".join(constraint.scope.services),
                " ".join(constraint.scope.ast_triggers),
                " ".join(constraint.scope.error_codes),
            ]
        ).lower()
        return [token for token in sorted(tokens) if token in searchable]

    def _tokenize(self, value: str) -> set[str]:
        return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if len(token) >= 3}

    def _get_branch_name(self) -> str:
        head_path = self.repo_root / ".git" / "HEAD"
        if not head_path.exists():
            return "unknown"
        head = head_path.read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            return head.rsplit("/", maxsplit=1)[-1]
        return head[:7]
