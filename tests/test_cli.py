"""Basic CLI lifecycle tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

from click.testing import CliRunner

from agents.observer_worker import classify_signal
from agents.observer_worker import drain_event_inbox
from cli.main import main
from core.storage import read_session_records


def _init_fake_git_repo(repo_root: Path) -> None:
    git_dir = repo_root / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")


def test_start_dry_run_prints_cortex_markdown() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        repo_root = Path.cwd()
        _init_fake_git_repo(repo_root)

        result = runner.invoke(main, ["start", "--dry-run", "--no-bootstrap"])

        assert result.exit_code == 0
        assert "CORTEX - Active Constraints for This Session" in result.output
        assert "Dry run complete" in result.output


def test_start_and_stop_session() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        repo_root = Path.cwd()
        _init_fake_git_repo(repo_root)

        start_result = runner.invoke(main, ["start", "--no-bootstrap"])
        assert start_result.exit_code == 0
        assert (repo_root / "CLAUDE.md").exists()
        assert (repo_root / ".cortex" / "session.lock").exists()

        status_result = runner.invoke(main, ["status"])
        assert status_result.exit_code == 0
        assert "Active session since:" in status_result.output

        stop_result = runner.invoke(main, ["stop"])
        assert stop_result.exit_code == 0
        assert not (repo_root / "CLAUDE.md").exists()
        assert not (repo_root / ".cortex" / "session.lock").exists()


def test_double_start_fails_when_session_is_active() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        repo_root = Path.cwd()
        _init_fake_git_repo(repo_root)

        first_start = runner.invoke(main, ["start", "--no-bootstrap"])
        assert first_start.exit_code == 0

        second_start = runner.invoke(main, ["start", "--no-bootstrap"])
        assert second_start.exit_code != 0
        assert "already active" in second_start.output

        stop_result = runner.invoke(main, ["stop"])
        assert stop_result.exit_code == 0


def test_start_reports_orphaned_session_when_observer_is_gone() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        repo_root = Path.cwd()
        _init_fake_git_repo(repo_root)
        cortex_dir = repo_root / ".cortex"
        (cortex_dir / "sessions").mkdir(parents=True, exist_ok=True)

        lock_payload = {
            "pid": 999999,
            "observer_pid": 999999,
            "started_at": "2026-04-21T21:21:57Z",
            "repo_path": str(repo_root),
            "log_path": str(cortex_dir / "sessions" / "stale.log"),
        }
        (cortex_dir / "session.lock").write_text(json.dumps(lock_payload), encoding="utf-8")

        result = runner.invoke(main, ["start", "--no-bootstrap"])
        assert result.exit_code == 0
        assert "Previous session ended without 'cortex stop'" in result.output
        assert (cortex_dir / "session.lock").exists()

        stop_result = runner.invoke(main, ["stop"])
        assert stop_result.exit_code == 0


def test_status_reports_stale_session_lock() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        repo_root = Path.cwd()
        _init_fake_git_repo(repo_root)
        cortex_dir = repo_root / ".cortex"
        (cortex_dir / "sessions").mkdir(parents=True, exist_ok=True)

        lock_payload = {
            "pid": 999999,
            "observer_pid": 999999,
            "started_at": "2026-04-21T21:21:57Z",
            "repo_path": str(repo_root),
            "log_path": str(cortex_dir / "sessions" / "stale.log"),
        }
        (cortex_dir / "session.lock").write_text(json.dumps(lock_payload), encoding="utf-8")

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "Stale session lock detected from:" in result.output
        assert "(not running)" in result.output


def test_manual_distill_with_sample_writes_constraint_library(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path
    _init_fake_git_repo(repo_root)
    log_path = repo_root / ".cortex" / "sessions" / "manual.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")

    result = runner.invoke(main, ["distill", "--log", str(log_path), "--sample"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Correction events detected: 1" in result.output
    constraint_path = repo_root / ".cortex" / "constraints" / "db-transaction-payload-001.yaml"
    assert constraint_path.exists()


def test_constraints_filter_and_show_use_stored_library(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path
    _init_fake_git_repo(repo_root)
    log_path = repo_root / ".cortex" / "sessions" / "manual.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")

    distill_result = runner.invoke(main, ["distill", "--log", str(log_path), "--sample"], catch_exceptions=False)
    assert distill_result.exit_code == 0

    constraints_result = runner.invoke(
        main,
        ["constraints", "--filter", "payments-api"],
        catch_exceptions=False,
    )
    assert constraints_result.exit_code == 0
    assert "db-transaction-payload-001" in constraints_result.output

    show_result = runner.invoke(main, ["show", "db-transaction-payload-001"], catch_exceptions=False)
    assert show_result.exit_code == 0
    assert "meta_type: operational_constraint" in show_result.output
    assert "context: PostgreSQL transaction handling above 10MB payload" in show_result.output


def test_record_sample_then_distill_uses_validated_event_path(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path
    _init_fake_git_repo(repo_root)
    log_path = repo_root / ".cortex" / "sessions" / "manual.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")

    record_result = runner.invoke(main, ["record", "--log", str(log_path), "--sample"], catch_exceptions=False)
    assert record_result.exit_code == 0
    assert "Recorded correction event:" in record_result.output

    distill_result = runner.invoke(main, ["distill", "--log", str(log_path)], catch_exceptions=False)
    assert distill_result.exit_code == 0
    assert "Correction events detected: 1" in distill_result.output
    constraint_path = repo_root / ".cortex" / "constraints" / "db-transaction-payload-001.yaml"
    assert constraint_path.exists()


def test_record_queue_then_observer_drain_writes_correction_event_to_session_log(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path
    _init_fake_git_repo(repo_root)
    previous_cwd = Path.cwd()
    os.chdir(repo_root)
    try:
        record_result = runner.invoke(main, ["record", "--sample", "--queue"], catch_exceptions=False)
        assert record_result.exit_code != 0

        start_result = runner.invoke(main, ["start", "--no-bootstrap"], catch_exceptions=False)
        assert start_result.exit_code == 0

        queue_result = runner.invoke(main, ["record", "--sample", "--queue"], catch_exceptions=False)
        assert queue_result.exit_code == 0
        assert "Queued correction event:" in queue_result.output

        session_logs = sorted((repo_root / ".cortex" / "sessions").glob("*.log"))
        assert session_logs

        drained = drain_event_inbox(session_logs[-1], repo_root)
        assert drained == 1

        records = read_session_records(session_logs[-1], record_type="correction_event")
        assert len(records) == 1
        assert records[0]["event_id"] == "evt-sample-001"

        stop_result = runner.invoke(main, ["stop"], catch_exceptions=False)
        assert stop_result.exit_code == 0
    finally:
        os.chdir(previous_cwd)


def test_signal_queue_then_observer_drain_classifies_into_correction_event(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path
    _init_fake_git_repo(repo_root)
    previous_cwd = Path.cwd()
    os.chdir(repo_root)
    try:
        start_result = runner.invoke(main, ["start", "--no-bootstrap"], catch_exceptions=False)
        assert start_result.exit_code == 0

        signal_result = runner.invoke(main, ["signal", "--sample", "token_refresh"], catch_exceptions=False)
        assert signal_result.exit_code == 0
        assert "Queued observer signal:" in signal_result.output

        session_logs = sorted((repo_root / ".cortex" / "sessions").glob("*.log"))
        assert session_logs
        drained = drain_event_inbox(session_logs[-1], repo_root)
        assert drained == 1

        records = read_session_records(session_logs[-1], record_type="correction_event")
        assert len(records) == 1
        assert records[0]["constraint_key"] == "auth-token-refresh"

        stop_result = runner.invoke(main, ["stop"], catch_exceptions=False)
        assert stop_result.exit_code == 0
    finally:
        os.chdir(previous_cwd)


def test_classify_signal_maps_supported_kinds_to_valid_correction_events() -> None:
    payload = {
        "type": "correction_signal",
        "signal_id": "sig-001",
        "kind": "webhook_signature",
        "language": "python",
        "services": ["webhooks-gateway"],
        "human_fix": "Verify the raw body signature before JSON parsing.",
        "evidence": [{"type": "agent_correction", "commit_hash": "feedbee", "corrected_by": "human", "date": "2025-03-22"}],
    }

    normalized = classify_signal(payload)

    assert normalized["type"] == "correction_event"
    assert normalized["constraint_key"] == "webhook-signature-order"
    assert normalized["scope"]["services"] == ["webhooks-gateway"]
