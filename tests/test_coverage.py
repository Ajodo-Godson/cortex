"""Tests for the P7 coverage map."""

from __future__ import annotations

from pathlib import Path

from core.coverage import (
    load_coverage,
    record_retrieval_hit,
    record_unconstrained_files,
)


def test_record_hit_increments_count(tmp_path: Path) -> None:
    record_retrieval_hit(tmp_path, "auth-001", [])
    record_retrieval_hit(tmp_path, "auth-001", [])
    data = load_coverage(tmp_path)
    assert data["constraint_hits"]["auth-001"]["hit_count"] == 2


def test_record_hit_logs_triggered_files(tmp_path: Path) -> None:
    record_retrieval_hit(tmp_path, "auth-001", [str(tmp_path / "payments.py")])
    data = load_coverage(tmp_path)
    assert "payments.py" in data["constraint_hits"]["auth-001"]["triggered_by_files"][0]


def test_record_hit_deduplicates_files(tmp_path: Path) -> None:
    f = str(tmp_path / "app.py")
    record_retrieval_hit(tmp_path, "auth-001", [f])
    record_retrieval_hit(tmp_path, "auth-001", [f])
    data = load_coverage(tmp_path)
    assert len(data["constraint_hits"]["auth-001"]["triggered_by_files"]) == 1


def test_record_hit_updates_file_coverage(tmp_path: Path) -> None:
    record_retrieval_hit(tmp_path, "auth-001", [str(tmp_path / "service.py")])
    data = load_coverage(tmp_path)
    assert "auth-001" in data["file_coverage"]["service.py"]["constraints_triggered"]


def test_record_hit_increments_file_touch_count(tmp_path: Path) -> None:
    f = str(tmp_path / "service.py")
    record_retrieval_hit(tmp_path, "auth-001", [f])
    record_retrieval_hit(tmp_path, "auth-002", [f])
    data = load_coverage(tmp_path)
    assert data["file_coverage"]["service.py"]["touch_count"] == 2


def test_record_multiple_constraints_independently(tmp_path: Path) -> None:
    record_retrieval_hit(tmp_path, "c-001", [])
    record_retrieval_hit(tmp_path, "c-002", [])
    record_retrieval_hit(tmp_path, "c-001", [])
    data = load_coverage(tmp_path)
    assert data["constraint_hits"]["c-001"]["hit_count"] == 2
    assert data["constraint_hits"]["c-002"]["hit_count"] == 1


def test_record_unconstrained_files_logs_new(tmp_path: Path) -> None:
    record_unconstrained_files(tmp_path, [str(tmp_path / "utils.py")])
    data = load_coverage(tmp_path)
    assert any("utils.py" in f for f in data["unconstrained_files"])


def test_record_unconstrained_skips_covered_files(tmp_path: Path) -> None:
    f = str(tmp_path / "service.py")
    record_retrieval_hit(tmp_path, "auth-001", [f])
    record_unconstrained_files(tmp_path, [f])
    data = load_coverage(tmp_path)
    assert not any("service.py" in u for u in data.get("unconstrained_files", []))


def test_record_unconstrained_deduplicates(tmp_path: Path) -> None:
    f = str(tmp_path / "utils.py")
    record_unconstrained_files(tmp_path, [f])
    record_unconstrained_files(tmp_path, [f])
    data = load_coverage(tmp_path)
    matching = [u for u in data["unconstrained_files"] if "utils.py" in u]
    assert len(matching) == 1


def test_load_coverage_returns_empty_when_no_file(tmp_path: Path) -> None:
    data = load_coverage(tmp_path)
    assert data["constraint_hits"] == {}
    assert data["file_coverage"] == {}


def test_coverage_sets_last_updated(tmp_path: Path) -> None:
    record_retrieval_hit(tmp_path, "c-001", [])
    data = load_coverage(tmp_path)
    assert "last_updated" in data
