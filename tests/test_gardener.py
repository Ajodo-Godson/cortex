"""Tests for the Gardener: conflict detection and reconciliation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from core.schema import Constraint, Scope
from core.storage import ensure_cortex_dirs
from gardener.gardener import ConflictReport, Gardener


def _make_constraint(
    constraint_id: str,
    constraint_text: str,
    never_do: str,
    instead: str,
    ast_triggers: list[str] | None = None,
    services: list[str] | None = None,
    language: str = "python",
) -> Constraint:
    return Constraint(
        constraint_id=constraint_id,
        meta_type="operational_constraint",
        scope=Scope(
            language=language,
            services=services or [],
            ast_triggers=ast_triggers or [],
            error_codes=[],
        ),
        context="test context",
        constraint=constraint_text,
        never_do=[never_do],
        because="test reason",
        instead=instead,
        evidence=[],
        validation="run the tests",
        confidence=0.8,
        source="observed",
    )


def _write_constraint(directory: Path, c: Constraint) -> None:
    (directory / f"{c.constraint_id}.yaml").write_text(
        yaml.safe_dump(c.model_dump(mode="json")), encoding="utf-8"
    )


# ── scan(): heuristic conflict detection ──────────────────────────────────────

def test_scan_returns_empty_when_no_constraints(tmp_path: Path) -> None:
    assert Gardener(tmp_path).scan() == []


def test_scan_returns_empty_for_single_constraint(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    c = _make_constraint("only-001", "Never do X.", "Do X", "Do Y")
    _write_constraint(tmp_path / ".cortex" / "constraints", c)
    assert Gardener(tmp_path).scan() == []


def test_detect_conflict_shared_trigger_different_rules() -> None:
    g = Gardener(Path("/tmp"))
    a = _make_constraint(
        "commit-in-loop-001",
        "Never commit inside a loop. It causes deadlocks.",
        "Commit inside a loop",
        "Batch all writes then commit once outside",
        ast_triggers=["db.session.commit()"],
    )
    b = _make_constraint(
        "commit-per-record-001",
        "Always commit after each record to preserve partial progress.",
        "Skip committing after each record",
        "Commit after each individual record write",
        ast_triggers=["db.session.commit()"],
    )
    conflicting, explanation = g._detect_conflict(a, b)
    assert conflicting is True
    assert "db.session.commit()" in explanation


def test_detect_conflict_opposing_always_never() -> None:
    g = Gardener(Path("/tmp"))
    a = _make_constraint(
        "always-open-tx-001",
        "Always open the transaction before calling the token service.",
        "Call token service outside a transaction",
        "Open transaction then call token service inside it",
    )
    b = _make_constraint(
        "never-token-in-tx-001",
        "Never call the token service inside an open transaction.",
        "Call token service inside a transaction",
        "Call token service before opening the transaction",
    )
    conflicting, _ = g._detect_conflict(a, b)
    assert conflicting is True


def test_detect_conflict_opposing_inside_outside() -> None:
    g = Gardener(Path("/tmp"))
    a = _make_constraint(
        "lock-inside-001",
        "Always acquire the lock inside the retry loop.",
        "Acquire the lock outside the retry loop",
        "Acquire the lock inside each retry attempt",
    )
    b = _make_constraint(
        "lock-outside-001",
        "Never acquire locks inside a retry loop to avoid deadlocks.",
        "Acquire locks inside a retry loop",
        "Acquire the lock once outside and release after all retries",
    )
    conflicting, _ = g._detect_conflict(a, b)
    assert conflicting is True


def test_detect_no_conflict_unrelated_constraints() -> None:
    g = Gardener(Path("/tmp"))
    a = _make_constraint(
        "no-eval-001",
        "Never use eval() on user input. It allows code injection.",
        "Use eval() on user input",
        "Use ast.literal_eval() for safe parsing",
        ast_triggers=["eval("],
    )
    b = _make_constraint(
        "use-utc-001",
        "Always store timestamps in UTC. Local timezone offsets cause bugs.",
        "Store timestamps in local timezone",
        "Convert to UTC before storing",
    )
    conflicting, _ = g._detect_conflict(a, b)
    assert conflicting is False


def test_detect_no_conflict_different_languages() -> None:
    g = Gardener(Path("/tmp"))
    a = _make_constraint(
        "py-commit-001",
        "Never commit inside a loop in Python.",
        "Commit inside a loop",
        "Batch commits outside the loop",
        ast_triggers=["session.commit()"],
        language="python",
    )
    b = _make_constraint(
        "java-commit-001",
        "Always commit at the end of each transaction unit in Java.",
        "Skip committing after transaction units",
        "Commit at transaction boundary",
        ast_triggers=["session.commit()"],
        language="java",
    )
    conflicting, _ = g._detect_conflict(a, b)
    assert conflicting is False


def test_scan_finds_conflict_from_stored_constraints(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    cdir = tmp_path / ".cortex" / "constraints"
    a = _make_constraint(
        "commit-always-001",
        "Always commit after every write.",
        "Skip commit after write",
        "Commit immediately after each write",
        ast_triggers=["db.session.commit()"],
    )
    b = _make_constraint(
        "commit-never-loop-001",
        "Never commit inside a loop.",
        "Commit inside a loop",
        "Batch all writes and commit outside the loop",
        ast_triggers=["db.session.commit()"],
    )
    _write_constraint(cdir, a)
    _write_constraint(cdir, b)

    reports = Gardener(tmp_path).scan()
    assert len(reports) == 1
    ids = {reports[0].constraint_a.constraint_id, reports[0].constraint_b.constraint_id}
    assert ids == {"commit-always-001", "commit-never-loop-001"}


def test_scan_returns_empty_for_non_conflicting_stored(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    cdir = tmp_path / ".cortex" / "constraints"
    _write_constraint(cdir, _make_constraint("no-eval-001", "Never use eval().", "Use eval()", "Use ast.literal_eval()"))
    _write_constraint(cdir, _make_constraint("use-utc-001", "Always use UTC.", "Use local time", "Convert to UTC"))
    assert Gardener(tmp_path).scan() == []


# ── reconcile() ───────────────────────────────────────────────────────────────

def test_reconcile_raises_without_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CORTEX_API_KEY", raising=False)
    monkeypatch.setenv("CORTEX_MODEL", "claude-opus-4-7")

    g = Gardener(tmp_path)
    conflict = ConflictReport(
        constraint_a=_make_constraint("a-001", "Never do A.", "Do A", "Do B"),
        constraint_b=_make_constraint("b-001", "Never do B.", "Do B", "Do A"),
        explanation="test conflict",
    )
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        g.reconcile(conflict)


def test_reconcile_produces_valid_constraint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ensure_cortex_dirs(tmp_path)
    monkeypatch.setenv("CORTEX_MODEL", "test-model")

    duel_text = "A scenario where doing A violates B and vice versa."
    meta_json = json.dumps({
        "constraint_id": "meta-ab-resolution-001",
        "meta_type": "operational_constraint",
        "scope": {"language": "python", "services": [], "ast_triggers": [], "error_codes": []},
        "context": "When both A and B constraints apply simultaneously.",
        "constraint": "Never mix A and B patterns. Always use approach C which satisfies both.",
        "never_do": ["Mix A and B patterns in the same code path"],
        "because": "A and B contradict each other in the shared context",
        "instead": "Use approach C which handles both cases correctly",
        "evidence": [],
        "validation": "Run the integration tests for both A and B scenarios",
        "confidence": 0.75,
        "source": "inferred",
    })

    call_count = [0]

    def mock_create(**kwargs):
        call_count[0] += 1
        resp = MagicMock()
        resp.choices[0].message.content = duel_text if call_count[0] == 1 else meta_json
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    g = Gardener(tmp_path)
    conflict = ConflictReport(
        constraint_a=_make_constraint("a-001", "Never do A.", "Do A", "Do B"),
        constraint_b=_make_constraint("b-001", "Never do B.", "Do B", "Do A"),
        explanation="test conflict",
    )
    with patch.object(g, "_build_llm_client" if hasattr(g, "_build_llm_client") else "_call_text",
                      wraps=g._call_text) as _:
        with patch("gardener.gardener._build_llm_client", return_value=("openai", mock_client)):
            result = g.reconcile(conflict)

    assert result.constraint_id.startswith("meta-ab")
    assert result.source == "inferred"
    assert result.confidence <= 0.75
    assert len(result.never_do) >= 1
    assert conflict.duel_scenario == duel_text
