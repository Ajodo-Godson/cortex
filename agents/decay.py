"""Constraint Decay: detects stale constraints and decreases their confidence."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from core.schema import Constraint
from core.storage import load_constraints, save_constraint


@dataclass
class DecayReport:
    constraint: Constraint
    missing_triggers: list[str]
    drift_ratio: float          # fraction of ast_triggers no longer found in codebase
    original_confidence: float
    new_confidence: float
    routed_to_gardener: bool = field(default=False)


class ConstraintDecay:
    """Scans the codebase for ast_triggers that no longer exist.

    For each constraint:
    - If all triggers are still present: no change.
    - If some are missing: confidence decreases proportionally to drift.
    - If all are missing: constraint is flagged for Gardener review.

    No changes are written unless apply() is called.
    """

    # Confidence drops by this fraction per fully-missing trigger
    _DECAY_PER_MISSING = 0.10
    # Constraints below this threshold are routed to the Gardener
    _GARDENER_THRESHOLD = 0.50

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def scan(self) -> list[DecayReport]:
        """Return decay reports for all constraints with stale ast_triggers."""
        constraints = load_constraints(self.repo_root)
        source_files = self._get_source_files()
        reports = []
        for constraint in constraints:
            report = self._check_constraint(constraint, source_files)
            if report is not None:
                reports.append(report)
        return reports

    def apply(self, reports: list[DecayReport]) -> None:
        """Write updated confidence values back to the constraint library."""
        for report in reports:
            updated = report.constraint.model_copy(
                update={"confidence": report.new_confidence}
            )
            save_constraint(self.repo_root, updated)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _check_constraint(
        self, constraint: Constraint, source_files: list[Path]
    ) -> DecayReport | None:
        triggers = constraint.scope.ast_triggers
        if not triggers:
            return None

        missing = [t for t in triggers if not self._trigger_exists(t, source_files)]
        if not missing:
            return None

        drift_ratio = len(missing) / len(triggers)
        decay = self._DECAY_PER_MISSING * len(missing)
        new_confidence = max(0.0, round(constraint.confidence - decay, 4))
        routed = new_confidence < self._GARDENER_THRESHOLD

        return DecayReport(
            constraint=constraint,
            missing_triggers=missing,
            drift_ratio=drift_ratio,
            original_confidence=constraint.confidence,
            new_confidence=new_confidence,
            routed_to_gardener=routed,
        )

    def _trigger_exists(self, pattern: str, source_files: list[Path]) -> bool:
        """Return True if pattern appears in any source file."""
        for path in source_files:
            try:
                if pattern in path.read_text(encoding="utf-8", errors="ignore"):
                    return True
            except OSError:
                pass
        return False

    def _get_source_files(self) -> list[Path]:
        """Return all tracked source files in the repo."""
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo_root), "ls-files"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if result.returncode != 0:
                return list(self.repo_root.rglob("*.py"))
            files = []
            for name in result.stdout.splitlines():
                name = name.strip()
                if name:
                    full = self.repo_root / name
                    if full.exists() and full.is_file():
                        files.append(full)
            return files
        except Exception:
            return list(self.repo_root.rglob("*.py"))
