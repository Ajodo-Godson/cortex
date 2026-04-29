"""Distiller: converts correction events into structured constraints."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from core.llm import build_client as _build_llm_client
from core.llm import DEFAULT_MODEL as _DEFAULT_MODEL
from core.schema import Constraint
from core.schema import CorrectionEvent
from core.storage import load_constraints
from core.storage import read_session_records
from core.storage import constraint_path
from core.storage import save_constraint

_SYSTEM_PROMPT = """\
You are the Cortex constraint extractor. Cortex is a persistent constraint \
layer that captures what NOT to do when writing code, based on real observed \
errors and corrections.

Given raw signals from a coding agent (code context, error context, and a \
learned rule), extract a single structured operational constraint.

Respond with ONLY a valid JSON object — no markdown fences, no explanation, \
no commentary. The JSON must match this exact schema:

{
  "constraint_id": "<kebab-case-slug>-001",
  "meta_type": "operational_constraint",
  "scope": {
    "language": "<python|typescript|go|rust|java|etc>",
    "services": [],
    "ast_triggers": ["<specific code token or pattern that triggers this constraint>"],
    "error_codes": []
  },
  "context": "<one sentence describing when this constraint applies>",
  "constraint": "<prose rule: Never [action] because [reason]. Always [alternative].>",
  "never_do": ["<the specific forbidden action in plain English>"],
  "because": "<why this action is dangerous or wrong>",
  "instead": "<what to do instead>",
  "evidence": [],
  "validation": "<how to verify the constraint is being followed>",
  "confidence": 0.80,
  "source": "observed"
}

Strict rules:
- constraint must be prose only — never contains backticks or code fences
- never_do must have exactly one entry in plain English (no code syntax)
- confidence must be between 0.0 and 0.85 (agent-flagged constraints cap at 0.85)
- ast_triggers must contain specific code tokens (e.g. "db.session.commit()")
- constraint_id must be kebab-case ending in a 3-digit sequence like -001
- source is always "observed"
- meta_type is "operational_constraint" for implementation rules, \
"workflow_constraint" for process rules, "architectural_constraint" for design rules
"""


@dataclass
class DistillResult:
    correction_events: int
    new_constraints: int
    updated_constraints: int


class Distiller:
    """Turns correction events into structured constraints.

    Model and provider are controlled by environment variables:
      CORTEX_MODEL     — model name (default: claude-opus-4-7)
      CORTEX_API_KEY   — API key override (falls back to ANTHROPIC_API_KEY or OPENAI_API_KEY)
      CORTEX_BASE_URL  — base URL for OpenAI-compatible endpoints (Ollama, Groq, etc.)

    Provider is inferred from the model name:
      claude-*  → Anthropic SDK (requires anthropic package)
      anything else → OpenAI-compatible SDK (requires openai package)

    distill_event() is always deterministic and requires no API key.
    distill_raw_signal() requires the appropriate package and key.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._model = os.environ.get("CORTEX_MODEL", _DEFAULT_MODEL)

    # ── Public API ─────────────────────────────────────────────────────────────

    def distill_event(self, event: CorrectionEvent | dict[str, object]) -> Constraint:
        """Convert a structured correction event into a validated constraint."""
        parsed = event if isinstance(event, CorrectionEvent) else CorrectionEvent.model_validate(event)
        evidence = parsed.evidence or []
        return Constraint(
            constraint_id=parsed.constraint_id,
            meta_type=parsed.meta_type,
            scope=parsed.scope,
            context=parsed.context,
            constraint=self._build_constraint_text(parsed),
            never_do=[parsed.failing_action],
            because=parsed.because,
            instead=parsed.instead,
            evidence=evidence,
            validation=parsed.validation,
            confidence=parsed.confidence,
            last_validated=parsed.last_validated,
            source=parsed.source,
        )

    def distill_events(self, events: list[CorrectionEvent | dict[str, object]]) -> list[Constraint]:
        return [self.distill_event(event) for event in events]

    def distill_raw_signal(
        self,
        code_context: str,
        error_context: str,
        learned_rule: str,
    ) -> Constraint:
        """Use an LLM to convert a raw agent signal into a constraint.

        The constraint is NOT automatically saved — the caller is responsible
        for calling save_constraint().
        """
        provider, client = self._build_client()
        if provider == "anthropic":
            raw = self._call_anthropic(client, code_context, error_context, learned_rule)
        else:
            raw = self._call_openai_compat(client, code_context, error_context, learned_rule)

        proposed_id = str(raw.get("constraint_id", "agent-flagged-001"))
        raw["constraint_id"] = self._next_constraint_id(proposed_id)
        raw["source"] = "observed"
        raw.setdefault("evidence", [])
        conf = float(raw.get("confidence", 0.80))
        raw["confidence"] = min(conf, 0.85)
        return Constraint.model_validate(raw)

    def run(self, log_path: Path | str) -> DistillResult:
        """Distill newline-delimited JSON correction events from a session log."""
        log_path = Path(log_path)
        archive_path = self.repo_root / ".cortex" / "archive" / f"{log_path.stem}.distilled"
        constraints = self._distill_log_file(log_path)
        new_constraints = 0
        updated_constraints = 0
        for constraint in constraints:
            existing_path = constraint_path(self.repo_root, constraint.constraint_id)
            existed = existing_path.exists()
            save_constraint(self.repo_root, constraint)
            if existed:
                updated_constraints += 1
            else:
                new_constraints += 1
        rendered = [constraint.model_dump(mode="json") for constraint in constraints]
        archive_path.write_text(json.dumps(rendered, indent=2), encoding="utf-8")
        return DistillResult(
            correction_events=len(constraints),
            new_constraints=new_constraints,
            updated_constraints=updated_constraints,
        )

    # ── Provider routing ───────────────────────────────────────────────────────

    def _build_client(self) -> tuple[str, object]:
        return _build_llm_client(self._model)

    def _call_anthropic(
        self,
        client: object,
        code_context: str,
        error_context: str,
        learned_rule: str,
    ) -> dict[str, object]:
        response = client.messages.create(  # type: ignore[union-attr]
            model=self._model,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": self._user_prompt(code_context, error_context, learned_rule),
                }
            ],
        )
        for block in response.content:
            if block.type == "text":
                return self._parse_json(block.text)
        raise ValueError("Model returned no text content")

    def _call_openai_compat(
        self,
        client: object,
        code_context: str,
        error_context: str,
        learned_rule: str,
    ) -> dict[str, object]:
        response = client.chat.completions.create(  # type: ignore[union-attr]
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": self._user_prompt(code_context, error_context, learned_rule)},
            ],
        )
        text = response.choices[0].message.content or ""
        return self._parse_json(text)

    # ── Shared helpers ─────────────────────────────────────────────────────────

    def _user_prompt(self, code_context: str, error_context: str, learned_rule: str) -> str:
        return (
            f"Code context:\n{code_context}\n\n"
            f"Error context:\n{error_context}\n\n"
            f"Learned rule:\n{learned_rule}\n\n"
            "Extract a Cortex constraint. Respond with JSON only."
        )

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

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _distill_log_file(self, log_path: Path) -> list[Constraint]:
        constraints: list[Constraint] = []
        for payload in read_session_records(log_path):
            if payload.get("type") not in (None, "correction_event"):
                continue
            constraints.append(self.distill_event(payload))
        return constraints

    def _build_constraint_text(self, event: CorrectionEvent) -> str:
        return (
            f"{event.failing_action}. {event.because}. "
            f"Always {event.instead.lower()}."
        )
