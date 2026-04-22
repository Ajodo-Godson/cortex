"""Session state and orphan detection."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from core.storage import ensure_cortex_dirs


@dataclass
class SessionState:
    pid: int
    observer_pid: int
    started_at: str
    repo_path: str
    log_path: str

    @property
    def log_path_obj(self) -> Path:
        return Path(self.log_path)


class SessionManager:
    """Manage the local CORTEX session lock file."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.cortex_dir = repo_root / ".cortex"
        self.lock_path = self.cortex_dir / "session.lock"

    def is_git_repo(self) -> bool:
        return (self.repo_root / ".git").exists()

    def get_branch_name(self) -> str:
        head_path = self.repo_root / ".git" / "HEAD"
        if not head_path.exists():
            return "unknown"
        head = head_path.read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            return head.rsplit("/", maxsplit=1)[-1]
        return head[:7]

    def load_active_session(self) -> SessionState | None:
        if not self.lock_path.exists():
            return None
        data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        return SessionState(**data)

    def is_session_active(self, session: SessionState | None = None) -> bool:
        if session is None:
            session = self.load_active_session()
        if session is None:
            return False
        return self._pid_exists(session.observer_pid)

    def detect_orphaned_session(self) -> SessionState | None:
        session = self.load_active_session()
        if session is None:
            return None
        if self.is_session_active(session):
            return None
        return session

    def clear_stale_session(self, session: SessionState | None = None) -> None:
        if session is None:
            session = self.load_active_session()
        if session is None:
            return
        if self.is_session_active(session):
            raise RuntimeError("Cannot clear an active CORTEX session.")

        cortex_md_path = self.repo_root / "CORTEX.md"
        if cortex_md_path.exists():
            cortex_md_path.unlink()
        self.end_session()

    def start_session(self, observer_pid: int) -> SessionState:
        active = self.load_active_session()
        if self.is_session_active(active):
            raise RuntimeError("A CORTEX session is already active in this repo.")

        ensure_cortex_dirs(self.repo_root)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        session_name = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
        log_path = self.cortex_dir / "sessions" / f"{session_name}.log"
        log_path.write_text("session started\n", encoding="utf-8")
        session = SessionState(
            pid=os.getpid(),
            observer_pid=observer_pid,
            started_at=timestamp,
            repo_path=str(self.repo_root),
            log_path=str(log_path),
        )
        self.lock_path.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
        return session

    def end_session(self) -> None:
        if self.lock_path.exists():
            self.lock_path.unlink()

    def _pid_exists(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
