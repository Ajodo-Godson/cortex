"""Basic CLI lifecycle tests."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from cli.main import main


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
        assert (repo_root / "CORTEX.md").exists()
        assert (repo_root / ".cortex" / "session.lock").exists()

        status_result = runner.invoke(main, ["status"])
        assert status_result.exit_code == 0
        assert "Active session since:" in status_result.output

        stop_result = runner.invoke(main, ["stop"])
        assert stop_result.exit_code == 0
        assert not (repo_root / "CORTEX.md").exists()
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
