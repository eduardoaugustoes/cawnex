"""cawnex setup — configure individual settings."""

import asyncio
import click
from rich.console import Console
from rich.prompt import Prompt
from cryptography.fernet import Fernet

from cawnex_cli import config as cfg

console = Console()


@click.group()
def setup():
    """⚙️  Configure Cawnex settings."""
    pass


@setup.command("anthropic")
def setup_anthropic():
    """Set Anthropic API key."""
    api_key = Prompt.ask("Anthropic API key", password=True)

    console.print("Validating...", end="")
    valid = asyncio.run(_validate(api_key))
    console.print(f" [green]✓[/]" if valid else " [red]✗ Invalid[/]")

    if valid or click.confirm("Save anyway?"):
        cfg.set_key("anthropic_api_key", api_key)

        fk = cfg.get("fernet_key")
        if fk:
            encrypted = Fernet(fk.encode()).encrypt(api_key.encode()).decode()
            cfg.set_key("anthropic_api_key_encrypted", encrypted)

        console.print("[green]✓ Saved[/]")


@setup.command("github")
def setup_github():
    """Set GitHub token."""
    token = Prompt.ask("GitHub PAT (repo scope)", password=True)
    cfg.set_key("github_token", token)
    console.print("[green]✓ Saved[/]")


@setup.command("repo")
@click.argument("repo")
def setup_repo(repo: str):
    """Set default repository (owner/repo)."""
    cfg.set_key("default_repo", repo)
    console.print(f"[green]✓ Default repo: {repo}[/]")


@setup.command("show")
def setup_show():
    """Show current configuration."""
    config = cfg.load_config()
    for key, value in config.items():
        if "key" in key.lower() or "token" in key.lower() or "encrypted" in key.lower():
            if isinstance(value, str) and len(value) > 12:
                value = value[:8] + "..." + value[-4:]
        console.print(f"  [cyan]{key}[/]: {value}")

    if not config:
        console.print("[dim]  No configuration found. Run: cawnex init[/]")


async def _validate(api_key: str) -> bool:
    import anthropic
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        await client.messages.create(
            model="claude-haiku-4-6", max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        return True
    except anthropic.AuthenticationError:
        return False
    except Exception:
        return True
