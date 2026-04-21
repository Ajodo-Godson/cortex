"""Distiller placeholder implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DistillResult:
    correction_events: int
    new_constraints: int
    updated_constraints: int


class Distiller:
    """Turns session logs into constraints."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def run(self, log_path: Path | str) -> DistillResult:
        log_path = Path(log_path)
        archive_path = self.repo_root / ".cortex" / "archive" / f"{log_path.stem}.distilled"
        archive_path.write_text(
            f"Distillation placeholder for session log: {log_path.name}\n",
            encoding="utf-8",
        )
        return DistillResult(correction_events=0, new_constraints=0, updated_constraints=0)
