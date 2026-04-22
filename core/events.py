"""Helpers for writing validated correction events to session logs."""

from __future__ import annotations

import json
from pathlib import Path

from core.schema import CorrectionEvent
from core.storage import inbox_dir
from core.storage import append_session_record


def normalize_correction_event(event: CorrectionEvent | dict[str, object]) -> dict[str, object]:
    """Validate and normalize a correction event payload for log storage."""
    parsed = event if isinstance(event, CorrectionEvent) else CorrectionEvent.model_validate(event)
    payload = parsed.model_dump(mode="json")
    payload["type"] = "correction_event"
    return payload


def append_correction_event(log_path: Path, event: CorrectionEvent | dict[str, object]) -> dict[str, object]:
    """Append a validated correction event to a session log."""
    payload = normalize_correction_event(event)
    append_session_record(log_path, payload)
    return payload


def queue_correction_event(repo_root: Path, event: CorrectionEvent | dict[str, object]) -> Path:
    """Queue a validated correction event for the observer to ingest."""
    payload = normalize_correction_event(event)
    path = inbox_dir(repo_root) / f"{payload['event_id']}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
