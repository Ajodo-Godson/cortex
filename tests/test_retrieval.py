"""Tests for the three-layer retrieval stack: L1 AST filter, L2 semantic, L3 reranker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.schema import Constraint, Scope
from retrieval.ast_filter import scan
from retrieval.semantic import score as semantic_score
from retrieval.reranker import rerank


# ── Shared fixtures ────────────────────────────────────────────────────────────

def _make_constraint(
    constraint_id: str = "test-constraint-001",
    context: str = "test context",
    confidence: float = 0.85,
    services: list[str] | None = None,
    ast_triggers: list[str] | None = None,
    source: str = "observed",
    meta_type: str = "operational_constraint",
    language: str = "python",
) -> Constraint:
    return Constraint(
        constraint_id=constraint_id,
        meta_type=meta_type,  # type: ignore[arg-type]
        scope=Scope(
            language=language,
            services=services or [],
            ast_triggers=ast_triggers or [],
            error_codes=[],
        ),
        context=context,
        constraint=f"Never do the failing action. {context}. Always do the right thing.",
        never_do=["do the wrong thing"],
        because="it causes problems",
        instead="do the right thing",
        evidence=[],
        validation="run the tests",
        confidence=confidence,
        source=source,  # type: ignore[arg-type]
    )


# ── L1: AST fast-filter ────────────────────────────────────────────────────────

def test_l1_finds_pattern_in_file(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("result = db.session.commit()\n", encoding="utf-8")

    constraint = _make_constraint(ast_triggers=["db.session.commit()"])
    hits = scan([str(target)], [constraint])

    assert "test-constraint-001" in hits
    assert "db.session.commit()" in hits["test-constraint-001"]


def test_l1_returns_empty_when_no_pattern_matches(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("result = safe_operation()\n", encoding="utf-8")

    constraint = _make_constraint(ast_triggers=["db.session.commit()"])
    hits = scan([str(target)], [constraint])

    assert hits == {}


def test_l1_returns_empty_when_no_ast_triggers() -> None:
    constraint = _make_constraint(ast_triggers=[])
    hits = scan(["/nonexistent/file.py"], [constraint])
    assert hits == {}


def test_l1_returns_empty_for_missing_files(tmp_path: Path) -> None:
    constraint = _make_constraint(ast_triggers=["bulk_insert"])
    hits = scan([str(tmp_path / "does_not_exist.py")], [constraint])
    assert hits == {}


def test_l1_matches_multiple_patterns_in_same_file(tmp_path: Path) -> None:
    target = tmp_path / "payments.py"
    target.write_text(
        "db.session.commit()\nbulk_insert(rows)\n",
        encoding="utf-8",
    )
    constraint = _make_constraint(ast_triggers=["db.session.commit()", "bulk_insert"])
    hits = scan([str(target)], [constraint])

    assert "test-constraint-001" in hits
    assert set(hits["test-constraint-001"]) == {"db.session.commit()", "bulk_insert"}


def test_l1_matches_across_multiple_files(tmp_path: Path) -> None:
    file_a = tmp_path / "a.py"
    file_b = tmp_path / "b.py"
    file_a.write_text("bulk_insert(rows)\n", encoding="utf-8")
    file_b.write_text("bulk_insert(more_rows)\n", encoding="utf-8")

    constraint = _make_constraint(ast_triggers=["bulk_insert"])
    hits = scan([str(file_a), str(file_b)], [constraint])

    assert "test-constraint-001" in hits


def test_l1_only_returns_constraints_with_matches(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("refresh_token()\n", encoding="utf-8")

    c1 = _make_constraint("c-001", ast_triggers=["refresh_token()"])
    c2 = _make_constraint("c-002", ast_triggers=["bulk_insert"])
    hits = scan([str(target)], [c1, c2])

    assert "c-001" in hits
    assert "c-002" not in hits


def test_l1_returns_empty_when_file_list_is_empty() -> None:
    constraint = _make_constraint(ast_triggers=["db.session.commit()"])
    hits = scan([], [constraint])
    assert hits == {}


def test_l1_handles_empty_constraint_list(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("db.session.commit()\n", encoding="utf-8")
    hits = scan([str(target)], [])
    assert hits == {}


# ── L2: Semantic scoring ───────────────────────────────────────────────────────

def test_l2_returns_zero_for_empty_query() -> None:
    c = _make_constraint(context="PostgreSQL transaction handling")
    assert semantic_score(c, "") == 0.0


def test_l2_returns_positive_for_overlapping_token() -> None:
    c = _make_constraint(context="PostgreSQL transaction handling above 10MB payload")
    result = semantic_score(c, "transaction deadlock postgres")
    assert result > 0.0


def test_l2_returns_zero_for_no_overlap() -> None:
    c = _make_constraint(context="JWT refresh behavior in payment flows")
    result = semantic_score(c, "kubernetes pod scheduling eviction")
    assert result == 0.0


def test_l2_scores_higher_for_more_overlap() -> None:
    c = _make_constraint(
        context="auth token refresh inside database transaction causes timeout",
        services=["payments-api"],
        ast_triggers=["refresh_token()", "db.transaction"],
    )
    high_query = "auth token refresh transaction timeout payments"
    low_query = "auth kubernetes eviction scaling"  # only "auth" matches → lower score
    assert semantic_score(c, high_query) > semantic_score(c, low_query)


def test_l2_score_is_bounded_between_0_and_1() -> None:
    c = _make_constraint(context="x y z", services=["svc"], ast_triggers=["pat"])
    result = semantic_score(c, "x y z svc pat extra tokens that dont match")
    assert 0.0 <= result <= 1.0


# ── L3: Schema-aware reranker ──────────────────────────────────────────────────

def test_l3_returns_at_most_max_results() -> None:
    constraints = [_make_constraint(f"c-{i:03d}") for i in range(10)]
    scored = [(c, float(i), []) for i, c in enumerate(constraints)]
    result = rerank(scored, max_results=3)
    assert len(result) <= 3


def test_l3_applies_language_bonus() -> None:
    python_c = _make_constraint("py-001", language="python")
    java_c = _make_constraint("java-001", language="java")
    scored = [(python_c, 1.0, []), (java_c, 1.0, [])]
    result = rerank(scored, language="python", max_results=5)
    py_score = next(score for c, score, _ in result if c.constraint_id == "py-001")
    java_score = next(score for c, score, _ in result if c.constraint_id == "java-001")
    assert py_score > java_score


def test_l3_applies_service_bonus() -> None:
    matched_c = _make_constraint("svc-match-001", services=["payments-api"])
    unmatched_c = _make_constraint("svc-none-001", services=["unrelated-service"])
    scored = [(matched_c, 1.0, []), (unmatched_c, 1.0, [])]
    result = rerank(scored, active_services=["payments-api"], max_results=5)
    match_score = next(score for c, score, _ in result if c.constraint_id == "svc-match-001")
    none_score = next(score for c, score, _ in result if c.constraint_id == "svc-none-001")
    assert match_score > none_score


def test_l3_preserves_original_order_when_no_bonuses_apply() -> None:
    c1 = _make_constraint("z-001", confidence=0.95)
    c2 = _make_constraint("a-002", confidence=0.80)
    scored = [(c1, 0.95, []), (c2, 0.80, [])]
    result = rerank(scored, language="go", active_services=[], max_results=5)
    assert result[0][0].constraint_id == "z-001"
    assert result[1][0].constraint_id == "a-002"
