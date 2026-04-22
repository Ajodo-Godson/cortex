"""Fixture-based Distiller eval harness."""

from __future__ import annotations

import json
from pathlib import Path

from agents.distiller import Distiller
from core.schema import Constraint


FIXTURES = [
    {
        "event_id": "evt-001",
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
    },
    {
        "event_id": "evt-002",
        "constraint_key": "auth-token-refresh",
        "sequence": 3,
        "meta_type": "operational_constraint",
        "scope": {
            "language": "python",
            "services": ["payments-api"],
            "ast_triggers": ["refresh_token()", "db.transaction"],
            "error_codes": ["TimeoutError"],
        },
        "context": "JWT refresh behavior in payment write flows",
        "failing_action": "Call refresh_token() inside a database transaction",
        "correction": "Refresh the token before opening the transaction",
        "because": "Token service latency stretches the transaction long enough to trigger timeouts",
        "instead": "refresh the token before opening the transaction",
        "evidence": [{"type": "agent_correction", "commit_hash": "c0ffee1", "corrected_by": "human", "date": "2025-02-21"}],
        "validation": "Run the payment write integration test with a forced token refresh",
        "confidence": 0.93,
        "source": "observed",
    },
    {
        "event_id": "evt-003",
        "constraint_key": "python-async-context-manager",
        "sequence": 2,
        "meta_type": "workflow_constraint",
        "scope": {
            "language": "python",
            "services": ["jobs-worker"],
            "ast_triggers": ["async with", "get_client()"],
            "error_codes": ["ResourceWarning"],
        },
        "context": "Async client lifecycle in background workers",
        "failing_action": "Instantiate the async client without an async context manager in the worker loop",
        "correction": "Wrap the client in async with before making network calls",
        "because": "Skipping the async context manager leaks connections across long-running jobs",
        "instead": "wrap the client in async with before making network calls",
        "evidence": [{"type": "agent_correction", "commit_hash": "f3a1b9c", "corrected_by": "human", "date": "2025-03-12"}],
        "validation": "Run the worker integration suite and confirm there are no ResourceWarning entries",
        "confidence": 0.91,
        "source": "observed",
    },
    {
        "event_id": "evt-004",
        "constraint_key": "react-stale-closure",
        "sequence": 1,
        "meta_type": "architectural_constraint",
        "scope": {
            "language": "typescript",
            "services": ["web-app"],
            "ast_triggers": ["setInterval", "useEffect"],
            "error_codes": ["stale state"],
        },
        "context": "Polling callbacks in React dashboard widgets",
        "failing_action": "Capture mutable dashboard state inside a long-lived interval callback",
        "correction": "Read fresh state through an effect event instead of the stale closure",
        "because": "The interval keeps the original closure and renders stale values after the first update",
        "instead": "read fresh state through an effect event instead of the stale closure",
        "evidence": [{"type": "agent_correction", "commit_hash": "9ab12cd", "corrected_by": "human", "date": "2025-04-02"}],
        "validation": "Run the dashboard polling test and confirm widget counts update after state changes",
        "confidence": 0.89,
        "source": "observed",
    },
    {
        "event_id": "evt-005",
        "constraint_key": "redis-cache-stampede",
        "sequence": 1,
        "meta_type": "operational_constraint",
        "scope": {
            "language": "python",
            "services": ["pricing-api"],
            "ast_triggers": ["cache.get", "cache.set"],
            "error_codes": ["429"],
        },
        "context": "High-traffic pricing cache refresh behavior",
        "failing_action": "Let multiple requests regenerate the same missing cache key concurrently",
        "correction": "Use a single-flight lock around cache regeneration",
        "because": "Concurrent misses stampede the upstream pricing service and trigger rate limits",
        "instead": "use a single-flight lock around cache regeneration",
        "evidence": [{"type": "production_incident", "reference": "INC-2025-014", "date": "2025-01-18"}],
        "validation": "Load test the cold-cache path and verify only one upstream regeneration occurs per key",
        "confidence": 0.95,
        "source": "observed",
    },
    {
        "event_id": "evt-006",
        "constraint_key": "s3-stream-close",
        "sequence": 1,
        "meta_type": "workflow_constraint",
        "scope": {
            "language": "python",
            "services": ["ingest-service"],
            "ast_triggers": ["boto3.client", "upload_fileobj"],
            "error_codes": ["TooManyOpenFiles"],
        },
        "context": "Temporary upload stream handling during ingest jobs",
        "failing_action": "Leave temporary upload streams open after S3 upload completes",
        "correction": "Close the stream in a finally block after upload",
        "because": "Open file handles accumulate across batch jobs and exhaust the worker process limit",
        "instead": "close the stream in a finally block after upload",
        "evidence": [{"type": "agent_correction", "commit_hash": "abc1234", "corrected_by": "human", "date": "2025-02-08"}],
        "validation": "Run the ingest batch test and verify open file descriptors stay flat",
        "confidence": 0.9,
        "source": "observed",
    },
    {
        "event_id": "evt-007",
        "constraint_key": "payments-idempotency-key",
        "sequence": 1,
        "meta_type": "operational_constraint",
        "scope": {
            "language": "python",
            "services": ["payments-api"],
            "ast_triggers": ["create_charge", "idempotency_key"],
            "error_codes": ["duplicate charge"],
        },
        "context": "Outbound payment creation retries",
        "failing_action": "Retry charge creation without reusing the original idempotency key",
        "correction": "Persist and reuse the same idempotency key across retries",
        "because": "Fresh keys turn safe retries into duplicate charges at the payment processor",
        "instead": "persist and reuse the same idempotency key across retries",
        "evidence": [{"type": "production_incident", "reference": "INC-2025-022", "date": "2025-02-02"}],
        "validation": "Run the retry integration test and confirm only one processor charge is created",
        "confidence": 0.97,
        "source": "observed",
    },
    {
        "event_id": "evt-008",
        "constraint_key": "webhook-signature-order",
        "sequence": 1,
        "meta_type": "workflow_constraint",
        "scope": {
            "language": "python",
            "services": ["webhooks-gateway"],
            "ast_triggers": ["request.json()", "verify_signature"],
            "error_codes": ["signature mismatch"],
        },
        "context": "Webhook verification flow before payload parsing",
        "failing_action": "Parse the webhook body before verifying the raw-body signature",
        "correction": "Verify the signature against the raw body before parsing JSON",
        "because": "JSON normalization changes the byte stream and invalidates the provider signature",
        "instead": "verify the signature against the raw body before parsing JSON",
        "evidence": [{"type": "agent_correction", "commit_hash": "feedbee", "corrected_by": "human", "date": "2025-03-22"}],
        "validation": "Run the webhook signature test with the provider sample payload",
        "confidence": 0.92,
        "source": "observed",
    },
    {
        "event_id": "evt-009",
        "constraint_key": "feature-flag-default",
        "sequence": 1,
        "meta_type": "architectural_constraint",
        "scope": {
            "language": "typescript",
            "services": ["admin-console"],
            "ast_triggers": ["isFlagEnabled", "defaultValue"],
            "error_codes": ["silent enablement"],
        },
        "context": "Feature flag evaluation for unreleased admin features",
        "failing_action": "Default missing admin feature flags to enabled",
        "correction": "Default missing admin feature flags to disabled",
        "because": "Missing flag configuration should fail closed or unreleased features leak into production",
        "instead": "default missing admin feature flags to disabled",
        "evidence": [{"type": "agent_correction", "commit_hash": "456def7", "corrected_by": "human", "date": "2025-04-09"}],
        "validation": "Run the feature flag unit suite with absent configuration values",
        "confidence": 0.88,
        "source": "observed",
    },
    {
        "event_id": "evt-010",
        "constraint_key": "sql-migration-lock",
        "sequence": 1,
        "meta_type": "operational_constraint",
        "scope": {
            "language": "sql",
            "services": ["ledger-db"],
            "ast_triggers": ["ALTER TABLE", "UPDATE"],
            "error_codes": ["lock timeout"],
        },
        "context": "Large ledger backfill migrations on production tables",
        "failing_action": "Backfill an entire hot table in a single write-heavy migration",
        "correction": "Split the backfill into small batches scheduled outside peak traffic",
        "because": "Long-running write locks on the ledger table block live traffic and trigger lock timeouts",
        "instead": "split the backfill into small batches scheduled outside peak traffic",
        "evidence": [{"type": "production_incident", "reference": "INC-2025-030", "date": "2025-03-04"}],
        "validation": "Run the migration on a production-sized clone and verify lock wait stays below the threshold",
        "confidence": 0.96,
        "source": "observed",
    },
]


def test_distiller_emits_schema_valid_constraints_for_ground_truth_events() -> None:
    distiller = Distiller(Path.cwd())

    constraints = [distiller.distill_event(fixture) for fixture in FIXTURES]

    assert len(constraints) == 10
    for fixture, constraint in zip(FIXTURES, constraints):
        assert isinstance(constraint, Constraint)
        assert constraint.constraint_id == f"{fixture['constraint_key']}-{fixture['sequence']:03d}"
        assert constraint.context == fixture["context"]
        assert constraint.never_do == [fixture["failing_action"]]
        assert constraint.because == fixture["because"]
        assert constraint.instead == fixture["instead"]
        assert constraint.validation == fixture["validation"]
        assert constraint.confidence == fixture["confidence"]
        assert constraint.scope.language == fixture["scope"]["language"]
        assert constraint.scope.services == fixture["scope"]["services"]
        assert fixture["because"] in constraint.constraint
        assert "```" not in constraint.constraint


def test_distiller_run_distills_json_log_lines_into_archive_output(tmp_path: Path) -> None:
    repo_root = tmp_path
    archive_dir = repo_root / ".cortex" / "archive"
    archive_dir.mkdir(parents=True)
    log_path = repo_root / ".cortex" / "sessions.log"
    log_path.write_text(
        "\n".join(
            [
                "not-json",
                json.dumps(FIXTURES[0]),
                json.dumps(FIXTURES[1]),
            ]
        ),
        encoding="utf-8",
    )

    result = Distiller(repo_root).run(log_path)

    assert result.correction_events == 2
    assert result.new_constraints == 2
    archive_path = archive_dir / "sessions.distilled"
    assert archive_path.exists()
    rendered = archive_path.read_text(encoding="utf-8")
    assert "db-transaction-payload-001" in rendered
    assert "auth-token-refresh-003" in rendered
