"""cawnex agents — list and manage crows."""

import asyncio
import click
from rich.console import Console
from rich.table import Table

from cawnex_cli import config as cfg

console = Console()


@click.command("agents")
def agents():
    """🐦 List configured agents (crows)."""
    result = asyncio.run(_list_agents())
    if not result:
        console.print("[dim]No agents found. Run: cawnex init[/]")
        return

    table = Table(title="🐦 Crows", show_header=True, border_style="dim")
    table.add_column("Slug", style="cyan")
    table.add_column("Name")
    table.add_column("Model", style="dim")
    table.add_column("Tools")
    table.add_column("Status")

    for agent in result:
        status = "[green]ready[/]" if agent.is_active else "[dim]disabled[/]"
        tools = ", ".join(agent.tool_packs) if agent.tool_packs else ""
        table.add_row(agent.slug, agent.name, agent.model, tools, status)

    console.print(table)


async def _list_agents():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from cawnex_core.models import AgentDefinition, Tenant

    url = cfg.get("database_url", "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex")
    engine = create_async_engine(url)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as session:
        tenant = (await session.execute(
            select(Tenant).where(Tenant.slug == "cawnex-dogfood")
        )).scalar_one_or_none()
        if not tenant:
            await engine.dispose()
            return []

        result = await session.execute(
            select(AgentDefinition).where(AgentDefinition.tenant_id == tenant.id)
        )
        agents = result.scalars().all()

    await engine.dispose()
    return agents
