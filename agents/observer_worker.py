"""Background observer worker with confidence scoring and real signal sources."""

from __future__ import annotations

import json
import os
import shutil
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from core.events import normalize_correction_event
from core.events import queue_signal
from core.storage import ensure_cortex_dirs
from core.storage import inbox_dir
from core.storage import append_session_record


RUNNING = True
CONFIDENCE_THRESHOLD = 0.70
_POLL_INTERVAL = 1  # seconds


def _handle_signal(signum: int, frame: object) -> None:
    del signum, frame
    global RUNNING
    RUNNING = False


# ── Confidence scoring ─────────────────────────────────────────────────────────

def score_confidence(payload: dict[str, object], base: float) -> float:
    """Adjust base confidence upward based on how complete the signal payload is."""
    score = base
    if payload.get("human_fix"):
        score += 0.05
    evidence = payload.get("evidence", [])
    if isinstance(evidence, list) and len(evidence) > 0:
        score += 0.04
    if payload.get("services"):
        score += 0.03
    if payload.get("context"):
        score += 0.02
    return min(score, 0.97)


# ── Inbox processing ───────────────────────────────────────────────────────────

def drain_event_inbox(log_path: Path, repo_root: Path) -> int:
    """Move queued correction events from the inbox into the session log.

    Signals scoring below CONFIDENCE_THRESHOLD are logged as low_confidence_skip
    and archived separately rather than being distilled.
    """
    ensure_cortex_dirs(repo_root)
    queued_dir = inbox_dir(repo_root)
    processed_dir = repo_root / ".cortex" / "archive" / "events"
    processed_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    for path in sorted(queued_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            normalized = classify_inbox_payload(payload)
        except Exception:
            bad_path = processed_dir / f"{path.stem}.invalid.json"
            shutil.move(str(path), str(bad_path))
            continue

        confidence = float(normalized.get("confidence", 0.0))
        if confidence < CONFIDENCE_THRESHOLD:
            append_session_record(
                log_path,
                {
                    "type": "low_confidence_skip",
                    "event_id": normalized.get("event_id", "unknown"),
                    "confidence": confidence,
                    "threshold": CONFIDENCE_THRESHOLD,
                    "skipped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            skipped_path = processed_dir / f"{path.stem}.skipped.json"
            shutil.move(str(path), str(skipped_path))
            continue

        append_session_record(log_path, normalized)
        archived_path = processed_dir / path.name
        shutil.move(str(path), str(archived_path))
        processed += 1

    return processed


def classify_inbox_payload(payload: dict[str, object]) -> dict[str, object]:
    """Normalize inbox payloads into correction events."""
    if payload.get("type") == "correction_event":
        return normalize_correction_event(payload)
    if payload.get("type") != "correction_signal":
        raise ValueError("Unsupported inbox payload type")
    return classify_signal(payload)


def classify_signal(payload: dict[str, object]) -> dict[str, object]:
    """Convert a correction signal into a correction event with dynamic confidence scoring."""
    kind = payload.get("kind")
    language = str(payload.get("language", "python"))
    services = list(payload.get("services", []))
    evidence = list(payload.get("evidence", []))

    if kind == "deadlock":
        template = _deadlock_template(payload, language, services, evidence)
    elif kind == "token_refresh":
        template = _token_refresh_template(payload, language, services, evidence)
    elif kind == "webhook_signature":
        template = _webhook_signature_template(payload, language, services, evidence)
    elif kind == "git_revert":
        template = _git_revert_template(payload, language, services, evidence)
    elif kind == "git_fix":
        template = _git_fix_template(payload, language, services, evidence)
    elif kind == "test_failure":
        template = _test_failure_template(payload, language, services, evidence)
    else:
        raise ValueError(f"Unsupported correction signal kind: {kind}")

    return normalize_correction_event(template)


# ── Signal templates ───────────────────────────────────────────────────────────

def _deadlock_template(
    payload: dict[str, object],
    language: str,
    services: list[str],
    evidence: list[object],
) -> dict[str, object]:
    return {
        "event_id": "evt-observer-deadlock-001",
        "constraint_key": "db-transaction-payload",
        "sequence": 1,
        "meta_type": "operational_constraint",
        "scope": {
            "language": language,
            "services": services or ["payments-api", "ledger-service"],
            "ast_triggers": ["db.session.commit()", "bulk_insert"],
            "error_codes": ["OperationalError", "deadlock detected"],
        },
        "context": "PostgreSQL transaction handling above 10MB payload",
        "failing_action": "Single transaction for bulk inserts greater than 500 rows against the ledger table",
        "correction": str(payload.get("human_fix", "Chunk inserts into batches of 500 rows before commit.")),
        "because": "Row-level locking causes deadlocks above 10MB payloads in the ledger path",
        "instead": "chunk inserts into batches of at most 500 rows",
        "evidence": evidence,
        "validation": "Run test_bulk_insert_chunking.py with payloads above 10MB",
        "confidence": score_confidence(payload, 0.85),
        "source": "observed",
    }


def _token_refresh_template(
    payload: dict[str, object],
    language: str,
    services: list[str],
    evidence: list[object],
) -> dict[str, object]:
    return {
        "event_id": "evt-observer-token-refresh-001",
        "constraint_key": "auth-token-refresh",
        "sequence": 3,
        "meta_type": "operational_constraint",
        "scope": {
            "language": language,
            "services": services or ["payments-api"],
            "ast_triggers": ["refresh_token()", "db.transaction"],
            "error_codes": ["TimeoutError"],
        },
        "context": "JWT refresh behavior in payment write flows",
        "failing_action": "Call refresh_token() inside a database transaction",
        "correction": str(payload.get("human_fix", "Refresh the token before opening the transaction.")),
        "because": "Token service latency stretches the transaction long enough to trigger timeouts",
        "instead": "refresh the token before opening the transaction",
        "evidence": evidence,
        "validation": "Run the payment write integration test with a forced token refresh",
        "confidence": score_confidence(payload, 0.83),
        "source": "observed",
    }


def _webhook_signature_template(
    payload: dict[str, object],
    language: str,
    services: list[str],
    evidence: list[object],
) -> dict[str, object]:
    return {
        "event_id": "evt-observer-webhook-signature-001",
        "constraint_key": "webhook-signature-order",
        "sequence": 1,
        "meta_type": "workflow_constraint",
        "scope": {
            "language": language,
            "services": services or ["webhooks-gateway"],
            "ast_triggers": ["request.json()", "verify_signature"],
            "error_codes": ["signature mismatch"],
        },
        "context": "Webhook verification flow before payload parsing",
        "failing_action": "Parse the webhook body before verifying the raw-body signature",
        "correction": str(payload.get("human_fix", "Verify the raw body signature before JSON parsing.")),
        "because": "JSON normalization changes the byte stream and invalidates the provider signature",
        "instead": "verify the signature against the raw body before parsing JSON",
        "evidence": evidence,
        "validation": "Run the webhook signature test with the provider sample payload",
        "confidence": score_confidence(payload, 0.82),
        "source": "observed",
    }


def _git_revert_template(
    payload: dict[str, object],
    language: str,
    services: list[str],
    evidence: list[object],
) -> dict[str, object]:
    commit_hash = str(payload.get("commit_hash", "unknown"))[:7]
    original_hash = str(payload.get("original_hash", "unknown"))[:7]
    message = str(payload.get("message", ""))
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "event_id": f"evt-git-revert-{commit_hash}",
        "constraint_key": f"git-revert-{commit_hash}",
        "sequence": 1,
        "meta_type": "operational_constraint",
        "scope": {
            "language": language,
            "services": services,
            "ast_triggers": [],
            "error_codes": [],
        },
        "context": f"Git history: revert of commit {original_hash}",
        "failing_action": f"Apply the approach reverted by commit {commit_hash}: {message[:120]}",
        "correction": str(payload.get("human_fix", f"Review revert commit {commit_hash} before proceeding.")),
        "because": f"Commit {original_hash} was reverted — this approach caused a regression",
        "instead": f"review revert commit {commit_hash} to understand why the approach was reverted",
        "evidence": evidence or [
            {
                "type": "agent_correction",
                "commit_hash": commit_hash,
                "corrected_by": "git_revert",
                "date": date_str,
            }
        ],
        "validation": f"git show {commit_hash}",
        # Base 0.62: scores to ~0.76 with human_fix + evidence, stays below 0.70 without them
        "confidence": score_confidence(payload, 0.62),
        "source": "observed",
    }


def _git_fix_template(
    payload: dict[str, object],
    language: str,
    services: list[str],
    evidence: list[object],
) -> dict[str, object]:
    commit_hash = str(payload.get("commit_hash", "unknown"))[:7]
    message = str(payload.get("message", ""))
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "event_id": f"evt-git-fix-{commit_hash}",
        "constraint_key": f"git-fix-{commit_hash}",
        "sequence": 1,
        "meta_type": "operational_constraint",
        "scope": {
            "language": language,
            "services": services,
            "ast_triggers": [],
            "error_codes": [],
        },
        "context": f"Git history: fix commit {commit_hash}",
        "failing_action": f"Apply the approach that required this fix: {message[:120]}",
        "correction": str(payload.get("human_fix", f"Review fix commit {commit_hash} for constraint details.")),
        "because": f"A fix commit on {date_str} indicates the prior approach had a defect",
        "instead": f"review fix commit {commit_hash} and add human_fix context to promote confidence",
        "evidence": evidence,
        "validation": f"git show {commit_hash}",
        # Base 0.50: needs human_fix + evidence + services to clear 0.70
        "confidence": score_confidence(payload, 0.50),
        "source": "observed",
    }


def _test_failure_template(
    payload: dict[str, object],
    language: str,
    services: list[str],
    evidence: list[object],
) -> dict[str, object]:
    test_ids = list(payload.get("test_ids", []))
    summary = ", ".join(test_ids[:3]) + ("..." if len(test_ids) > 3 else "")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return {
        "event_id": f"evt-test-failure-{ts}",
        "constraint_key": f"test-regression-{ts}",
        "sequence": 1,
        "meta_type": "operational_constraint",
        "scope": {
            "language": language,
            "services": services,
            "ast_triggers": [],
            "error_codes": ["AssertionError", "pytest failure"],
        },
        "context": "Test suite regression detected during session",
        "failing_action": f"Apply code that causes test failures: {summary}",
        "correction": str(payload.get("human_fix", "Fix the failing tests before proceeding.")),
        "because": "Test failures during this session indicate a regression was introduced",
        "instead": "ensure all listed tests pass before committing",
        "evidence": evidence,
        "validation": f"pytest {' '.join(test_ids[:5])}",
        # Base 0.55: needs human_fix + evidence to clear 0.70
        "confidence": score_confidence(payload, 0.55),
        "source": "observed",
    }


# ── Real signal sources ────────────────────────────────────────────────────────

class GitWatcher:
    """Polls .git/logs/HEAD for new commits and queues correction signals."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.reflog_path = repo_root / ".git" / "logs" / "HEAD"
        self._last_byte_offset: int = 0
        self._seen_hashes: set[str] = set()

    def poll(self) -> int:
        """Check for new git events. Returns number of signals queued."""
        if not self.reflog_path.exists():
            return 0

        current_size = self.reflog_path.stat().st_size
        if current_size <= self._last_byte_offset:
            return 0

        lines = self.reflog_path.read_text(encoding="utf-8", errors="replace").splitlines()
        self._last_byte_offset = current_size
        queued = 0

        for line in reversed(lines):
            # Format: <old-sha> <new-sha> Name <email> <ts> <tz>\t<action: message>
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            meta = parts[0].split()
            if len(meta) < 2:
                continue
            new_hash = meta[1]
            null_sha = "0" * 40
            if new_hash in self._seen_hashes or new_hash == null_sha:
                continue
            self._seen_hashes.add(new_hash)

            action_msg = parts[1]
            sig = self._build_signal(new_hash, action_msg)
            if sig:
                queue_signal(self.repo_root, sig)
                queued += 1

        return queued

    def _build_signal(self, commit_hash: str, action_msg: str) -> dict[str, object] | None:
        if not action_msg.startswith("commit:"):
            return None
        msg = action_msg[len("commit:"):].strip()
        msg_lower = msg.lower()

        if msg_lower.startswith("revert ") or 'revert "' in msg_lower:
            return {
                "type": "correction_signal",
                "kind": "git_revert",
                "signal_id": f"git-revert-{commit_hash[:7]}",
                "commit_hash": commit_hash,
                "message": msg,
                "queued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

        fix_prefixes = ("fix:", "hotfix:", "bugfix:", "fix(")
        if any(msg_lower.startswith(p) for p in fix_prefixes):
            return {
                "type": "correction_signal",
                "kind": "git_fix",
                "signal_id": f"git-fix-{commit_hash[:7]}",
                "commit_hash": commit_hash,
                "message": msg,
                "queued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

        return None


class FailureWatcher:
    """Polls .pytest_cache/v/cache/lastfailed for new test failures."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.lastfailed_path = repo_root / ".pytest_cache" / "v" / "cache" / "lastfailed"
        self._last_mtime: float = 0.0
        self._last_failures: set[str] = set()

    def poll(self) -> int:
        """Check for new test failures. Returns number of signals queued."""
        if not self.lastfailed_path.exists():
            return 0

        mtime = self.lastfailed_path.stat().st_mtime
        if mtime <= self._last_mtime:
            return 0
        self._last_mtime = mtime

        try:
            data = json.loads(self.lastfailed_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return 0

        current_failures = set(data.keys())
        new_failures = current_failures - self._last_failures
        self._last_failures = current_failures

        if not new_failures:
            return 0

        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        sig: dict[str, object] = {
            "type": "correction_signal",
            "kind": "test_failure",
            "signal_id": f"test-failure-{ts}",
            "test_ids": sorted(new_failures),
            "queued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        queue_signal(self.repo_root, sig)
        return 1


# ── Background watcher thread ──────────────────────────────────────────────────

def _run_watcher(watcher: GitWatcher | FailureWatcher) -> None:
    while RUNNING:
        try:
            watcher.poll()
        except Exception:
            pass
        time.sleep(_POLL_INTERVAL)


# ── Main loop ──────────────────────────────────────────────────────────────────

def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log_path = Path(sys.argv[1])
    repo_root = Path(sys.argv[2])

    for watcher in (GitWatcher(repo_root), FailureWatcher(repo_root)):
        threading.Thread(target=_run_watcher, args=(watcher,), daemon=True).start()

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
        time.sleep(_POLL_INTERVAL)


if __name__ == "__main__":
    main()
