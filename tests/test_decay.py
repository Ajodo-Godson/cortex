"""Tests for ConstraintDecay: stale trigger detection and confidence decay."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agents.decay import ConstraintDecay, DecayReport
from core.schema import Constraint, Scope
from core.storage import ensure_cortex_dirs, load_constraint


def _make_constraint(
    constraint_id: str,
    ast_triggers: list[str],
    confidence: float = 0.9,
) -> Constraint:
    return Constraint(
        constraint_id=constraint_id,
        meta_type="operational_constraint",
        scope=Scope(language="python", services=[], ast_triggers=ast_triggers, error_codes=[]),
        context="test context",
        constraint="Never do the bad thing. It causes issues. Always do the good thing.",
        never_do=["do the bad thing"],
        because="it causes issues",
        instead="do the good thing",
        evidence=[],
        validation="run the tests",
        confidence=confidence,
        source="observed",
    )


def _store(repo_root: Path, c: Constraint) -> None:
    ensure_cortex_dirs(repo_root)
    path = repo_root / ".cortex" / "constraints" / f"{c.constraint_id}.yaml"
    path.write_text(yaml.safe_dump(c.model_dump(mode="json")), encoding="utf-8")


def _write_source(repo_root: Path, name: str, content: str) -> Path:
    path = repo_root / name
    path.write_text(content, encoding="utf-8")
    return path


# ── scan(): stale detection ────────────────────────────────────────────────────

def test_scan_no_report_when_all_triggers_present(tmp_path: Path) -> None:
    _write_source(tmp_path, "app.py", "result = db.session.commit()\n")
    c = _make_constraint("c-001", ast_triggers=["db.session.commit()"])
    _store(tmp_path, c)
    decay = ConstraintDecay(tmp_path)
    decay._get_source_files = lambda: [tmp_path / "app.py"]
    assert decay.scan() == []


def test_scan_reports_missing_trigger(tmp_path: Path) -> None:
    _write_source(tmp_path, "app.py", "result = safe_operation()\n")
    c = _make_constraint("c-001", ast_triggers=["db.session.commit()"])
    _store(tmp_path, c)
    decay = ConstraintDecay(tmp_path)
    decay._get_source_files = lambda: [tmp_path / "app.py"]
    reports = decay.scan()
    assert len(reports) == 1
    assert "db.session.commit()" in reports[0].missing_triggers


def test_scan_no_report_for_constraint_without_triggers(tmp_path: Path) -> None:
    c = _make_constraint("c-001", ast_triggers=[])
    _store(tmp_path, c)
    decay = ConstraintDecay(tmp_path)
    decay._get_source_files = lambda: []
    assert decay.scan() == []


def test_drift_ratio_all_missing(tmp_path: Path) -> None:
    _write_source(tmp_path, "app.py", "pass\n")
    c = _make_constraint("c-001", ast_triggers=["bulk_insert", "db.session.commit()"])
    _store(tmp_path, c)
    decay = ConstraintDecay(tmp_path)
    decay._get_source_files = lambda: [tmp_path / "app.py"]
    reports = decay.scan()
    assert reports[0].drift_ratio == 1.0


def test_drift_ratio_partial_missing(tmp_path: Path) -> None:
    _write_source(tmp_path, "app.py", "db.session.commit()\n")
    c = _make_constraint("c-001", ast_triggers=["db.session.commit()", "bulk_insert"])
    _store(tmp_path, c)
    decay = ConstraintDecay(tmp_path)
    decay._get_source_files = lambda: [tmp_path / "app.py"]
    reports = decay.scan()
    assert reports[0].drift_ratio == pytest.approx(0.5)
    assert reports[0].missing_triggers == ["bulk_insert"]


def test_confidence_decreases_per_missing_trigger(tmp_path: Path) -> None:
    _write_source(tmp_path, "app.py", "pass\n")
    c = _make_constraint("c-001", ast_triggers=["pattern_a", "pattern_b"], confidence=0.9)
    _store(tmp_path, c)
    decay = ConstraintDecay(tmp_path)
    decay._get_source_files = lambda: [tmp_path / "app.py"]
    reports = decay.scan()
    # Two missing triggers × 0.10 decay each = 0.20 total decay
    assert reports[0].new_confidence == pytest.approx(0.70)
    assert reports[0].original_confidence == pytest.approx(0.90)


def test_confidence_does_not_go_below_zero(tmp_path: Path) -> None:
    _write_source(tmp_path, "app.py", "pass\n")
    triggers = [f"pattern_{i}" for i in range(20)]
    c = _make_constraint("c-001", ast_triggers=triggers, confidence=0.5)
    _store(tmp_path, c)
    decay = ConstraintDecay(tmp_path)
    decay._get_source_files = lambda: [tmp_path / "app.py"]
    reports = decay.scan()
    assert reports[0].new_confidence >= 0.0


def test_routed_to_gardener_when_confidence_below_threshold(tmp_path: Path) -> None:
    _write_source(tmp_path, "app.py", "pass\n")
    c = _make_constraint("c-001", ast_triggers=["p1", "p2", "p3", "p4", "p5"], confidence=0.9)
    _store(tmp_path, c)
    decay = ConstraintDecay(tmp_path)
    decay._get_source_files = lambda: [tmp_path / "app.py"]
    reports = decay.scan()
    # 5 missing × 0.10 = 0.50 decay → 0.40 < 0.50 threshold → routed
    assert reports[0].routed_to_gardener is True


def test_not_routed_when_confidence_stays_above_threshold(tmp_path: Path) -> None:
    _write_source(tmp_path, "app.py", "pass\n")
    c = _make_constraint("c-001", ast_triggers=["missing_one"], confidence=0.9)
    _store(tmp_path, c)
    decay = ConstraintDecay(tmp_path)
    decay._get_source_files = lambda: [tmp_path / "app.py"]
    reports = decay.scan()
    # 1 missing × 0.10 = 0.10 decay → 0.80 ≥ 0.50 threshold → not routed
    assert reports[0].routed_to_gardener is False


# ── apply(): write updated confidence ─────────────────────────────────────────

def test_apply_writes_updated_confidence(tmp_path: Path) -> None:
    _write_source(tmp_path, "app.py", "pass\n")
    c = _make_constraint("c-001", ast_triggers=["stale_pattern"], confidence=0.9)
    _store(tmp_path, c)
    decay = ConstraintDecay(tmp_path)
    decay._get_source_files = lambda: [tmp_path / "app.py"]
    reports = decay.scan()
    decay.apply(reports)

    updated = load_constraint(tmp_path / ".cortex" / "constraints" / "c-001.yaml")
    assert updated.confidence == pytest.approx(reports[0].new_confidence)
    assert updated.confidence < 0.9


def test_apply_does_not_modify_non_stale_constraints(tmp_path: Path) -> None:
    _write_source(tmp_path, "app.py", "db.session.commit()\n")
    c = _make_constraint("c-001", ast_triggers=["db.session.commit()"], confidence=0.9)
    _store(tmp_path, c)
    decay = ConstraintDecay(tmp_path)
    decay._get_source_files = lambda: [tmp_path / "app.py"]
    reports = decay.scan()
    assert reports == []  # nothing stale, nothing to apply
