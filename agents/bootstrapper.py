"""Bootstrapper placeholder implementation."""

from __future__ import annotations

from pathlib import Path


class Bootstrapper:
    """Seeds a new CORTEX library with placeholder data."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def run_initial_bootstrap(self) -> None:
        bootstrap_marker = self.repo_root / ".cortex" / "bootstrap.txt"
        bootstrap_marker.write_text(
            "Bootstrap placeholder created. Replace with PyGit2 history mining.\n",
            encoding="utf-8",
        )
