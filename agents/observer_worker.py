"""Simple background observer worker."""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from core.storage import append_session_record


RUNNING = True


def _handle_signal(signum: int, frame: object) -> None:
    del signum, frame
    global RUNNING
    RUNNING = False


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log_path = Path(sys.argv[1])

    while RUNNING:
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
