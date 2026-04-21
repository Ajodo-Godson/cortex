"""Simple background observer worker."""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path


RUNNING = True


def _handle_signal(signum: int, frame: object) -> None:
    del signum, frame
    global RUNNING
    RUNNING = False


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log_dir = Path(sys.argv[1])
    heartbeat = log_dir / "observer-heartbeat.log"

    while RUNNING:
        heartbeat.write_text(f"observer alive {int(time.time())}\n", encoding="utf-8")
        time.sleep(1)


if __name__ == "__main__":
    main()
