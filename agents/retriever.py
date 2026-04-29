"""Retriever: three-layer constraint retrieval pipeline."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.coverage import record_retrieval_hit, record_unconstrained_files
from core.schema import Constraint
from core.storage import load_constraints
from retrieval import ast_filter as l1
from retrieval import semantic as l2
from retrieval import reranker as l3


_L1_SCORE = 1.5   # bonus per matched ast_trigger pattern
_L2_WEIGHT = 1.0  # multiplier on semantic score


@dataclass
class RetrievedConstraint:
    constraint_id: str
    title: str
    never_do: str
    because: str
    instead: str
    score: float = 0.0
    reasons: list[str] | None = None


@dataclass
class RetrievalResult:
    constraints: list[RetrievedConstraint]


class Retriever:
    """Three-layer retrieval: L1 AST filter → L2 semantic → L3 schema reranker."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def retrieve(self, boost: str | None = None, verbose: bool = False) -> RetrievalResult:
        stored = load_constraints(self.repo_root)
        if not stored:
            return self._scaffold(boost, verbose)

        branch_name = self._get_branch_name()
        touched_files = self._get_recently_touched_files()

        # L1: find which constraints have ast_trigger hits in recently-touched files
        l1_hits = l1.scan(touched_files, stored)

        # L2 + base: score every constraint
        query = " ".join(filter(None, [branch_name, boost or ""]))
        scored = self._score_all(stored, branch_name, boost, query, l1_hits)

        # L3: scope-aware reranking
        ranked = l3.rerank(scored, language="python", max_results=5)

        # P7: log retrieval hits to coverage map
        for c, _, _ in ranked:
            triggered = l1_hits.get(c.constraint_id, [])
            files_for_constraint = [f for f in touched_files if triggered]
            record_retrieval_hit(self.repo_root, c.constraint_id, files_for_constraint)
        record_unconstrained_files(self.repo_root, touched_files)

        return RetrievalResult(
            constraints=[
                RetrievedConstraint(
                    constraint_id=c.constraint_id,
                    title=c.context,
                    never_do=c.never_do[0],
                    because=c.because,
                    instead=c.instead,
                    score=score,
                    reasons=reasons if verbose else None,
                )
                for c, score, reasons in ranked
            ]
        )

    # ── Scoring ────────────────────────────────────────────────────────────────

    def _score_all(
        self,
        constraints: list[Constraint],
        branch_name: str,
        boost: str | None,
        query: str,
        l1_hits: dict[str, list[str]],
    ) -> list[tuple[Constraint, float, list[str]]]:
        branch_tokens = self._tokenize(branch_name)
        boost_tokens = self._tokenize(boost or "")
        scored = []

        for constraint in constraints:
            score = 0.0
            reasons: list[str] = []

            # Base confidence
            score += constraint.confidence
            reasons.append(f"confidence={constraint.confidence:.2f}")

            # Sequence bonus: higher sequence = more times confirmed
            seq_match = re.search(r"-(\d+)$", constraint.constraint_id)
            seq = int(seq_match.group(1)) if seq_match else 1
            if seq > 1:
                score += (seq - 1) * 0.01
                reasons.append(f"sequence bonus: {seq}")

            # Source and type bonuses
            if constraint.source == "observed":
                score += 0.5
                reasons.append("observed source")
            if constraint.meta_type == "operational_constraint":
                score += 0.25
                reasons.append("operational constraint")

            # Branch token matches
            branch_matches = self._matches_tokens(constraint, branch_tokens)
            if branch_matches:
                score += 2.0 * len(branch_matches)
                reasons.append(f"branch match: {', '.join(branch_matches)}")

            # Boost token matches
            boost_matches = self._matches_tokens(constraint, boost_tokens)
            if boost_matches:
                score += 3.0 * len(boost_matches)
                reasons.append(f"boost match: {', '.join(boost_matches)}")

            # L1: ast_trigger hits in recently-touched files
            if constraint.constraint_id in l1_hits:
                patterns = l1_hits[constraint.constraint_id]
                score += _L1_SCORE * len(patterns)
                reasons.append(f"L1 ast match: {', '.join(patterns)}")

            # L2: semantic overlap with branch+boost query
            sem = l2.score(constraint, query)
            if sem > 0:
                score += _L2_WEIGHT * sem
                reasons.append(f"L2 semantic={sem:.2f}")

            scored.append((constraint, score, reasons))

        scored.sort(key=lambda item: (-item[1], item[0].constraint_id))
        return scored

    # ── Git helpers ────────────────────────────────────────────────────────────

    def _get_branch_name(self) -> str:
        head_path = self.repo_root / ".git" / "HEAD"
        if not head_path.exists():
            return "unknown"
        head = head_path.read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            return head.rsplit("/", maxsplit=1)[-1]
        return head[:7]

    def _get_recently_touched_files(self) -> list[str]:
        """Return absolute paths of files changed in the last 5 commits."""
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo_root), "diff", "--name-only", "HEAD~5..HEAD"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if result.returncode != 0:
                return []
            files = []
            for name in result.stdout.splitlines():
                name = name.strip()
                if name:
                    full = self.repo_root / name
                    if full.exists():
                        files.append(str(full))
            return files
        except Exception:
            return []

    # ── Token helpers ──────────────────────────────────────────────────────────

    def _matches_tokens(self, constraint: Constraint, tokens: set[str]) -> list[str]:
        searchable = " ".join([
            constraint.constraint_id,
            constraint.context,
            constraint.because,
            constraint.instead,
            " ".join(constraint.scope.services),
            " ".join(constraint.scope.ast_triggers),
            " ".join(constraint.scope.error_codes),
        ]).lower()
        return [token for token in sorted(tokens) if token in searchable]

    def _tokenize(self, value: str) -> set[str]:
        return {t for t in re.split(r"[^a-z0-9]+", value.lower()) if len(t) >= 3}

    # ── Scaffold fallback ──────────────────────────────────────────────────────

    def _scaffold(self, boost: str | None, verbose: bool) -> RetrievalResult:
        boost_suffix = f" in {boost}" if boost else ""
        return RetrievalResult(constraints=[
            RetrievedConstraint(
                constraint_id="scaffold-session-001",
                title=f"Session lifecycle management{boost_suffix}",
                never_do="Never lose session state without warning the user",
                because="Session logs are the backbone of later distillation and recovery",
                instead="Persist session metadata and handle orphan recovery explicitly",
                score=1.0,
                reasons=["fallback scaffold"] if verbose else None,
            ),
            RetrievedConstraint(
                constraint_id="scaffold-cli-001",
                title="CLI-first architecture",
                never_do="Never hide core lifecycle behavior behind an implicit background flow",
                because="The README requires explicit start and stop boundaries for debuggability",
                instead="Keep session start, stop, status, and recovery as first-class commands",
                score=0.9,
                reasons=["fallback scaffold"] if verbose else None,
            ),
        ])
