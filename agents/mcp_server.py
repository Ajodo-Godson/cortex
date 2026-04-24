"""Cortex MCP server: exposes cortex_flag for real-time agent constraint self-writing."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False

from agents.distiller import Distiller
from core.storage import save_constraint


def create_mcp_server(repo_root: Path) -> object:
    """Return a configured FastMCP server bound to the given repo root.

    Raises RuntimeError if the mcp package is not installed.
    """
    if not _HAS_MCP:
        raise RuntimeError(
            "The 'mcp' package is not installed. "
            "Run: pip install 'mcp>=1.0'"
        )

    mcp = FastMCP("cortex")
    distiller = Distiller(repo_root)

    @mcp.tool()
    def cortex_flag(
        code_context: str,
        error_context: str,
        learned_rule: str,
    ) -> str:
        """Store a constraint observed by an agent in real time.

        Call this tool when you notice a mistake, receive a correction, or
        learn a rule you want Cortex to remember for future sessions.

        Args:
            code_context: The code snippet or file path where the issue occurred.
            error_context: The error message, traceback, or description of what went wrong.
            learned_rule: The rule you learned — what to never do and what to do instead.

        Returns:
            JSON with constraint_id and status.
        """
        try:
            constraint = distiller.distill_raw_signal(
                code_context=code_context,
                error_context=error_context,
                learned_rule=learned_rule,
            )
            save_constraint(repo_root, constraint)
            return json.dumps({
                "status": "stored",
                "constraint_id": constraint.constraint_id,
                "context": constraint.context,
                "confidence": constraint.confidence,
                "never_do": constraint.never_do,
                "instead": constraint.instead,
            })
        except RuntimeError as exc:
            return json.dumps({"status": "error", "message": str(exc)})
        except Exception as exc:
            return json.dumps({
                "status": "error",
                "message": f"Failed to extract constraint: {exc}",
            })

    return mcp
