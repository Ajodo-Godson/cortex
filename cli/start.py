"""Implementation of `cortex start`."""

from __future__ import annotations

from pathlib import Path

import click

from agents.bootstrapper import Bootstrapper
from agents.observer import ObserverManager
from agents.retriever import Retriever
from core.session import SessionManager
from core.storage import ensure_cortex_dirs
from templates.renderer import render_cortex_markdown


@click.command()
@click.option("--dry-run", is_flag=True, help="Show what would be injected without writing CORTEX.md.")
@click.option("--verbose", is_flag=True, help="Show retrieval reasoning.")
@click.option("--boost", type=str, default=None, help="Boost retrieval toward a given domain.")
@click.option("--no-bootstrap", is_flag=True, help="Skip first-run bootstrap prompt.")
def start_command(dry_run: bool, verbose: bool, boost: str | None, no_bootstrap: bool) -> None:
    """Start a CORTEX session in the current repository."""
    repo_root = Path.cwd()
    session_manager = SessionManager(repo_root)

    if not session_manager.is_git_repo():
        raise click.ClickException("Current directory is not a git repository.")

    active = session_manager.load_active_session()
    if session_manager.is_session_active(active):
        raise click.ClickException("A CORTEX session is already active in this repo.")

    orphan = session_manager.detect_orphaned_session()
    if orphan is not None:
        click.echo(
            f"Previous session ended without 'cortex stop' ({orphan.started_at}). "
            "Run 'cortex distill' after review if you want to recover it."
        )

    first_run = not session_manager.cortex_dir.exists()
    ensure_cortex_dirs(repo_root)

    if first_run and not no_bootstrap:
        should_bootstrap = click.confirm(
            "No CORTEX library found. Initialize and bootstrap from git history?",
            default=True,
        )
        if should_bootstrap:
            Bootstrapper(repo_root).run_initial_bootstrap()

    retriever = Retriever(repo_root)
    result = retriever.retrieve(boost=boost, verbose=verbose)
    cortex_markdown = render_cortex_markdown(
        repo_name=repo_root.name,
        branch_name=session_manager.get_branch_name(),
        constraints=result.constraints,
    )

    if dry_run:
        click.echo(cortex_markdown)
        click.echo("")
        click.echo("Dry run complete. No session started.")
        return

    cortex_md_path = repo_root / "CORTEX.md"
    cortex_md_path.write_text(cortex_markdown, encoding="utf-8")

    observer = ObserverManager(repo_root)
    observer_state = observer.start()
    session = session_manager.start_session(observer_pid=observer_state.pid)

    click.echo(f"Repo:       {repo_root.name}")
    click.echo(f"Library:    initialized at {session_manager.cortex_dir}")
    click.echo(f"Retrieved:  {len(result.constraints)} constraints injected into CORTEX.md")
    click.echo(f"Observer:   running (PID {observer_state.pid})")
    click.echo(f"Session:    {session.started_at}")
    click.echo("")
    click.echo("Ready. Run Claude Code or Codex as normal.")
    click.echo("CORTEX is watching. Run 'cortex stop' when done.")
