"""Deterministic first-pass Distiller implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.schema import Constraint
from core.schema import CorrectionEvent
from core.storage import constraint_path
from core.storage import save_constraint


@dataclass
class DistillResult:
    correction_events: int
    new_constraints: int
    updated_constraints: int


class Distiller:
    """Turns correction events into structured constraints."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def distill_event(self, event: CorrectionEvent | dict[str, object]) -> Constraint:
        """Convert a correction event into a validated constraint."""
        parsed_event = event if isinstance(event, CorrectionEvent) else CorrectionEvent.model_validate(event)
        evidence = parsed_event.evidence or []

        return Constraint(
            constraint_id=parsed_event.constraint_id,
            meta_type=parsed_event.meta_type,
            scope=parsed_event.scope,
            context=parsed_event.context,
            constraint=self._build_constraint_text(parsed_event),
            never_do=[parsed_event.failing_action],
            because=parsed_event.because,
            instead=parsed_event.instead,
            evidence=evidence,
            validation=parsed_event.validation,
            confidence=parsed_event.confidence,
            last_validated=parsed_event.last_validated,
            source=parsed_event.source,
        )

    def distill_events(self, events: list[CorrectionEvent | dict[str, object]]) -> list[Constraint]:
        return [self.distill_event(event) for event in events]

    def run(self, log_path: Path | str) -> DistillResult:
        """Distill newline-delimited JSON correction events from a session log."""
        log_path = Path(log_path)
        archive_path = self.repo_root / ".cortex" / "archive" / f"{log_path.stem}.distilled"
        constraints = self._distill_log_file(log_path)
        new_constraints = 0
        updated_constraints = 0
        for constraint in constraints:
            existing_path = constraint_path(self.repo_root, constraint.constraint_id)
            existed = existing_path.exists()
            save_constraint(self.repo_root, constraint)
            if existed:
                updated_constraints += 1
            else:
                new_constraints += 1
        rendered = [constraint.model_dump(mode="json") for constraint in constraints]
        archive_path.write_text(json.dumps(rendered, indent=2), encoding="utf-8")
        return DistillResult(
            correction_events=len(constraints),
            new_constraints=new_constraints,
            updated_constraints=updated_constraints,
        )

    def _distill_log_file(self, log_path: Path) -> list[Constraint]:
        constraints: list[Constraint] = []
        if not log_path.exists():
            return constraints

        for line in log_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if payload.get("type") not in (None, "correction_event"):
                continue
            constraints.append(self.distill_event(payload))
        return constraints

    def _build_constraint_text(self, event: CorrectionEvent) -> str:
        return (
            f"{event.failing_action}. {event.because}. "
            f"Always {event.instead.lower()}."
        )
