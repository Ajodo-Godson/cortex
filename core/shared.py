"""Shared constraint namespace for cross-repo inheritance (P5)."""

from __future__ import annotations

from pathlib import Path

import yaml

from core.schema import Constraint


SHARED_DIR = Path.home() / ".cortex" / "shared"


def shared_constraints_dir() -> Path:
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    return SHARED_DIR


def load_shared_constraints() -> list[Constraint]:
    directory = shared_constraints_dir()
    loaded: list[Constraint] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            loaded.append(Constraint.model_validate(payload))
        except Exception:
            continue
    return loaded


def save_shared_constraint(constraint: Constraint) -> Path:
    path = shared_constraints_dir() / f"{constraint.constraint_id}.yaml"
    rendered = yaml.safe_dump(
        constraint.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=False,
    )
    path.write_text(rendered, encoding="utf-8")
    return path


def is_shared(constraint_id: str) -> bool:
    return (shared_constraints_dir() / f"{constraint_id}.yaml").exists()
