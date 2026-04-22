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
