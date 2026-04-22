"""Supporting CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from agents.distiller import Distiller
from core.sample_data import sample_correction_event
from core.session import SessionManager
from core.storage import load_constraints


@click.command("status")
def status_command() -> None:
    """Show current session status."""
    session_manager = SessionManager(Path.cwd())
    session = session_manager.load_active_session()

    if session is None:
        click.echo("CORTEX is not running in this repo.")
        return

    if not session_manager.is_session_active(session):
        click.echo(f"Stale session lock detected from: {session.started_at}")
        click.echo(f"Observer PID:               {session.observer_pid} (not running)")
        click.echo(f"Session log:                {session.log_path}")
        click.echo("Run 'cortex start' to recover automatically or 'cortex distill' after review.")
        return

    click.echo(f"Active session since: {session.started_at}")
    click.echo(f"Observer PID:         {session.observer_pid}")
    click.echo(f"Session log:          {session.log_path}")


@click.command("constraints")
def constraints_command() -> None:
    """List stored constraints."""
    constraints = load_constraints(Path.cwd())
    if not constraints:
        click.echo("No stored constraints found.")
        return
    for constraint in constraints:
        click.echo(f"{constraint.constraint_id}  {constraint.context}  confidence={constraint.confidence:.2f}")


@click.command("diff")
def diff_command() -> None:
    """Stub diff command."""
    click.echo("Constraint diff is not implemented yet.")


@click.command("show")
@click.argument("constraint_id", required=False)
def show_command(constraint_id: str | None) -> None:
    """Stub show command."""
    if constraint_id is None:
        click.echo("Provide a constraint id.")
        return
    click.echo(f"Constraint detail is not implemented yet for: {constraint_id}")


@click.command("bootstrap")
@click.option("--since", type=str, default=None, help="Limit bootstrap history.")
def bootstrap_command(since: str | None) -> None:
    """Stub bootstrap command."""
    scope = since if since else "full history"
    click.echo(f"Bootstrap is not implemented yet. Requested scope: {scope}")


@click.command("distill")
@click.option("--log", "log_path", type=click.Path(path_type=Path), default=None, help="Distill a specific session log.")
@click.option("--sample", is_flag=True, help="Append a sample correction event before distilling.")
def distill_command(log_path: Path | None, sample: bool) -> None:
    """Manually trigger distillation."""
    repo_root = Path.cwd()
    session_manager = SessionManager(repo_root)
    session = session_manager.load_active_session()

    if log_path is None:
        if session is None:
            raise click.ClickException("No active session found. Pass --log to distill a specific session log.")
        log_path = Path(session.log_path)

    if sample:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sample_correction_event()) + "\n")

    result = Distiller(repo_root).run(log_path)
    click.echo(f"Correction events detected: {result.correction_events}")
    click.echo(f"New constraints added:      {result.new_constraints}")
    click.echo(f"Constraints updated:       {result.updated_constraints}")


@click.command("garden")
def garden_command() -> None:
    """Stub garden command."""
    click.echo("Gardener is not implemented yet.")


@click.command("view")
def view_command() -> None:
    """Stub view command."""
    click.echo("Viewer launch is not implemented yet.")
