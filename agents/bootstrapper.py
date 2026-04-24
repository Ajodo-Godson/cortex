"""Bootstrapper: mines git history for revert/fix sequences and seeds the constraint library."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import pygit2
    _PYGIT2_AVAILABLE = True
except ImportError:
    _PYGIT2_AVAILABLE = False

from agents.distiller import Distiller
from core.storage import ensure_cortex_dirs
from core.storage import save_constraint


class Bootstrapper:
    """Seeds the CORTEX library by mining git history for correction patterns."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.distiller = Distiller(repo_root)

    def run_initial_bootstrap(self, since_days: int = 90) -> int:
        """Mine git history and seed the constraint library.

        Returns the number of constraints added.
        All bootstrapped constraints are stored as source=inferred with confidence capped at 0.70.
        """
        if not _PYGIT2_AVAILABLE:
            self._write_marker(
                "pygit2 not installed — run: pip install pygit2\n"
                "Bootstrap skipped. Re-run after installing pygit2."
            )
            return 0

        try:
            repo = pygit2.Repository(str(self.repo_root))
        except Exception:
            self._write_marker("Could not open git repository. Bootstrap skipped.")
            return 0

        ensure_cortex_dirs(self.repo_root)
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        events = self._mine_commits(repo, cutoff)

        added = 0
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self._distill_and_save, event): event for event in events}
            for future in as_completed(futures):
                if future.result():
                    added += 1

        self._write_marker(
            f"Bootstrapped {added} constraints from git history (last {since_days} days).\n"
            f"All constraints stored as source=inferred, confidence<=0.70.\n"
            f"Run 'cortex constraints' to review."
        )
        return added

    def _distill_and_save(self, event_dict: dict[str, object]) -> bool:
        try:
            constraint = self.distiller.distill_event(event_dict)
            constraint = constraint.model_copy(
                update={
                    "confidence": min(constraint.confidence, 0.70),
                    "source": "inferred",
                }
            )
            save_constraint(self.repo_root, constraint)
            return True
        except Exception:
            return False

    # ── Commit mining ──────────────────────────────────────────────────────────

    def _mine_commits(
        self,
        repo: "pygit2.Repository",
        cutoff: datetime,
    ) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        seen_keys: set[str] = set()

        try:
            head = repo.head.peel(pygit2.Commit)
        except Exception:
            return events

        for commit in repo.walk(head.id, pygit2.GIT_SORT_TIME):
            commit_time = datetime.fromtimestamp(commit.commit_time, tz=timezone.utc)
            if commit_time < cutoff:
                break

            message = commit.message.strip()
            event = self._extract_event(repo, commit, message)
            if event is None:
                continue

            key = event["constraint_key"]
            if key in seen_keys:
                continue
            seen_keys.add(key)
            events.append(event)

        return events

    def _extract_event(
        self,
        repo: "pygit2.Repository",
        commit: "pygit2.Commit",
        message: str,
    ) -> dict[str, object] | None:
        msg_lower = message.lower()

        if message.startswith("Revert ") and '"' in message:
            return self._build_revert_event(commit, message)

        fix_prefixes = ("fix:", "hotfix:", "bugfix:", "fix(")
        if any(msg_lower.startswith(p) for p in fix_prefixes):
            return self._build_fix_event(repo, commit, message)

        return None

    # ── Event builders ─────────────────────────────────────────────────────────

    def _build_revert_event(
        self,
        commit: "pygit2.Commit",
        message: str,
    ) -> dict[str, object]:
        try:
            original = message.split('"', 1)[1].rsplit('"', 1)[0]
        except IndexError:
            original = message[7:100]

        short_hash = str(commit.id)[:7]
        date_str = datetime.fromtimestamp(commit.commit_time, tz=timezone.utc).strftime("%Y-%m-%d")

        return {
            "event_id": f"evt-bootstrap-revert-{short_hash}",
            "constraint_key": f"bootstrap-revert-{short_hash}",
            "sequence": 1,
            "meta_type": "operational_constraint",
            "scope": {
                "language": "python",
                "services": [],
                "ast_triggers": [],
                "error_codes": [],
            },
            "context": f"Git history: revert detected on {date_str}",
            "failing_action": f"Apply the approach that was reverted in commit {short_hash}: {original[:200]}",
            "correction": f"Review revert commit {short_hash} to understand what went wrong",
            "because": f"This commit was reverted on {date_str} — the approach caused a regression",
            "instead": f"check revert commit {short_hash} before applying similar changes",
            "evidence": [
                {
                    "type": "agent_correction",
                    "commit_hash": short_hash,
                    "corrected_by": "git_revert",
                    "date": date_str,
                }
            ],
            "validation": f"git show {short_hash}",
            "confidence": 0.70,
            "source": "inferred",
        }

    def _build_fix_event(
        self,
        repo: "pygit2.Repository",
        commit: "pygit2.Commit",
        message: str,
    ) -> dict[str, object]:
        short_hash = str(commit.id)[:7]
        date_str = datetime.fromtimestamp(commit.commit_time, tz=timezone.utc).strftime("%Y-%m-%d")

        colon_idx = message.find(":")
        summary = message[colon_idx + 1:].strip() if colon_idx != -1 else message
        # Strip parenthetical scope from conventional commits e.g. "fix(auth): ..."
        summary = re.sub(r"^\([^)]+\)\s*", "", summary)

        error_hint = self._extract_error_hint(repo, commit)

        return {
            "event_id": f"evt-bootstrap-fix-{short_hash}",
            "constraint_key": f"bootstrap-fix-{short_hash}",
            "sequence": 1,
            "meta_type": "operational_constraint",
            "scope": {
                "language": "python",
                "services": [],
                "ast_triggers": [],
                "error_codes": [error_hint] if error_hint else [],
            },
            "context": f"Git history: fix commit on {date_str}",
            "failing_action": f"Apply the defective approach that required this fix: {summary[:200]}",
            "correction": f"Apply the correction from commit {short_hash}",
            "because": f"A fix commit on {date_str} indicates the prior approach had a defect",
            "instead": f"use the corrected approach from commit {short_hash}",
            "evidence": [
                {
                    "type": "agent_correction",
                    "commit_hash": short_hash,
                    "corrected_by": "fix_commit",
                    "date": date_str,
                }
            ],
            "validation": f"git show {short_hash}",
            "confidence": 0.65,
            "source": "inferred",
        }

    def _extract_error_hint(
        self,
        repo: "pygit2.Repository",
        commit: "pygit2.Commit",
    ) -> str | None:
        """Extract the first error class name from lines added in this commit's diff."""
        try:
            if not commit.parents:
                return None
            diff = repo.diff(commit.parents[0], commit)
            for patch in diff:
                for hunk in patch.hunks:
                    for line in hunk.lines:
                        if line.origin != "+":
                            continue
                        for token in ("Error", "Exception", "Timeout", "Deadlock"):
                            if token in line.content:
                                match = re.search(r"\b\w*" + token + r"\w*\b", line.content)
                                if match:
                                    return match.group(0)
        except Exception:
            pass
        return None

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _write_marker(self, message: str) -> None:
        marker = self.repo_root / ".cortex" / "bootstrap.txt"
        marker.write_text(message + "\n", encoding="utf-8")
