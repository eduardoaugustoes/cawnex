"""cawnex roost — dashboard view of executions."""

import asyncio
import click
from rich.console import Console
from rich.table import Table

from cawnex_cli import config as cfg

console = Console()

STATUS_ICONS = {
    "pending": "⏳",
    "refining": "🔍",
    "awaiting_approval": "🤚",
    "approved": "✅",
    "in_progress": "🐦",
    "completed": "✅",
    "failed": "💀",
    "rejected": "❌",
}

EXEC_ICONS = {
    "queued": "⏳",
    "running": "🔄",
    "completed": "✅",
    "failed": "💀",
    "cancelled": "🚫",
    "retrying": "🔄",
}


@click.command()
@click.option("--limit", default=10, help="Number of tasks to show.")
def roost(limit: int):
    """📊 The Roost — dashboard of recent tasks and executions."""
    data = asyncio.run(_fetch_dashboard(limit))

    if not data["tasks"]:
        console.print("[dim]No tasks found. Submit one: cawnex issue <number>[/]")
        return

    # Summary
    summary = Table(title="📊 The Roost", show_header=True, border_style="dim")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", justify="right")

    summary.add_row("Total Tasks", str(data["total_tasks"]))
    summary.add_row("Completed", f"[green]{data['completed']}[/]")
    summary.add_row("Failed", f"[red]{data['failed']}[/]" if data["failed"] else "0")
    summary.add_row("In Progress", f"[yellow]{data['in_progress']}[/]" if data["in_progress"] else "0")
    summary.add_row("Total Cost", f"${data['total_cost']:.4f}")
    summary.add_row("Total Tokens", f"{data['total_tokens']:,}")

    console.print(summary)
    console.print()

    # Tasks table
    tasks_table = Table(title="Recent Tasks", show_header=True, border_style="dim")
    tasks_table.add_column("ID", style="dim")
    tasks_table.add_column("Title")
    tasks_table.add_column("Status")
    tasks_table.add_column("Cost", justify="right")
    tasks_table.add_column("Tokens", justify="right")

    for task in data["tasks"]:
        icon = STATUS_ICONS.get(task["status"], "❓")
        tasks_table.add_row(
            str(task["id"]),
            task["title"][:50],
            f"{icon} {task['status']}",
            f"${task['cost']:.4f}",
            f"{task['tokens']:,}",
        )

    console.print(tasks_table)

    # Executions
    if data["executions"]:
        console.print()
        exec_table = Table(title="Recent Executions", show_header=True, border_style="dim")
        exec_table.add_column("Task", style="dim")
        exec_table.add_column("Agent")
        exec_table.add_column("Status")
        exec_table.add_column("Duration", justify="right")
        exec_table.add_column("Cost", justify="right")

        for ex in data["executions"]:
            icon = EXEC_ICONS.get(ex["status"], "❓")
            duration = f"{ex['duration']:.1f}s" if ex["duration"] else "-"
            exec_table.add_row(
                str(ex["task_id"]),
                ex["agent"],
                f"{icon} {ex['status']}",
                duration,
                f"${ex['cost']:.4f}",
            )

        console.print(exec_table)


async def _fetch_dashboard(limit: int) -> dict:
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from cawnex_core.models import Task, Execution, Tenant

    url = cfg.get("database_url", "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex")
    engine = create_async_engine(url)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    data = {
        "tasks": [], "executions": [],
        "total_tasks": 0, "completed": 0, "failed": 0, "in_progress": 0,
        "total_cost": 0.0, "total_tokens": 0,
    }

    async with sf() as session:
        tenant = (await session.execute(
            select(Tenant).where(Tenant.slug == "cawnex-dogfood")
        )).scalar_one_or_none()
        if not tenant:
            await engine.dispose()
            return data

        # Tasks
        tasks = (await session.execute(
            select(Task)
            .where(Task.tenant_id == tenant.id)
            .order_by(Task.created_at.desc())
            .limit(limit)
        )).scalars().all()

        for t in tasks:
            data["tasks"].append({
                "id": t.id, "title": t.title, "status": t.status,
                "cost": t.total_cost_usd, "tokens": t.total_tokens,
            })
            data["total_cost"] += t.total_cost_usd
            data["total_tokens"] += t.total_tokens

        # Counts
        data["total_tasks"] = (await session.execute(
            select(func.count()).select_from(Task).where(Task.tenant_id == tenant.id)
        )).scalar() or 0
        data["completed"] = (await session.execute(
            select(func.count()).select_from(Task).where(Task.tenant_id == tenant.id, Task.status == "completed")
        )).scalar() or 0
        data["failed"] = (await session.execute(
            select(func.count()).select_from(Task).where(Task.tenant_id == tenant.id, Task.status == "failed")
        )).scalar() or 0
        data["in_progress"] = (await session.execute(
            select(func.count()).select_from(Task).where(Task.tenant_id == tenant.id, Task.status == "in_progress")
        )).scalar() or 0

        # Recent executions
        execs = (await session.execute(
            select(Execution).order_by(Execution.created_at.desc()).limit(10)
        )).scalars().all()

        for ex in execs:
            data["executions"].append({
                "task_id": ex.task_id, "agent": ex.agent_name,
                "status": ex.status, "duration": ex.duration_seconds,
                "cost": ex.cost_usd,
            })

    await engine.dispose()
    return data
