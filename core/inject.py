"""Helpers for injecting and removing cortex sections in agent context files."""

from __future__ import annotations

import re
from pathlib import Path

_MARKER_START = "<!-- CORTEX:START -->"
_MARKER_END = "<!-- CORTEX:END -->"
_SECTION_RE = re.compile(
    rf"{re.escape(_MARKER_START)}.*?{re.escape(_MARKER_END)}\n?",
    re.DOTALL,
)

AGENT_FILES = ["CLAUDE.md", "AGENTS.md"]


def inject_constraints(repo_root: Path, content: str) -> list[Path]:
    """Inject cortex content into all agent context files. Returns paths written."""
    section = f"{_MARKER_START}\n{content}\n{_MARKER_END}\n"
    written = []
    for filename in AGENT_FILES:
        path = repo_root / filename
        if path.exists():
            existing = _remove_section(path.read_text(encoding="utf-8"))
            path.write_text(existing.rstrip("\n") + "\n\n" + section, encoding="utf-8")
        else:
            path.write_text(section, encoding="utf-8")
        written.append(path)
    return written


def remove_constraints(repo_root: Path) -> None:
    """Remove cortex section from all agent context files."""
    for filename in AGENT_FILES:
        path = repo_root / filename
        if not path.exists():
            continue
        cleaned = _remove_section(path.read_text(encoding="utf-8")).strip()
        if cleaned:
            path.write_text(cleaned + "\n", encoding="utf-8")
        else:
            path.unlink()


def _remove_section(text: str) -> str:
    return _SECTION_RE.sub("", text)
