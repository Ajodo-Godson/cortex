"""L1 AST fast-filter: calls the Rust binary to find ast_trigger matches in touched files."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from core.schema import Constraint


_BINARY = Path(__file__).parent / "ast_filter" / "target" / "release" / "ast_filter"


def scan(
    files: list[str],
    constraints: list[Constraint],
) -> dict[str, list[str]]:
    """Return a mapping of constraint_id → matched_patterns for each constraint
    whose ast_triggers appear in the given files.

    Falls back to empty dict if the binary is not compiled or no files are given.
    """
    if not files or not constraints or not _BINARY.exists():
        return {}

    triggers = [
        {"constraint_id": c.constraint_id, "patterns": c.scope.ast_triggers}
        for c in constraints
        if c.scope.ast_triggers
    ]
    if not triggers:
        return {}

    payload = json.dumps({"files": files, "triggers": triggers})
    try:
        result = subprocess.run(
            [str(_BINARY)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=1.0,
        )
        if result.returncode != 0:
            return {}
        matches = json.loads(result.stdout).get("matches", [])
        return {m["constraint_id"]: m["matched_patterns"] for m in matches}
    except Exception:
        return {}
