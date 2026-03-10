"""cawnex watch — real-time terminal dashboard of The Murder."""

import asyncio
import click
from datetime import datetime, timezone
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from redis.asyncio import Redis

from cawnex_cli import config as cfg

console = Console()

STATUS_STYLE = {
    "pending": ("⏳", "dim"),
    "refining": ("🔍", "yellow"),
    "awaiting_approval": ("🤚", "yellow bold"),
    "approved": ("✅", "green"),
    "in_progress": ("🐦", "cyan"),
    "completed": ("✅", "green"),
    "failed": ("💀", "red"),
    "rejected": ("❌", "red"),
    "queued": ("⏳", "dim"),
    "running": ("🔄", "cyan"),
    "cancelled": ("🚫", "dim"),
    "retrying": ("🔄", "yellow"),
}


@click.command()
@click.option("--task", "-t", type=int, default=None, help="Watch a specific task ID.")
def watch(task: int | None):
    """👁️  Live dashboard — watch The Murder work in real-time."""
    try:
        asyncio.run(_watch_loop(task))
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching.[/]")


async def _watch_loop(task_id: int | None):
    config = cfg.load_config()
    redis_url = config.get("redis_url", "redis://localhost:6380")
    db_url = config.get("database_url", "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex")

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload
    from cawnex_core.models import Task, Execution, ExecutionEvent, Tenant

    engine = create_async_engine(db_url)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = Redis.from_url(redis_url, decode_responses=True)

    # Event log buffer
    event_log: list[str] = []
    max_events = 30

    # Subscribe to Redis events
    stream_key = f"cawnex:events:{task_id}" if task_id else None

    with Live(console=console, refresh_per_second=2, screen=True) as live:
        last_stream_id = "0"

        while True:
            # Fetch current state from DB
            async with sf() as session:
                tenant = (await session.execute(
                    select(Tenant).where(Tenant.slug == "cawnex-dogfood")
                )).scalar_one_or_none()

                if not tenant:
                    live.update(Panel("[red]No tenant found[/]"))
                    await asyncio.sleep(2)
                    continue

                # Tasks
                task_query = select(Task).where(Task.tenant_id == tenant.id)
                if task_id:
                    task_query = task_query.where(Task.id == task_id)
                task_query = task_query.order_by(Task.created_at.desc()).limit(10)
                tasks = (await session.execute(task_query)).scalars().all()

                # Executions
                exec_query = select(Execution).order_by(Execution.created_at.desc()).limit(15)
                if task_id:
                    exec_query = select(Execution).where(
                        Execution.task_id == task_id
                    ).order_by(Execution.created_at.desc())
                executions = (await session.execute(exec_query)).scalars().all()

                # Recent events
                event_query = select(ExecutionEvent).order_by(
                    ExecutionEvent.created_at.desc()
                ).limit(10)
                if task_id and executions:
                    exec_ids = [e.id for e in executions]
                    event_query = select(ExecutionEvent).where(
                        ExecutionEvent.execution_id.in_(exec_ids)
                    ).order_by(ExecutionEvent.created_at.desc()).limit(10)
                db_events = (await session.execute(event_query)).scalars().all()

                # Aggregates
                total = (await session.execute(
                    select(func.count()).select_from(Task).where(Task.tenant_id == tenant.id)
                )).scalar() or 0
                total_cost = sum(t.total_cost_usd for t in tasks)
                total_tokens = sum(t.total_tokens for t in tasks)

            # Poll Redis for live events
            if stream_key:
                try:
                    messages = await redis.xread(
                        {stream_key: last_stream_id}, count=10, block=100
                    )
                    if messages:
                        for _, entries in messages:
                            for msg_id, data in entries:
                                last_stream_id = msg_id
                                ts = data.get("timestamp", "")[:19]
                                content = data.get("content", "")[:80]
                                event_log.append(f"[dim]{ts}[/] {content}")
                                if len(event_log) > max_events:
                                    event_log.pop(0)
                except Exception:
                    pass

            # Also add DB events to log
            for ev in reversed(db_events):
                ts = ev.created_at.strftime("%H:%M:%S") if ev.created_at else ""
                line = f"[dim]{ts}[/] [{ev.event_type}] {ev.content[:80]}"
                if line not in event_log:
                    event_log.append(line)
                    if len(event_log) > max_events:
                        event_log.pop(0)

            # Build the dashboard
            layout = Layout()
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body"),
                Layout(name="events", size=min(len(event_log) + 4, 16)),
            )
            layout["body"].split_row(
                Layout(name="tasks"),
                Layout(name="executions"),
            )

            # Header
            now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            active = sum(1 for t in tasks if t.status in ("in_progress", "refining"))
            header_text = Text()
            header_text.append("🐦‍⬛ The Murder", style="bold white")
            header_text.append(f"  │  {now}  │  ", style="dim")
            header_text.append(f"{total} tasks", style="cyan")
            header_text.append("  │  ", style="dim")
            header_text.append(f"{active} active", style="green" if active else "dim")
            header_text.append("  │  ", style="dim")
            header_text.append(f"${total_cost:.4f}", style="yellow")
            layout["header"].update(Panel(header_text, style="white"))

            # Tasks table
            task_table = Table(show_header=True, border_style="dim", expand=True)
            task_table.add_column("ID", style="dim", width=4)
            task_table.add_column("Title", ratio=3)
            task_table.add_column("Status", width=16)
            task_table.add_column("Cost", justify="right", width=8)

            for t in tasks:
                icon, style = STATUS_STYLE.get(t.status, ("❓", ""))
                task_table.add_row(
                    str(t.id),
                    t.title[:40],
                    Text(f"{icon} {t.status}", style=style),
                    f"${t.total_cost_usd:.4f}",
                )

            layout["tasks"].update(Panel(task_table, title="Tasks", border_style="cyan"))

            # Executions table
            exec_table = Table(show_header=True, border_style="dim", expand=True)
            exec_table.add_column("Agent", ratio=2)
            exec_table.add_column("Status", width=14)
            exec_table.add_column("Time", justify="right", width=8)
            exec_table.add_column("Cost", justify="right", width=8)

            for ex in executions:
                icon, style = STATUS_STYLE.get(ex.status, ("❓", ""))
                duration = f"{ex.duration_seconds:.1f}s" if ex.duration_seconds else "..."
                exec_table.add_row(
                    ex.agent_name[:20],
                    Text(f"{icon} {ex.status}", style=style),
                    duration,
                    f"${ex.cost_usd:.4f}",
                )

            layout["executions"].update(Panel(exec_table, title="Executions", border_style="yellow"))

            # Event log
            if event_log:
                log_text = "\n".join(event_log[-max_events:])
            else:
                log_text = "[dim]Waiting for events...[/]"
            layout["events"].update(Panel(log_text, title="Live Events", border_style="green"))

            live.update(layout)
            await asyncio.sleep(1)
