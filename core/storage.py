"""Storage helpers for the local .cortex directory."""

from __future__ import annotations

from pathlib import Path

import yaml

from core.schema import Constraint


def ensure_cortex_dirs(repo_root: Path) -> Path:
    cortex_dir = repo_root / ".cortex"
    for relative in ("constraints", "sessions", "archive", "patterns"):
        (cortex_dir / relative).mkdir(parents=True, exist_ok=True)
    return cortex_dir


def constraints_dir(repo_root: Path) -> Path:
    return ensure_cortex_dirs(repo_root) / "constraints"


def constraint_path(repo_root: Path, constraint_id: str) -> Path:
    return constraints_dir(repo_root) / f"{constraint_id}.yaml"


def save_constraint(repo_root: Path, constraint: Constraint) -> Path:
    path = constraint_path(repo_root, constraint.constraint_id)
    rendered = yaml.safe_dump(
        constraint.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=False,
    )
    path.write_text(rendered, encoding="utf-8")
    return path


def load_constraint(path: Path) -> Constraint:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Constraint.model_validate(payload)


def load_constraints(repo_root: Path) -> list[Constraint]:
    directory = constraints_dir(repo_root)
    loaded: list[Constraint] = []
    for path in sorted(directory.glob("*.yaml")):
        loaded.append(load_constraint(path))
    return loaded
