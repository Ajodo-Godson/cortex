"""Supporting CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import click
import yaml

from agents.bootstrapper import Bootstrapper
from agents.distiller import Distiller
from core.events import append_correction_event
from core.events import queue_correction_event
from core.events import queue_signal
from core.sample_data import sample_correction_event
from core.sample_data import sample_correction_signal
from core.session import SessionManager
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
@click.option("--since", "since_days", type=int, default=90, show_default=True, help="Number of days of git history to mine.")
def bootstrap_command(since_days: int) -> None:
    """Mine git history and seed the constraint library."""
    repo_root = Path.cwd()
    click.echo(f"Bootstrapping from last {since_days} days of git history...")
    added = Bootstrapper(repo_root).run_initial_bootstrap(since_days=since_days)
    if added:
        click.echo(f"Done. {added} constraint(s) added to the library.")
    else:
        click.echo("Done. Check .cortex/bootstrap.txt for details.")


@click.command("distill")
@click.option("--log", "log_path", type=click.Path(path_type=Path), default=None, help="Distill a specific session log.")
@click.option("--sample", is_flag=True, help="Append a sample correction event before distilling.")
def distill_command(log_path: Path | None, sample: bool) -> None:
    """Manually trigger distillation."""
    if log_path is not None:
        # Derive repo_root from the log path: <repo_root>/.cortex/sessions/<name>.log
        repo_root = log_path.resolve().parent.parent.parent
    else:
        repo_root = Path.cwd()

    session_manager = SessionManager(repo_root)
    session = session_manager.load_active_session()

    if log_path is None:
        if session is None:
            raise click.ClickException("No active session found. Pass --log to distill a specific session log.")
        log_path = Path(session.log_path)

    if sample:
        append_correction_event(log_path, sample_correction_event())

    result = Distiller(repo_root).run(log_path)
    click.echo(f"Correction events detected: {result.correction_events}")
    click.echo(f"New constraints added:      {result.new_constraints}")
    click.echo(f"Constraints updated:       {result.updated_constraints}")


@click.command("record")
@click.option("--log", "log_path", type=click.Path(path_type=Path), default=None, help="Write to a specific session log.")
@click.option("--sample", is_flag=True, help="Append a sample correction event.")
@click.option("--event-file", type=click.Path(exists=True, path_type=Path), default=None, help="Append a correction event from a JSON file.")
@click.option("--queue", "queue_for_observer", is_flag=True, help="Queue the event for observer ingestion instead of writing directly to the log.")
def record_command(log_path: Path | None, sample: bool, event_file: Path | None, queue_for_observer: bool) -> None:
    """Append a validated correction event to a session log without distilling it."""
    repo_root = Path.cwd()
    session_manager = SessionManager(repo_root)
    session = session_manager.load_active_session()

    if queue_for_observer:
        if session is None:
            raise click.ClickException("No active session found. Start a session before queueing an observer event.")
    elif log_path is None:
        if session is None:
            raise click.ClickException("No active session found. Pass --log to write to a specific session log.")
        log_path = Path(session.log_path)

    if sample == bool(event_file):
        raise click.ClickException("Choose exactly one of --sample or --event-file.")

    event_payload = sample_correction_event() if sample else json.loads(event_file.read_text(encoding="utf-8"))

    if queue_for_observer:
        queued_path = queue_correction_event(repo_root, event_payload)
        event_id = queued_path.stem
        click.echo(f"Queued correction event:    {event_id}")
        click.echo(f"Inbox file:                 {queued_path}")
        return

    if sample:
        payload = append_correction_event(log_path, event_payload)
    else:
        payload = append_correction_event(log_path, event_payload)

    click.echo(f"Recorded correction event:  {payload['event_id']}")
    click.echo(f"Constraint candidate:       {payload['constraint_key']}-{int(payload['sequence']):03d}")
    click.echo(f"Session log:                {log_path}")


@click.command("signal")
@click.option("--sample", "sample_kind", type=click.Choice(["deadlock", "token_refresh", "webhook_signature"]), required=True, help="Queue a sample observer signal.")
def signal_command(sample_kind: str) -> None:
    """Queue a simple observer signal for worker-side classification."""
    repo_root = Path.cwd()
    session_manager = SessionManager(repo_root)
    session = session_manager.load_active_session()
    if session is None or not session_manager.is_session_active(session):
        raise click.ClickException("No active session found. Start a session before queueing an observer signal.")

    queued_path = queue_signal(repo_root, sample_correction_signal(sample_kind))
    click.echo(f"Queued observer signal:     {queued_path.stem}")
    click.echo(f"Signal kind:                {sample_kind}")
    click.echo(f"Inbox file:                 {queued_path}")


@click.command("mcp")
@click.option(
    "--transport",
    default="stdio",
    type=click.Choice(["stdio", "sse"]),
    show_default=True,
    help="MCP transport protocol.",
)
def mcp_command(transport: str) -> None:
    """Start the Cortex MCP server for agent tool integration."""
    try:
        from agents.mcp_server import create_mcp_server
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc

    server = create_mcp_server(Path.cwd())
    try:
        server.run(transport=transport)  # type: ignore[union-attr]
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


@click.command("garden")
def garden_command() -> None:
    """Stub garden command."""
    click.echo("Gardener is not implemented yet.")


@click.command("view")
def view_command() -> None:
    """Stub view command."""
    click.echo("Viewer launch is not implemented yet.")
