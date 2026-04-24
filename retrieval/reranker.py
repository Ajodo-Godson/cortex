"""L3 schema-aware reranker: cross-references constraint scope against current environment."""

from __future__ import annotations

from core.schema import Constraint


def rerank(
    scored: list[tuple[Constraint, float, list[str]]],
    language: str = "python",
    active_services: list[str] | None = None,
    max_results: int = 5,
) -> list[tuple[Constraint, float, list[str]]]:
    """Adjust scores based on how well each constraint's scope matches the
    current environment, then return the top max_results.

    Bonuses applied:
    - +0.10 if constraint language matches the repo language
    - +0.20 per service in the constraint's scope that appears in active_services
    """
    service_set = {s.lower() for s in (active_services or [])}

    adjusted: list[tuple[Constraint, float, list[str]]] = []
    for constraint, score, reasons in scored:
        bonus = 0.0
        new_reasons = list(reasons)

        if constraint.scope.language.lower() == language.lower():
            bonus += 0.10
            new_reasons.append(f"language match: {language}")

        service_matches = [
            s for s in constraint.scope.services if s.lower() in service_set
        ]
        if service_matches:
            bonus += 0.20 * len(service_matches)
            new_reasons.append(f"service match: {', '.join(service_matches)}")

        adjusted.append((constraint, score + bonus, new_reasons))

    adjusted.sort(key=lambda item: (-item[1], item[0].constraint_id))
    return adjusted[:max_results]
