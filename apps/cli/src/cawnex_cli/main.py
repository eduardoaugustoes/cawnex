"""Cawnex CLI — main entry point."""

import click
from rich.console import Console

from cawnex_cli.commands.init import init
from cawnex_cli.commands.setup import setup
from cawnex_cli.commands.status import status
from cawnex_cli.commands.agents import agents
from cawnex_cli.commands.run import run
from cawnex_cli.commands.roost import roost
from cawnex_cli.commands.issue import issue

console = Console()

BANNER = """[bold white]
   ██████╗ █████╗ ██╗    ██╗███╗   ██╗███████╗██╗  ██╗
  ██╔════╝██╔══██╗██║    ██║████╗  ██║██╔════╝╚██╗██╔╝
  ██║     ███████║██║ █╗ ██║██╔██╗ ██║█████╗   ╚███╔╝
  ██║     ██╔══██║██║███╗██║██║╚██╗██║██╔══╝   ██╔██╗
  ╚██████╗██║  ██║╚███╔███╔╝██║ ╚████║███████╗██╔╝ ██╗
   ╚═════╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝[/]
[dim]  Coordinated Intelligence[/]
"""


@click.group()
@click.version_option(version="0.1.0", prog_name="cawnex")
def cli():
    """🐦‍⬛ Cawnex — Coordinated Intelligence.

    Multi-agent orchestration that turns issues into shipped code.
    """
    pass


cli.add_command(init)
cli.add_command(setup)
cli.add_command(status)
cli.add_command(agents)
cli.add_command(run)
cli.add_command(roost)
cli.add_command(issue)


if __name__ == "__main__":
    cli()
