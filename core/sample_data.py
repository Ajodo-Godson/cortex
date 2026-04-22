"""Sample correction events for CLI smoke tests and demos."""

from __future__ import annotations


def sample_correction_event() -> dict[str, object]:
    return {
        "type": "correction_event",
        "event_id": "evt-sample-001",
        "constraint_key": "db-transaction-payload",
        "sequence": 1,
        "meta_type": "operational_constraint",
        "scope": {
            "language": "python",
            "services": ["payments-api", "ledger-service"],
            "ast_triggers": ["db.session.commit()", "bulk_insert"],
            "error_codes": ["OperationalError", "deadlock detected"],
        },
        "context": "PostgreSQL transaction handling above 10MB payload",
        "failing_action": "Single transaction for bulk inserts greater than 500 rows against the ledger table",
        "correction": "Chunk inserts into batches of 500",
        "because": "Row-level locking causes deadlocks above 10MB payloads in the ledger path",
        "instead": "chunk inserts into batches of at most 500 rows",
        "evidence": [{"type": "production_incident", "reference": "INC-2024-089", "date": "2024-11-14"}],
        "validation": "Run test_bulk_insert_chunking.py with payloads above 10MB",
        "confidence": 0.94,
        "source": "observed",
    }


def sample_correction_signal(kind: str = "deadlock") -> dict[str, object]:
    """Return a simple observer-facing correction signal for demos."""
    signals: dict[str, dict[str, object]] = {
        "deadlock": {
            "type": "correction_signal",
            "signal_id": "sig-sample-deadlock-001",
            "kind": "deadlock",
            "language": "python",
            "services": ["payments-api", "ledger-service"],
            "summary": "Bulk insert deadlocked in ledger path after the agent wrapped 1200 rows in one transaction.",
            "human_fix": "Chunk inserts into batches of 500 rows before commit.",
            "evidence": [{"type": "production_incident", "reference": "INC-2024-089", "date": "2024-11-14"}],
        },
        "token_refresh": {
            "type": "correction_signal",
            "signal_id": "sig-sample-token-refresh-001",
            "kind": "token_refresh",
            "language": "python",
            "services": ["payments-api"],
            "summary": "The write transaction timed out because refresh_token() ran inside the transaction block.",
            "human_fix": "Refresh the token before opening the transaction.",
            "evidence": [{"type": "agent_correction", "commit_hash": "c0ffee1", "corrected_by": "human", "date": "2025-02-21"}],
        },
        "webhook_signature": {
            "type": "correction_signal",
            "signal_id": "sig-sample-webhook-001",
            "kind": "webhook_signature",
            "language": "python",
            "services": ["webhooks-gateway"],
            "summary": "Webhook verification failed after the body was parsed before the raw signature check.",
            "human_fix": "Verify the raw body signature before JSON parsing.",
            "evidence": [{"type": "agent_correction", "commit_hash": "feedbee", "corrected_by": "human", "date": "2025-03-22"}],
        },
    }
    if kind not in signals:
        raise ValueError(f"Unknown sample correction signal kind: {kind}")
    return signals[kind]
