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

    use_subscription = config.get("use_subscription", False)
    if not use_subscription and not config.get("anthropic_api_key"):
        console.print("[red]No LLM configured. Run: cawnex init[/]")
        return

    console.print("[bold]🐦‍⬛ Starting The Murder...[/]")
    mode = "subscription" if use_subscription else "api_key"
    console.print(f"[dim]Mode: {mode} | Listening on Redis Stream. Ctrl+C to stop.[/]")
    console.print()

    from cawnex_worker.murder import Murder

    murder = Murder(
        database_url=config.get("database_url", "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex"),
        redis_url=config.get("redis_url", "redis://localhost:6380"),
        fernet_key=config.get("fernet_key", ""),
        github_token=config.get("github_token"),
        use_subscription=use_subscription,
    )

    try:
        asyncio.run(murder.start())
    except KeyboardInterrupt:
        console.print("\n[dim]The Murder sleeps.[/]")
