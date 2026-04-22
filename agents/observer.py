"""Observer lifecycle placeholder."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ObserverState:
    pid: int


class ObserverManager:
    """Starts and stops the background observer process."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def start(self, log_path: Path) -> ObserverState:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        worker_path = Path(__file__).with_name("observer_worker.py")
        process = subprocess.Popen(
            [sys.executable, str(worker_path), str(log_path), str(self.repo_root)],
            cwd=self.repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return ObserverState(pid=process.pid)

    def stop(self, pid: int) -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
