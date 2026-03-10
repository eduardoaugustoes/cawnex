"""cawnex watch — interactive real-time terminal dashboard."""

import asyncio
import sys
import termios
import tty
import click
from datetime import datetime, timezone
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
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

HELP_TEXT = "[dim]↑/↓ select  │  Enter expand  │  r run  │  q quit[/]"


class WatchState:
    def __init__(self):
        self.selected_idx = 0
        self.expanded_task_id: int | None = None
        self.tasks: list = []
        self.executions: list = []
        self.events: list = []
        self.pending_key: str | None = None
        self.message: str = ""


def _read_key_nonblocking() -> str | None:
    """Read a single keypress without blocking."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        # Check if input available
        import select as sel
        if sel.select([sys.stdin], [], [], 0.0)[0]:
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                # Arrow key sequence
                if sel.select([sys.stdin], [], [], 0.05)[0]:
                    ch2 = sys.stdin.read(1)
                    if ch2 == "[" and sel.select([sys.stdin], [], [], 0.05)[0]:
                        ch3 = sys.stdin.read(1)
                        if ch3 == "A": return "up"
                        if ch3 == "B": return "down"
                return "esc"
            return ch
        return None
    except Exception:
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


@click.command()
@click.option("--task", "-t", type=int, default=None, help="Focus on a specific task ID.")
def watch(task: int | None):
    """👁️  Live dashboard — watch The Murder work in real-time.

    \b
    Controls:
      ↑/↓ or j/k  Select task
      Enter        Expand/collapse task details
      r            Run selected task through pipeline
      q            Quit
    """
    try:
        asyncio.run(_watch_loop(task))
    except KeyboardInterrupt:
        pass
    finally:
        console.print("\n[dim]Stopped watching.[/]")


async def _watch_loop(focus_task_id: int | None):
    config = cfg.load_config()
    db_url = config.get("database_url", "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex")
    redis_url = config.get("redis_url", "redis://localhost:6380")

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select, func
    from cawnex_core.models import Task, Execution, ExecutionEvent, Tenant

    engine = create_async_engine(db_url)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = Redis.from_url(redis_url, decode_responses=True)

    state = WatchState()
    if focus_task_id:
        state.expanded_task_id = focus_task_id

    with Live(console=console, refresh_per_second=4, screen=True) as live:
        while True:
            # Handle keyboard input
            key = _read_key_nonblocking()
            if key:
                await _handle_key(key, state, sf, redis, config)
                if key == "q":
                    break

            # Fetch data
            async with sf() as session:
                tenant = (await session.execute(
                    select(Tenant).where(Tenant.slug == "cawnex-dogfood")
                )).scalar_one_or_none()

                if not tenant:
                    live.update(Panel("[red]No tenant found. Run: cawnex init[/]"))
                    await asyncio.sleep(1)
                    continue

                # Tasks
                task_query = select(Task).where(Task.tenant_id == tenant.id)
                if focus_task_id:
                    task_query = task_query.where(Task.id == focus_task_id)
                tasks = (await session.execute(
                    task_query.order_by(Task.created_at.desc()).limit(20)
                )).scalars().all()
                state.tasks = tasks

                # Clamp selection
                if state.selected_idx >= len(tasks):
                    state.selected_idx = max(0, len(tasks) - 1)

                # Executions for expanded task
                execs = []
                events = []
                expanded_task = None
                if state.expanded_task_id:
                    expanded_task = next((t for t in tasks if t.id == state.expanded_task_id), None)
                    if not expanded_task:
                        # Task might not be in the current page, fetch it
                        expanded_task = (await session.execute(
                            select(Task).where(Task.id == state.expanded_task_id)
                        )).scalar_one_or_none()

                    if expanded_task:
                        execs = (await session.execute(
                            select(Execution)
                            .where(Execution.task_id == state.expanded_task_id)
                            .order_by(Execution.created_at.desc())
                        )).scalars().all()

                        if execs:
                            exec_ids = [e.id for e in execs]
                            events = (await session.execute(
                                select(ExecutionEvent)
                                .where(ExecutionEvent.execution_id.in_(exec_ids))
                                .order_by(ExecutionEvent.created_at.desc())
                                .limit(20)
                            )).scalars().all()

                state.executions = execs
                state.events = events

                # Aggregates
                total_cost = sum(t.total_cost_usd for t in tasks)
                active = sum(1 for t in tasks if t.status in ("in_progress", "refining"))

            # Build UI
            layout = _build_layout(state, tasks, execs, events, expanded_task, total_cost, active)
            live.update(layout)
            await asyncio.sleep(0.25)

    await redis.aclose()
    await engine.dispose()


async def _handle_key(key: str, state: WatchState, sf, redis, config):
    """Handle keyboard input."""
    if key in ("up", "k") and state.selected_idx > 0:
        state.selected_idx -= 1
        state.message = ""
    elif key in ("down", "j") and state.selected_idx < len(state.tasks) - 1:
        state.selected_idx += 1
        state.message = ""
    elif key in ("\r", "\n"):  # Enter
        if state.tasks:
            task = state.tasks[state.selected_idx]
            if state.expanded_task_id == task.id:
                state.expanded_task_id = None  # Collapse
                state.message = ""
            else:
                state.expanded_task_id = task.id  # Expand
                state.message = f"Expanded task #{task.id}"
    elif key == "r":
        if state.tasks:
            task = state.tasks[state.selected_idx]
            state.message = f"⚡ Queuing task #{task.id}..."
            await _queue_task(task.id, sf, redis, config)
            state.message = f"⚡ Task #{task.id} queued!"
    elif key == "q":
        pass


async def _queue_task(task_id: int, sf, redis, config):
    """Push a task to the Redis Stream for the worker to pick up."""
    from sqlalchemy import select
    from cawnex_core.models import Task, Tenant

    async with sf() as session:
        tenant = (await session.execute(
            select(Tenant).where(Tenant.slug == "cawnex-dogfood")
        )).scalar_one_or_none()
        if not tenant:
            return

        task = (await session.execute(
            select(Task).where(Task.id == task_id, Task.tenant_id == tenant.id)
        )).scalar_one_or_none()
        if not task:
            return

    redis_url = config.get("redis_url", "redis://localhost:6380")
    r = Redis.from_url(redis_url, decode_responses=True)
    await r.xadd("cawnex:tasks", {"task_id": str(task_id), "tenant_id": str(tenant.id)})
    await r.aclose()


def _build_layout(state, tasks, execs, events, expanded_task, total_cost, active):
    """Build the Rich layout."""
    layout = Layout()

    # Header
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    header = Text()
    header.append("🐦‍⬛ The Murder", style="bold white")
    header.append(f"  │  {now}  │  ", style="dim")
    header.append(f"{len(tasks)} tasks", style="cyan")
    header.append("  │  ", style="dim")
    header.append(f"{active} active", style="green" if active else "dim")
    header.append("  │  ", style="dim")
    header.append(f"${total_cost:.4f}", style="yellow")

    if state.message:
        header.append("  │  ", style="dim")
        header.append(state.message, style="bold cyan")

    if expanded_task:
        # Split: header, task detail, executions, events, help
        layout.split_column(
            Layout(Panel(header, style="white"), name="header", size=3),
            Layout(name="detail", size=8),
            Layout(name="body"),
            Layout(name="events", size=12),
            Layout(Panel(Text(HELP_TEXT), style="dim"), name="help", size=3),
        )
        layout["body"].split_row(
            Layout(name="tasks", ratio=1),
            Layout(name="executions", ratio=1),
        )

        # Task detail
        desc = (expanded_task.description or "")[:300]
        labels = expanded_task.labels or ""
        detail_text = Text()
        detail_text.append(f"#{expanded_task.id} ", style="cyan bold")
        detail_text.append(expanded_task.title, style="bold")
        detail_text.append(f"\n\n{desc}", style="dim")
        if labels:
            detail_text.append(f"\n\nLabels: {labels}", style="yellow")
        detail_text.append(f"\nStatus: {expanded_task.status}", style="")
        detail_text.append(f"  │  Cost: ${expanded_task.total_cost_usd:.4f}", style="")
        detail_text.append(f"  │  Tokens: {expanded_task.total_tokens:,}", style="dim")
        layout["detail"].update(Panel(detail_text, title="Task Detail", border_style="cyan"))

        # Events
        if events:
            event_lines = []
            for ev in reversed(events[:15]):
                ts = ev.created_at.strftime("%H:%M:%S") if ev.created_at else ""
                event_lines.append(f"[dim]{ts}[/] [{ev.event_type}] {ev.content[:100]}")
            layout["events"].update(
                Panel("\n".join(event_lines), title="Events", border_style="green")
            )
        else:
            layout["events"].update(
                Panel("[dim]No events yet. Run the task with 'r'.[/]", title="Events", border_style="green")
            )
    else:
        # Simple view: header, tasks, help
        layout.split_column(
            Layout(Panel(header, style="white"), name="header", size=3),
            Layout(name="body"),
            Layout(Panel(Text(HELP_TEXT), style="dim"), name="help", size=3),
        )
        layout["body"].split_row(
            Layout(name="tasks"),
        )

    # Tasks table (always shown)
    task_table = Table(show_header=True, border_style="dim", expand=True)
    task_table.add_column("", width=2)
    task_table.add_column("#", style="dim", width=4)
    task_table.add_column("Title", ratio=3)
    task_table.add_column("Status", width=18)
    task_table.add_column("Cost", justify="right", width=8)

    for i, t in enumerate(tasks):
        icon, style = STATUS_STYLE.get(t.status, ("❓", ""))
        selected = "▶" if i == state.selected_idx else " "
        sel_style = "bold cyan" if i == state.selected_idx else ""
        expanded = "▼" if t.id == state.expanded_task_id else ""

        task_table.add_row(
            Text(f"{selected}{expanded}", style=sel_style),
            Text(str(t.id), style=sel_style),
            Text(t.title[:50], style=sel_style),
            Text(f"{icon} {t.status}", style=style),
            f"${t.total_cost_usd:.4f}",
        )

    layout["tasks"].update(Panel(task_table, title="Tasks", border_style="cyan"))

    # Executions (only in expanded mode)
    if expanded_task and "executions" in layout:
        exec_table = Table(show_header=True, border_style="dim", expand=True)
        exec_table.add_column("Agent", ratio=2)
        exec_table.add_column("Status", width=14)
        exec_table.add_column("Time", justify="right", width=8)
        exec_table.add_column("Cost", justify="right", width=8)
        exec_table.add_column("Tools", justify="right", width=6)

        if execs:
            for ex in execs:
                icon, style = STATUS_STYLE.get(ex.status, ("❓", ""))
                duration = f"{ex.duration_seconds:.1f}s" if ex.duration_seconds else "..."
                exec_table.add_row(
                    ex.agent_name[:20],
                    Text(f"{icon} {ex.status}", style=style),
                    duration,
                    f"${ex.cost_usd:.4f}",
                    str(ex.tokens_input + ex.tokens_output) if ex.tokens_input else "—",
                )
        else:
            exec_table.add_row("[dim]—[/]", "[dim]waiting[/]", "—", "—", "—")

        layout["executions"].update(Panel(exec_table, title="Executions", border_style="yellow"))

    return layout
