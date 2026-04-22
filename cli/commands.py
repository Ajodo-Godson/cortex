"""Supporting CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import click
import yaml

from agents.distiller import Distiller
from core.sample_data import sample_correction_event
from core.session import SessionManager
from core.storage import append_session_record
from core.storage import load_constraint
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
@click.option("--filter", "filter_text", type=str, default=None, help="Filter constraints by id, context, or service.")
def constraints_command(filter_text: str | None) -> None:
    """List stored constraints."""
    constraints = load_constraints(Path.cwd())
    if not constraints:
        click.echo("No stored constraints found.")
        return
    if filter_text:
        needle = filter_text.lower()
        constraints = [
            constraint
            for constraint in constraints
            if needle in constraint.constraint_id.lower()
            or needle in constraint.context.lower()
            or any(needle in service.lower() for service in constraint.scope.services)
        ]
    if not constraints:
        click.echo("No constraints matched that filter.")
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
    """Show one stored constraint."""
    if constraint_id is None:
        click.echo("Provide a constraint id.")
        return
    path = Path.cwd() / ".cortex" / "constraints" / f"{constraint_id}.yaml"
    if not path.exists():
        raise click.ClickException(f"Constraint not found: {constraint_id}")
    constraint = load_constraint(path)
    click.echo(yaml.safe_dump(constraint.model_dump(mode="json"), sort_keys=False, allow_unicode=False))


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
        append_session_record(log_path, sample_correction_event())

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
