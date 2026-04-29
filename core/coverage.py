"""Coverage map: tracks which constraints are retrieved and which files they cover."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


_COVERAGE_FILE = ".cortex/coverage.json"


def _load(repo_root: Path) -> dict[str, Any]:
    path = repo_root / _COVERAGE_FILE
    if not path.exists():
        return {"constraint_hits": {}, "file_coverage": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"constraint_hits": {}, "file_coverage": {}}


def _save(repo_root: Path, data: dict[str, Any]) -> None:
    path = repo_root / _COVERAGE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = date.today().isoformat()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_retrieval_hit(
    repo_root: Path,
    constraint_id: str,
    triggered_by_files: list[str],
) -> None:
    """Increment the hit count for a retrieved constraint and log which files triggered it."""
    data = _load(repo_root)
    hits = data.setdefault("constraint_hits", {})
    entry = hits.setdefault(constraint_id, {"hit_count": 0, "last_hit": None, "triggered_by_files": []})
    entry["hit_count"] += 1
    entry["last_hit"] = date.today().isoformat()
    known = set(entry["triggered_by_files"])
    for f in triggered_by_files:
        rel = _rel(repo_root, f)
        if rel not in known:
            entry["triggered_by_files"].append(rel)
            known.add(rel)

    file_cov = data.setdefault("file_coverage", {})
    for f in triggered_by_files:
        rel = _rel(repo_root, f)
        fc = file_cov.setdefault(rel, {"touch_count": 0, "constraints_triggered": []})
        fc["touch_count"] += 1
        if constraint_id not in fc["constraints_triggered"]:
            fc["constraints_triggered"].append(constraint_id)

    _save(repo_root, data)


def record_unconstrained_files(repo_root: Path, all_touched: list[str]) -> None:
    """Log files that were touched but triggered no constraints."""
    data = _load(repo_root)
    file_cov = data.setdefault("file_coverage", {})
    unconstrained = data.setdefault("unconstrained_files", [])
    known_unconstrained = set(unconstrained)

    for f in all_touched:
        rel = _rel(repo_root, f)
        has_constraints = bool(file_cov.get(rel, {}).get("constraints_triggered"))
        if not has_constraints and rel not in known_unconstrained:
            unconstrained.append(rel)
            known_unconstrained.add(rel)

    _save(repo_root, data)


def load_coverage(repo_root: Path) -> dict[str, Any]:
    return _load(repo_root)


def _rel(repo_root: Path, file_path: str) -> str:
    try:
        return str(Path(file_path).relative_to(repo_root))
    except ValueError:
        return file_path
