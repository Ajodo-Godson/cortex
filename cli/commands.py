"""Supporting CLI commands."""

from __future__ import annotations

from pathlib import Path

import click

from core.session import SessionManager


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
    """Stub constraints command."""
    click.echo("Constraint listing is not implemented yet.")


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
def distill_command() -> None:
    """Stub distill command."""
    click.echo("Manual distillation is not implemented yet.")


@click.command("garden")
def garden_command() -> None:
    """Stub garden command."""
    click.echo("Gardener is not implemented yet.")


@click.command("view")
def view_command() -> None:
    """Stub view command."""
    click.echo("Viewer launch is not implemented yet.")
