"""Tests for observer confidence scoring, threshold handling, and real signal sources."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.observer_worker import (
    CONFIDENCE_THRESHOLD,
    FailureWatcher,
    GitWatcher,
    classify_signal,
    drain_event_inbox,
    score_confidence,
)
from core.storage import ensure_cortex_dirs, read_session_records


# ── score_confidence ───────────────────────────────────────────────────────────

def test_score_confidence_returns_base_when_payload_is_bare() -> None:
    result = score_confidence({}, 0.60)
    assert result == 0.60


def test_score_confidence_adds_for_human_fix() -> None:
    result = score_confidence({"human_fix": "do it differently"}, 0.60)
    assert result == 0.65


def test_score_confidence_adds_for_evidence() -> None:
    result = score_confidence({"evidence": [{"type": "production_incident"}]}, 0.60)
    assert result == 0.64


def test_score_confidence_adds_for_services() -> None:
    result = score_confidence({"services": ["payments-api"]}, 0.60)
    assert result == 0.63


def test_score_confidence_compounds_all_bonuses() -> None:
    payload = {
        "human_fix": "fix",
        "evidence": [{"type": "production_incident"}],
        "services": ["svc"],
        "context": "some context",
    }
    result = score_confidence(payload, 0.60)
    assert result == pytest.approx(0.74)  # 0.60 + 0.05 + 0.04 + 0.03 + 0.02


def test_score_confidence_caps_at_0_97() -> None:
    payload = {
        "human_fix": "fix",
        "evidence": [{"type": "x"}],
        "services": ["svc"],
        "context": "ctx",
    }
    result = score_confidence(payload, 0.95)
    assert result == 0.97


# ── Known signal kind confidence ───────────────────────────────────────────────

def test_deadlock_signal_without_enrichment_exceeds_threshold() -> None:
    payload = {"type": "correction_signal", "kind": "deadlock"}
    result = classify_signal(payload)
    assert result["confidence"] >= CONFIDENCE_THRESHOLD


def test_token_refresh_signal_without_enrichment_exceeds_threshold() -> None:
    payload = {"type": "correction_signal", "kind": "token_refresh"}
    result = classify_signal(payload)
    assert result["confidence"] >= CONFIDENCE_THRESHOLD


def test_webhook_signature_signal_without_enrichment_exceeds_threshold() -> None:
    payload = {"type": "correction_signal", "kind": "webhook_signature"}
    result = classify_signal(payload)
    assert result["confidence"] >= CONFIDENCE_THRESHOLD


def test_git_revert_without_enrichment_falls_below_threshold() -> None:
    payload = {
        "type": "correction_signal",
        "kind": "git_revert",
        "commit_hash": "abc1234",
        "message": 'Revert "feat: add bulk import"',
    }
    result = classify_signal(payload)
    assert result["confidence"] < CONFIDENCE_THRESHOLD


def test_git_revert_with_enrichment_exceeds_threshold() -> None:
    payload = {
        "type": "correction_signal",
        "kind": "git_revert",
        "commit_hash": "abc1234",
        "message": 'Revert "feat: add bulk import"',
        "human_fix": "Do not use bulk import for this path",
        "evidence": [{"type": "production_incident", "reference": "INC-001", "date": "2025-01-01"}],
        "services": ["payments-api"],
    }
    result = classify_signal(payload)
    assert result["confidence"] >= CONFIDENCE_THRESHOLD


def test_git_fix_without_enrichment_falls_below_threshold() -> None:
    payload = {
        "type": "correction_signal",
        "kind": "git_fix",
        "commit_hash": "def5678",
        "message": "fix: handle null pointer in payment flow",
    }
    result = classify_signal(payload)
    assert result["confidence"] < CONFIDENCE_THRESHOLD


def test_test_failure_without_enrichment_falls_below_threshold() -> None:
    payload = {
        "type": "correction_signal",
        "kind": "test_failure",
        "test_ids": ["tests/test_payments.py::test_charge"],
    }
    result = classify_signal(payload)
    assert result["confidence"] < CONFIDENCE_THRESHOLD


# ── Threshold enforcement in drain_event_inbox ─────────────────────────────────

def test_drain_skips_low_confidence_signals_and_logs_skip_record(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    log_path = tmp_path / ".cortex" / "sessions" / "test.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")

    inbox = tmp_path / ".cortex" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    # git_revert without enrichment → confidence < 0.70 → should be skipped
    signal = {
        "type": "correction_signal",
        "kind": "git_revert",
        "signal_id": "git-revert-abc1234",
        "commit_hash": "abc1234",
        "message": 'Revert "feat: add bulk import"',
    }
    (inbox / "git-revert-abc1234.json").write_text(json.dumps(signal), encoding="utf-8")

    drained = drain_event_inbox(log_path, tmp_path)

    assert drained == 0
    skip_records = read_session_records(log_path, record_type="low_confidence_skip")
    assert len(skip_records) == 1
    assert skip_records[0]["threshold"] == CONFIDENCE_THRESHOLD
    # File archived with .skipped suffix, not processed normally
    archive = tmp_path / ".cortex" / "archive" / "events"
    skipped_files = list(archive.glob("*.skipped.json"))
    assert len(skipped_files) == 1


def test_drain_accepts_signals_above_threshold(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    log_path = tmp_path / ".cortex" / "sessions" / "test.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")

    inbox = tmp_path / ".cortex" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    # token_refresh with enrichment → confidence >= 0.70 → should be accepted
    signal = {
        "type": "correction_signal",
        "kind": "token_refresh",
        "signal_id": "sig-token-001",
        "human_fix": "Refresh before transaction",
        "evidence": [{"type": "production_incident", "reference": "INC-002", "date": "2025-01-01"}],
        "services": ["payments-api"],
    }
    (inbox / "sig-token-001.json").write_text(json.dumps(signal), encoding="utf-8")

    drained = drain_event_inbox(log_path, tmp_path)

    assert drained == 1
    records = read_session_records(log_path, record_type="correction_event")
    assert len(records) == 1
    assert records[0]["constraint_key"] == "auth-token-refresh"


def test_drain_handles_mix_of_passing_and_skipped_signals(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    log_path = tmp_path / ".cortex" / "sessions" / "test.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")

    inbox = tmp_path / ".cortex" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    high = {
        "type": "correction_signal",
        "kind": "deadlock",
        "signal_id": "sig-deadlock-001",
    }
    low = {
        "type": "correction_signal",
        "kind": "git_fix",
        "signal_id": "git-fix-aaa1234",
        "commit_hash": "aaa1234",
        "message": "fix: null pointer",
    }
    (inbox / "sig-deadlock-001.json").write_text(json.dumps(high), encoding="utf-8")
    (inbox / "git-fix-aaa1234.json").write_text(json.dumps(low), encoding="utf-8")

    drained = drain_event_inbox(log_path, tmp_path)

    assert drained == 1
    skip_records = read_session_records(log_path, record_type="low_confidence_skip")
    assert len(skip_records) == 1


# ── GitWatcher ─────────────────────────────────────────────────────────────────

def _write_reflog(repo_root: Path, lines: list[str]) -> None:
    reflog = repo_root / ".git" / "logs" / "HEAD"
    reflog.parent.mkdir(parents=True, exist_ok=True)
    reflog.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_git_watcher_queues_revert_signal(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    _write_reflog(
        tmp_path,
        [
            "0000000000000000000000000000000000000000 abc1234abc1234abc1234abc1234abc1234abc123 "
            'Dev <dev@x.com> 1700000000 +0000\tcommit: Revert "feat: add bulk import"',
        ],
    )

    watcher = GitWatcher(tmp_path)
    queued = watcher.poll()

    assert queued == 1
    inbox = tmp_path / ".cortex" / "inbox"
    files = list(inbox.glob("git-revert-*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["kind"] == "git_revert"


def test_git_watcher_queues_fix_signal(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    _write_reflog(
        tmp_path,
        [
            "0000000000000000000000000000000000000000 def5678def5678def5678def5678def5678def56 "
            "Dev <dev@x.com> 1700000001 +0000\tcommit: fix: handle null pointer in payment flow",
        ],
    )

    watcher = GitWatcher(tmp_path)
    queued = watcher.poll()

    assert queued == 1
    inbox = tmp_path / ".cortex" / "inbox"
    files = list(inbox.glob("git-fix-*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["kind"] == "git_fix"


def test_git_watcher_ignores_regular_commits(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    _write_reflog(
        tmp_path,
        [
            "0000000000000000000000000000000000000000 abc9999abc9999abc9999abc9999abc9999abc99 "
            "Dev <dev@x.com> 1700000002 +0000\tcommit: feat: add new endpoint",
        ],
    )

    watcher = GitWatcher(tmp_path)
    queued = watcher.poll()

    assert queued == 0


def test_git_watcher_does_not_requeue_seen_hashes(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    line = (
        "0000000000000000000000000000000000000000 abc1234abc1234abc1234abc1234abc1234abc123 "
        'Dev <dev@x.com> 1700000000 +0000\tcommit: Revert "feat: something"'
    )
    _write_reflog(tmp_path, [line])

    watcher = GitWatcher(tmp_path)
    first = watcher.poll()
    second = watcher.poll()

    assert first == 1
    assert second == 0


# ── FailureWatcher ────────────────────────────────────────────────────────────────

def _write_lastfailed(repo_root: Path, failures: dict[str, bool]) -> None:
    cache = repo_root / ".pytest_cache" / "v" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "lastfailed").write_text(json.dumps(failures), encoding="utf-8")


def test_test_watcher_queues_signal_on_new_failures(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    _write_lastfailed(tmp_path, {"tests/test_foo.py::test_bar": True})

    watcher = FailureWatcher(tmp_path)
    queued = watcher.poll()

    assert queued == 1
    inbox = tmp_path / ".cortex" / "inbox"
    files = list(inbox.glob("test-failure-*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["kind"] == "test_failure"
    assert "tests/test_foo.py::test_bar" in payload["test_ids"]


def test_test_watcher_ignores_unchanged_failure_set(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)
    _write_lastfailed(tmp_path, {"tests/test_foo.py::test_bar": True})

    watcher = FailureWatcher(tmp_path)
    watcher.poll()

    # Re-poll without changing the file — same mtime → no new signal
    second = watcher.poll()
    assert second == 0


def test_test_watcher_queues_only_newly_appearing_failures(tmp_path: Path) -> None:
    ensure_cortex_dirs(tmp_path)

    watcher = FailureWatcher(tmp_path)
    _write_lastfailed(tmp_path, {"tests/test_a.py::test_x": True})
    watcher.poll()  # seed the known failures

    # Simulate file update with a new failure
    import time
    time.sleep(0.01)
    _write_lastfailed(
        tmp_path,
        {
            "tests/test_a.py::test_x": True,
            "tests/test_b.py::test_y": True,
        },
    )
    queued = watcher.poll()

    assert queued == 1
    inbox = tmp_path / ".cortex" / "inbox"
    files = sorted(inbox.glob("test-failure-*.json"))
    last_payload = json.loads(files[-1].read_text())
    assert last_payload["test_ids"] == ["tests/test_b.py::test_y"]
