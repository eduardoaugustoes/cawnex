"""cawnex status — system health check."""

import asyncio
import subprocess
import click
from rich.console import Console
from rich.table import Table

from cawnex_cli import config as cfg

console = Console()


@click.command()
def status():
    """🏥 Check system health — Docker, DB, Redis, config."""
    table = Table(title="🐦‍⬛ Cawnex Status", show_header=True, border_style="dim")
    table.add_column("Component", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    # Docker
    r = subprocess.run(["docker", "info"], capture_output=True, text=True)
    table.add_row("Docker", _ok(r.returncode == 0), "")

    # PostgreSQL
    db_ok, db_detail = asyncio.run(_check_db())
    table.add_row("PostgreSQL", _ok(db_ok), db_detail)

    # Redis
    redis_ok, redis_detail = asyncio.run(_check_redis())
    table.add_row("Redis", _ok(redis_ok), redis_detail)

    # Config
    config = cfg.load_config()
    table.add_row("Fernet Key", _ok(bool(config.get("fernet_key"))), "")

    # LLM mode
    llm_mode = config.get("llm_mode", "not configured")
    if config.get("use_subscription"):
        table.add_row("LLM Mode", "[green]✓ OK[/]", "subscription (Claude Max)")
    elif config.get("anthropic_api_key"):
        table.add_row("LLM Mode", "[green]✓ OK[/]", f"api_key ({_mask(config['anthropic_api_key'])})")
    else:
        table.add_row("LLM Mode", "[red]✗ DOWN[/]", "not configured")
    table.add_row(
        "GitHub Token",
        _ok(bool(config.get("github_token"))),
        _mask(config.get("github_token", "")),
    )
    table.add_row("Default Repo", _ok(bool(config.get("default_repo"))), config.get("default_repo", ""))

    console.print(table)

    # Summary
    all_ok = all([
        r.returncode == 0, db_ok, redis_ok,
        config.get("fernet_key"),
        config.get("anthropic_api_key") or config.get("use_subscription"),
    ])
    if all_ok:
        console.print("\n[bold green]✅ All systems operational[/]")
    else:
        console.print("\n[bold yellow]⚠️  Some components need attention. Run: cawnex init[/]")


def _ok(condition: bool) -> str:
    return "[green]✓ OK[/]" if condition else "[red]✗ DOWN[/]"


def _mask(value: str) -> str:
    if not value or len(value) < 12:
        return ""
    return value[:8] + "..." + value[-4:]


async def _check_db() -> tuple[bool, str]:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        url = cfg.get("database_url", "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex")
        engine = create_async_engine(url)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT count(*) FROM tenants"))
            count = result.scalar()
        await engine.dispose()
        return True, f"{count} tenant(s)"
    except Exception as e:
        return False, str(e)[:60]


async def _check_redis() -> tuple[bool, str]:
    try:
        from redis.asyncio import Redis
        url = cfg.get("redis_url", "redis://localhost:6380")
        r = Redis.from_url(url)
        info = await r.info("server")
        await r.aclose()
        return True, f"v{info.get('redis_version', '?')}"
    except Exception as e:
        return False, str(e)[:60]
