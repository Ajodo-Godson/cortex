"""Main CLI entry point for CORTEX."""

from __future__ import annotations

import click
from dotenv import load_dotenv

load_dotenv()

from cli.commands import bootstrap_command
from cli.commands import constraints_command
from cli.commands import diff_command
from cli.commands import distill_command
from cli.commands import garden_command
from cli.commands import mcp_command
from cli.commands import record_command
from cli.commands import signal_command
from cli.commands import show_command
from cli.commands import status_command
from cli.commands import view_command
from cli.start import start_command
from cli.stop import stop_command


@click.group()
def main() -> None:
    """CORTEX command line interface."""


main.add_command(start_command, name="start")
main.add_command(stop_command, name="stop")
main.add_command(status_command, name="status")
main.add_command(constraints_command, name="constraints")
main.add_command(diff_command, name="diff")
main.add_command(show_command, name="show")
main.add_command(bootstrap_command, name="bootstrap")
main.add_command(distill_command, name="distill")
main.add_command(record_command, name="record")
main.add_command(signal_command, name="signal")
main.add_command(mcp_command, name="mcp")
main.add_command(garden_command, name="garden")
main.add_command(view_command, name="view")


if __name__ == "__main__":
    main()
