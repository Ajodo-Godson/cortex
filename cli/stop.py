"""Implementation of `cortex stop`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import click

from agents.distiller import Distiller
from agents.observer import ObserverManager
from core.inject import remove_constraints
from core.session import SessionManager


@click.command()
def stop_command() -> None:
    """Stop the active CORTEX session."""
    repo_root = Path.cwd()
    session_manager = SessionManager(repo_root)
    session = session_manager.load_active_session()

    if session is None:
        click.echo("No active CORTEX session found.")
        return

    session_start = datetime.fromisoformat(session.started_at.replace("Z", "+00:00"))
    constraints_dir = repo_root / ".cortex" / "constraints"

    observer = ObserverManager(repo_root)
    observer.stop(session.observer_pid)

    distiller = Distiller(repo_root)
    distill_result = distiller.run(session.log_path)

    # Count constraints saved directly via cortex_flag during this session
    mcp_flagged = 0
    if constraints_dir.exists():
        for f in constraints_dir.glob("*.yaml"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime >= session_start:
                mcp_flagged += 1
    mcp_flagged -= distill_result.new_constraints  # avoid double-counting

    remove_constraints(repo_root)
    session_manager.end_session()

    click.echo("Session ended.")
    click.echo(f"Correction events detected: {distill_result.correction_events}")
    click.echo(f"New constraints added:      {distill_result.new_constraints + max(mcp_flagged, 0)}")
    if mcp_flagged > 0:
        click.echo(f"  via distiller:           {distill_result.new_constraints}")
        click.echo(f"  via cortex_flag (MCP):   {mcp_flagged}")
    click.echo(f"Constraints updated:       {distill_result.updated_constraints}")
