"""L3 schema-aware reranker: BM25 over precomputed constraint token vectors."""

from __future__ import annotations

import math
import re
from collections import Counter

from core.schema import Constraint

_K1 = 1.5
_B = 0.75


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 3]


def _vectorize(constraint: Constraint) -> Counter[str]:
    tokens = _tokenize(" ".join([
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
    return Counter(tokens)


def _compute_idf(doc_vectors: list[Counter[str]]) -> dict[str, float]:
    N = len(doc_vectors)
    df: Counter[str] = Counter()
    for vec in doc_vectors:
        for token in vec:
            df[token] += 1
    return {
        token: math.log((N - n + 0.5) / (n + 0.5) + 1)
        for token, n in df.items()
    }


def _bm25(
    query_tokens: list[str],
    doc_tf: Counter[str],
    idf: dict[str, float],
    dl: int,
    avg_dl: float,
) -> float:
    if avg_dl == 0:
        return 0.0
    score = 0.0
    for token in query_tokens:
        if token not in doc_tf:
            continue
        tf = doc_tf[token]
        score += idf.get(token, 0.0) * (tf * (_K1 + 1)) / (
            tf + _K1 * (1 - _B + _B * dl / avg_dl)
        )
    return score


class JaccardReranker:
    def __init__(self, constraints: list[Constraint]) -> None:
        self._doc_vectors: dict[str, Counter[str]] = {
            c.constraint_id: _vectorize(c) for c in constraints
        }
        doc_vecs = list(self._doc_vectors.values())
        self._idf = _compute_idf(doc_vecs)
        total = sum(sum(v.values()) for v in doc_vecs)
        self._avg_dl = total / max(len(doc_vecs), 1)

    def score(
        self,
        scored: list[tuple[Constraint, float, list[str]]],
        query: str = "",
        language: str = "python",
        active_services: list[str] | None = None,
        max_results: int = 5,
    ) -> list[tuple[Constraint, float, list[str]]]:
        query_tokens = _tokenize(f"{query} {language} {' '.join(active_services or [])}")

        adjusted: list[tuple[Constraint, float, list[str]]] = []
        for constraint, base_score, reasons in scored:
            doc_tf = self._doc_vectors.get(constraint.constraint_id) or _vectorize(constraint)
            dl = sum(doc_tf.values())
            bm = _bm25(query_tokens, doc_tf, self._idf, dl, self._avg_dl)
            new_reasons = list(reasons)
            if bm > 0:
                new_reasons.append(f"bm25: {bm:.3f}")
            adjusted.append((constraint, base_score + bm, new_reasons))

        adjusted.sort(key=lambda item: (-item[1], item[0].constraint_id))
        return adjusted[:max_results]


def rerank(
    scored: list[tuple[Constraint, float, list[str]]],
    query: str = "",
    language: str = "python",
    active_services: list[str] | None = None,
    max_results: int = 5,
) -> list[tuple[Constraint, float, list[str]]]:
    """Rerank by BM25 score between query tokens and each constraint's full text."""
    constraints = [c for c, _, _ in scored]
    return JaccardReranker(constraints).score(
        scored, query=query, language=language,
        active_services=active_services, max_results=max_results,
    )
