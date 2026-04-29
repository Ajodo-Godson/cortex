"""Gardener: detects constraint conflicts and reconciles them into meta-constraints."""

from __future__ import annotations

import itertools
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.llm import build_client as _build_llm_client
from core.llm import DEFAULT_MODEL as _DEFAULT_MODEL
from core.schema import Constraint
from core.storage import load_constraints


_OPPOSING_PAIRS = [
    # temporal
    ("always", "never"),
    ("before", "after"),
    ("early", "late"),
    ("eager", "lazy"),
    ("immediately", "defer"),
    # spatial / structural
    ("inside", "outside"),
    ("within", "without"),
    ("inline", "extracted"),
    ("wrap", "avoid"),
    ("nested", "flat"),
    # concurrency
    ("synchronous", "asynchronous"),
    ("sync", "async"),
    ("sequential", "parallel"),
    ("sequential", "concurrent"),
    ("blocking", "nonblocking"),
    # resource lifecycle
    ("acquire", "release"),
    ("open", "close"),
    ("lock", "unlock"),
    ("allocate", "free"),
    ("connect", "disconnect"),
    # data handling
    ("batch", "individual"),
    ("single", "batch"),
    ("cache", "bypass"),
    ("encrypt", "plain"),
    ("validate", "skip"),
    ("strict", "permissive"),
    ("explicit", "implicit"),
    ("mutable", "immutable"),
    # error handling
    ("retry", "abort"),
    ("fail", "ignore"),
    ("raise", "swallow"),
    # flow
    ("allow", "block"),
    ("allow", "deny"),
    ("push", "pull"),
    ("stateful", "stateless"),
]

_CONFLICT_CHECK_SYSTEM = """\
You are the Cortex Gardener. Determine whether two coding constraints conflict with each \
other — meaning following one would require violating the other in some plausible scenario.

Respond with ONLY a valid JSON object — no markdown fences:
{"conflicts": true or false, "explanation": "<one sentence if conflicts is true, else empty>"}
"""

_DUEL_SYSTEM = """\
You are the Cortex Gardener. Generate a short synthetic scenario (2-3 sentences) where \
two conflicting constraints apply simultaneously and following one would violate the other. \
Describe only the scenario — no resolution, no code blocks.
"""

_RECONCILE_SYSTEM = """\
You are the Cortex Gardener. Reconcile two conflicting coding constraints into a single \
meta-constraint that resolves the conflict by specifying exactly when each rule applies.

Respond with ONLY a valid JSON object — no markdown fences. Schema:
{
  "constraint_id": "meta-<slug>-001",
  "meta_type": "operational_constraint",
  "scope": {
    "language": "<inherited from source constraints>",
    "services": [],
    "ast_triggers": [],
    "error_codes": []
  },
  "context": "<one sentence: when does this meta-rule apply>",
  "constraint": "<prose: the reconciled rule specifying when each original rule applies>",
  "never_do": ["<the specific anti-pattern this meta-constraint prevents>"],
  "because": "<why the original constraints conflict and why this resolution works>",
  "instead": "<the specific action that correctly handles both cases>",
  "evidence": [
    {"type": "reconciled_from", "reference": "<constraint_a_id>"},
    {"type": "reconciled_from", "reference": "<constraint_b_id>"}
  ],
  "validation": "<how to verify the meta-constraint is being followed>",
  "confidence": 0.75,
  "source": "inferred"
}

Rules:
- constraint must be prose only — no backticks or code fences
- never_do must have exactly one entry in plain English
- confidence must be at most 0.75
- source is always "inferred"
"""


@dataclass
class ConflictReport:
    constraint_a: Constraint
    constraint_b: Constraint
    explanation: str
    duel_scenario: str = field(default="")


class Gardener:
    """Scans the constraint library for conflicts and reconciles them.

    scan() is heuristic-only — no API calls.
    reconcile() uses the configured LLM (same CORTEX_MODEL/CORTEX_API_KEY env vars).
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._model = os.environ.get("CORTEX_MODEL", _DEFAULT_MODEL)

    def scan(self, deep: bool = False) -> list[ConflictReport]:
        """Return all conflict pairs detected among stored constraints.

        deep=False (default): heuristic only — fast, no API calls.
        deep=True: heuristic first; pairs with high token overlap but no keyword
                   match are also sent to the LLM for semantic conflict detection.
        """
        constraints = load_constraints(self.repo_root)
        if len(constraints) < 2:
            return []

        provider, client = (_build_llm_client(self._model) if deep else (None, None))
        reports = []
        for a, b in itertools.combinations(constraints, 2):
            conflicting, explanation = self._detect_conflict(a, b)
            if not conflicting and deep:
                conflicting, explanation = self._llm_check_conflict(
                    provider, client, a, b  # type: ignore[arg-type]
                )
            if conflicting:
                reports.append(ConflictReport(
                    constraint_a=a,
                    constraint_b=b,
                    explanation=explanation,
                ))
        return reports

    def reconcile(self, conflict: ConflictReport) -> Constraint:
        """Generate a duel scenario and a meta-constraint resolving the conflict."""
        provider, client = _build_llm_client(self._model)
        conflict.duel_scenario = self._generate_duel(provider, client, conflict)
        raw = self._normalize_raw(self._generate_meta_constraint(provider, client, conflict))
        proposed_id = str(raw.get("constraint_id", "meta-constraint-001"))
        raw["constraint_id"] = self._next_constraint_id(proposed_id)
        raw["source"] = "inferred"
        raw["confidence"] = min(float(raw.get("confidence", 0.75)), 0.75)
        raw.setdefault("evidence", [
            {"type": "reconciled_from", "reference": conflict.constraint_a.constraint_id},
            {"type": "reconciled_from", "reference": conflict.constraint_b.constraint_id},
        ])
        return Constraint.model_validate(raw)

    # ── Conflict detection (heuristic, no API) ─────────────────────────────────

    def _detect_conflict(self, a: Constraint, b: Constraint) -> tuple[bool, str]:
        # Skip if languages explicitly differ
        if (
            a.scope.language and b.scope.language
            and a.scope.language.lower() != b.scope.language.lower()
        ):
            return False, ""

        # Shared ast_triggers with different never_do rules
        shared_triggers = set(a.scope.ast_triggers) & set(b.scope.ast_triggers)
        if shared_triggers and a.never_do[0].lower() != b.never_do[0].lower():
            return True, (
                f"Both triggered by {sorted(shared_triggers)} "
                f"but prescribe different forbidden actions"
            )

        # Opposing directives with sufficient token overlap
        a_text = f"{a.constraint} {a.never_do[0]} {a.instead}".lower()
        b_text = f"{b.constraint} {b.never_do[0]} {b.instead}".lower()
        a_tokens = {t for t in re.split(r"\W+", a_text) if len(t) >= 3}
        b_tokens = {t for t in re.split(r"\W+", b_text) if len(t) >= 3}
        overlap = len(a_tokens & b_tokens) / max(len(a_tokens | b_tokens), 1)

        if overlap >= 0.25:
            for pos_word, neg_word in _OPPOSING_PAIRS:
                a_has_pos = pos_word in a_text
                b_has_neg = neg_word in b_text
                a_has_neg = neg_word in a_text
                b_has_pos = pos_word in b_text
                if (a_has_pos and b_has_neg) or (a_has_neg and b_has_pos):
                    return True, (
                        f"Opposing directives ('{pos_word}' vs '{neg_word}') "
                        f"on related topics (overlap={overlap:.0%})"
                    )

        return False, ""

    def _llm_check_conflict(
        self,
        provider: str,
        client: object,
        a: Constraint,
        b: Constraint,
    ) -> tuple[bool, str]:
        """Ask the LLM whether two constraints conflict. Used only in --deep mode."""
        user_msg = (
            f"Constraint A ({a.constraint_id}):\n"
            f"  Rule: {a.constraint}\n"
            f"  Never do: {a.never_do[0]}\n\n"
            f"Constraint B ({b.constraint_id}):\n"
            f"  Rule: {b.constraint}\n"
            f"  Never do: {b.never_do[0]}\n\n"
            "Do these constraints conflict?"
        )
        try:
            text = self._call_text(provider, client, _CONFLICT_CHECK_SYSTEM, user_msg)
            result = self._parse_json(text)
            if result.get("conflicts"):
                return True, str(result.get("explanation", "LLM-detected semantic conflict"))
        except Exception:
            pass
        return False, ""

    # ── LLM calls ─────────────────────────────────────────────────────────────

    def _generate_duel(
        self, provider: str, client: object, conflict: ConflictReport
    ) -> str:
        a, b = conflict.constraint_a, conflict.constraint_b
        user_msg = (
            f"Constraint A ({a.constraint_id}): {a.constraint}\n"
            f"  Never do: {a.never_do[0]}\n\n"
            f"Constraint B ({b.constraint_id}): {b.constraint}\n"
            f"  Never do: {b.never_do[0]}\n\n"
            f"Conflict: {conflict.explanation}\n\n"
            "Generate the duel scenario."
        )
        return self._call_text(provider, client, _DUEL_SYSTEM, user_msg)

    def _generate_meta_constraint(
        self, provider: str, client: object, conflict: ConflictReport
    ) -> dict[str, object]:
        a, b = conflict.constraint_a, conflict.constraint_b
        user_msg = (
            f"Constraint A ({a.constraint_id}): {a.constraint}\n"
            f"Constraint B ({b.constraint_id}): {b.constraint}\n\n"
            f"Duel scenario: {conflict.duel_scenario}\n\n"
            "Generate the reconciling meta-constraint. Respond with JSON only."
        )
        text = self._call_text(provider, client, _RECONCILE_SYSTEM, user_msg)
        return self._parse_json(text)

    def _call_text(
        self, provider: str, client: object, system: str, user: str
    ) -> str:
        if provider == "anthropic":
            response = client.messages.create(  # type: ignore[union-attr]
                model=self._model,
                max_tokens=1024,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
            )
            for block in response.content:
                if block.type == "text":
                    return block.text.strip()
            raise ValueError("Model returned no text")

        response = client.chat.completions.create(  # type: ignore[union-attr]
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (response.choices[0].message.content or "").strip()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _normalize_raw(self, raw: dict[str, object]) -> dict[str, object]:
        """Coerce fields that must be lists but LLMs sometimes return as strings."""
        for field in ("never_do", "evidence", "ast_triggers", "services", "error_codes"):
            val = raw.get(field)
            if isinstance(val, str):
                raw[field] = [val] if val else []
            scope = raw.get("scope")
            if isinstance(scope, dict):
                sv = scope.get(field)
                if isinstance(sv, str):
                    scope[field] = [sv] if sv else []
        return raw

    def _parse_json(self, text: str) -> dict[str, object]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)

    def _next_constraint_id(self, proposed_id: str) -> str:
        base = re.sub(r"-\d{3}$", "", proposed_id)
        existing_ids = {c.constraint_id for c in load_constraints(self.repo_root)}
        for seq in range(1, 1000):
            candidate = f"{base}-{seq:03d}"
            if candidate not in existing_ids:
                return candidate
        return f"{base}-999"
