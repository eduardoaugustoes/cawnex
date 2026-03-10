"""cawnex run — start the worker (The Murder)."""

import asyncio
import os
import click
from rich.console import Console

from cawnex_cli import config as cfg

console = Console()


@click.command()
def run():
    """🚀 Start The Murder — worker that processes tasks."""
    config = cfg.load_config()

    if not config.get("anthropic_api_key"):
        console.print("[red]No Anthropic API key configured. Run: cawnex setup anthropic[/]")
        return

    # Set env vars for the worker
    os.environ["CAWNEX_DATABASE_URL"] = config.get("database_url", "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex")
    os.environ["CAWNEX_REDIS_URL"] = config.get("redis_url", "redis://localhost:6380")
    os.environ["CAWNEX_FERNET_KEY"] = config.get("fernet_key", "")
    os.environ["CAWNEX_GITHUB_TOKEN"] = config.get("github_token", "")

    console.print("[bold]🐦‍⬛ Starting The Murder...[/]")
    console.print("[dim]Listening for tasks on Redis Stream. Ctrl+C to stop.[/]")
    console.print()

    from cawnex_worker.murder import Murder

    murder = Murder(
        database_url=os.environ["CAWNEX_DATABASE_URL"],
        redis_url=os.environ["CAWNEX_REDIS_URL"],
        fernet_key=os.environ["CAWNEX_FERNET_KEY"],
        github_token=os.environ.get("CAWNEX_GITHUB_TOKEN"),
    )

    try:
        asyncio.run(murder.start())
    except KeyboardInterrupt:
        console.print("\n[dim]The Murder sleeps.[/]")
