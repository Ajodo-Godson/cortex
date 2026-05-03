"""L3 schema-aware reranker: Jaccard similarity between query tokens and constraint text."""

from __future__ import annotations

import re
from pathlib import Path

from core.schema import Constraint


def _tokenize(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 3}


def _vectorize(constraint: Constraint) -> set[str]:
    return _tokenize(" ".join([
        constraint.context,
        constraint.constraint,
        constraint.because,
        constraint.instead,
        " ".join(constraint.never_do),
        constraint.scope.language,
        " ".join(constraint.scope.services),
        " ".join(constraint.scope.ast_triggers),
        " ".join(constraint.scope.error_codes),
    ]))


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


class JaccardReranker:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def score(
        self,
        scored: list[tuple[Constraint, float, list[str]]],
        language: str = "python",
        active_services: list[str] | None = None,
        max_results: int = 5,
    ) -> list[tuple[Constraint, float, list[str]]]:
        query_set = _tokenize(f"{language} {' '.join(active_services or [])}")

        adjusted: list[tuple[Constraint, float, list[str]]] = []
        for constraint, base_score, reasons in scored:
            sim = _jaccard(query_set, _vectorize(constraint))
            new_reasons = list(reasons)
            if sim > 0:
                new_reasons.append(f"jaccard: {sim:.3f}")
            adjusted.append((constraint, base_score + sim, new_reasons))

        adjusted.sort(key=lambda item: (-item[1], item[0].constraint_id))
        return adjusted[:max_results]


def rerank(
    scored: list[tuple[Constraint, float, list[str]]],
    language: str = "python",
    active_services: list[str] | None = None,
    max_results: int = 5,
) -> list[tuple[Constraint, float, list[str]]]:
    """Rerank by Jaccard similarity between query tokens and each constraint's full text."""
    return JaccardReranker(Path(".")).score(
        scored, language=language, active_services=active_services, max_results=max_results
    )
