"""Simple background observer worker."""

from __future__ import annotations

import json
import os
import shutil
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from core.events import normalize_correction_event
from core.storage import ensure_cortex_dirs
from core.storage import inbox_dir
from core.storage import append_session_record


RUNNING = True


def _handle_signal(signum: int, frame: object) -> None:
    del signum, frame
    global RUNNING
    RUNNING = False


def drain_event_inbox(log_path: Path, repo_root: Path) -> int:
    """Move queued correction events from the inbox into the session log."""
    ensure_cortex_dirs(repo_root)
    queued_dir = inbox_dir(repo_root)
    processed_dir = repo_root / ".cortex" / "archive" / "events"
    processed_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    for path in sorted(queued_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            normalized = normalize_correction_event(payload)
        except Exception:
            bad_path = processed_dir / f"{path.stem}.invalid.json"
            shutil.move(str(path), str(bad_path))
            continue

        append_session_record(log_path, normalized)
        archived_path = processed_dir / path.name
        shutil.move(str(path), str(archived_path))
        processed += 1
    return processed


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log_path = Path(sys.argv[1])
    repo_root = Path(sys.argv[2])

    while RUNNING:
        drained = drain_event_inbox(log_path, repo_root)
        if drained:
            append_session_record(
                log_path,
                {
                    "type": "observer_ingest",
                    "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "pid": os.getpid(),
                    "events_ingested": drained,
                },
            )
        append_session_record(
            log_path,
            {
                "type": "observer_heartbeat",
                "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "pid": os.getpid(),
            },
        )
        time.sleep(1)


if __name__ == "__main__":
    main()
