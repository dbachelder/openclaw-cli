"""Entry point for the openclaw-cli."""

import click

from openclaw_cli import __version__
from openclaw_cli.commands.tail import tail


@click.group()
@click.version_option(version=__version__, prog_name="ocli")
def cli() -> None:
    """CLI utilities for OpenClaw."""


cli.add_command(tail)
