"""Storage helpers for the local .cortex directory."""

from __future__ import annotations

from pathlib import Path


def ensure_cortex_dirs(repo_root: Path) -> Path:
    cortex_dir = repo_root / ".cortex"
    for relative in ("constraints", "sessions", "archive", "patterns"):
        (cortex_dir / relative).mkdir(parents=True, exist_ok=True)
    return cortex_dir
