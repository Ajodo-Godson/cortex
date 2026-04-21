"""Implementation of `cortex stop`."""

from __future__ import annotations

from pathlib import Path

import click

from agents.distiller import Distiller
from agents.observer import ObserverManager
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

    observer = ObserverManager(repo_root)
    observer.stop(session.observer_pid)

    distiller = Distiller(repo_root)
    distill_result = distiller.run(session.log_path)

    cortex_md = repo_root / "CORTEX.md"
    if cortex_md.exists():
        cortex_md.unlink()

    session_manager.end_session()

    click.echo("Session ended.")
    click.echo(f"Correction events detected: {distill_result.correction_events}")
    click.echo(f"New constraints added:      {distill_result.new_constraints}")
    click.echo(f"Constraints updated:       {distill_result.updated_constraints}")
