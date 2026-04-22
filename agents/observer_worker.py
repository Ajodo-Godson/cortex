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
            normalized = classify_inbox_payload(payload)
        except Exception:
            bad_path = processed_dir / f"{path.stem}.invalid.json"
            shutil.move(str(path), str(bad_path))
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
    """Convert a simple correction signal into a full correction event."""
    kind = payload.get("kind")
    language = str(payload.get("language", "python"))
    services = list(payload.get("services", []))
    evidence = list(payload.get("evidence", []))

    templates: dict[str, dict[str, object]] = {
        "deadlock": {
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
            "confidence": 0.94,
            "source": "observed",
        },
        "token_refresh": {
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
            "confidence": 0.93,
            "source": "observed",
        },
        "webhook_signature": {
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
            "confidence": 0.92,
            "source": "observed",
        },
    }
    if kind not in templates:
        raise ValueError(f"Unsupported correction signal kind: {kind}")
    return normalize_correction_event(templates[kind])


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
