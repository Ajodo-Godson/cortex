"""L2 semantic retrieval: keyword-overlap scoring as a proxy for embedding similarity."""

from __future__ import annotations

import re

from core.schema import Constraint


def score(constraint: Constraint, query: str) -> float:
    """Score a constraint against a free-text query using token overlap.

    Returns a value in [0.0, 1.0] representing the fraction of query tokens
    found anywhere in the constraint's searchable text.
    """
    if not query:
        return 0.0

    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0

    searchable = " ".join([
        constraint.constraint_id,
        constraint.context,
        constraint.constraint,
        constraint.because,
        constraint.instead,
        " ".join(constraint.scope.services),
        " ".join(constraint.scope.ast_triggers),
        " ".join(constraint.scope.error_codes),
    ]).lower()

    matched = sum(1 for token in query_tokens if token in searchable)
    return matched / len(query_tokens)


def _tokenize(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 3}
