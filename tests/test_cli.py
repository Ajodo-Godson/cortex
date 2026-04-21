"""Basic CLI lifecycle tests."""

from __future__ import annotations

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
