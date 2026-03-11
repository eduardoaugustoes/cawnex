"""cawnex watch — interactive real-time dashboard. GitHub issues are the source of truth."""

import asyncio
import json
import os
import queue
import subprocess
import sys
import threading
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

HELP_TEXT = "[dim]↑/↓ select  │  Enter expand  │  r run  │  c create  │  R refresh  │  q quit[/]"


class WatchState:
    def __init__(self):
        self.selected_idx = 0
        self.expanded_issue: int | None = None
        self.issues: list[dict] = []  # From GitHub
        self.task_map: dict[str, dict] = {}  # issue_ref → task data
        self.executions: list = []
        self.events: list = []
        self.message: str = ""
        self.last_gh_fetch: float = 0
        self.action: str | None = None  # "create", "quit" — breaks out of Live


class KeyReader:
    """Background thread that reads keys and puts them in a queue."""

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._stop = False
        self._thread: threading.Thread | None = None
        self._old_settings = None
        self._pipe_r = -1
        self._pipe_w = -1

    def start(self):
        if not sys.stdin.isatty():
            return
        import termios, tty
        self._stop = False
        self._old_settings = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        # Create a pipe to wake up the blocking select
        self._pipe_r, self._pipe_w = os.pipe()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        # Wake the reader thread by writing to the pipe
        if self._pipe_w >= 0:
            try:
                os.write(self._pipe_w, b"\x00")
                os.close(self._pipe_w)
                self._pipe_w = -1
            except OSError:
                pass
        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None
        # Close read end
        if self._pipe_r >= 0:
            try:
                os.close(self._pipe_r)
                self._pipe_r = -1
            except OSError:
                pass
        # Restore terminal
        if self._old_settings:
            import termios
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_settings)
            except Exception:
                pass
            self._old_settings = None
        # Drain the queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def get_key(self) -> str | None:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def _reader(self):
        import select as sel
        stdin_fd = sys.stdin.fileno()
        while not self._stop:
            try:
                # Wait for stdin OR the wake pipe
                readable, _, _ = sel.select([stdin_fd, self._pipe_r], [], [], 0.2)
                if not readable:
                    continue
                if self._pipe_r in readable:
                    break  # Stop signal
                if stdin_fd not in readable:
                    continue

                ch = sys.stdin.read(1)
                if not ch:
                    break
                if ch == "\x1b":
                    # Check for arrow sequence
                    r2, _, _ = sel.select([stdin_fd], [], [], 0.05)
                    if r2:
                        ch2 = sys.stdin.read(1)
                        if ch2 == "[":
                            r3, _, _ = sel.select([stdin_fd], [], [], 0.05)
                            if r3:
                                ch3 = sys.stdin.read(1)
                                if ch3 == "A":
                                    self._queue.put("up")
                                elif ch3 == "B":
                                    self._queue.put("down")
                            continue
                    continue
                self._queue.put(ch)
            except Exception:
                break


def _fetch_gh_issues(repo: str, label: str | None = None) -> list[dict]:
    """Fetch issues from GitHub via gh CLI."""
    cmd = [
        "gh", "issue", "list", "--repo", repo, "--state", "all",
        "--limit", "30", "--json",
        "number,title,body,labels,state,createdAt,author,url"
    ]
    if label:
        cmd.extend(["--label", label])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


@click.command()
@click.option("--label", "-l", default=None, help="Filter issues by label.")
def watch(label: str | None):
    """👁️  Live dashboard — GitHub issues + agent executions in real-time.

    \b
    Controls:
      ↑/↓ or j/k  Select issue
      Enter        Expand/collapse issue details + executions
      r            Run selected issue through the pipeline
      R            Refresh issues from GitHub
      q            Quit
    """
    keys = KeyReader()
    keys.start()
    try:
        asyncio.run(_watch_loop(label, keys))
    except KeyboardInterrupt:
        pass
    finally:
        keys.stop()
        console.print("\n[dim]Stopped watching.[/]")


async def _watch_loop(label: str | None, keys: KeyReader):
    import time
    config = cfg.load_config()
    repo = config.get("default_repo", "")
    db_url = config.get("database_url", "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex")
    redis_url = config.get("redis_url", "redis://localhost:6380")

    if not repo:
        console.print("[red]No repo configured. Run: cawnex setup repo <owner/repo>[/]")
        return

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from cawnex_core.models import Task, Execution, ExecutionEvent, Tenant

    engine = create_async_engine(db_url)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = Redis.from_url(redis_url, decode_responses=True)

    state = WatchState()

    # Initial fetch
    state.message = "Fetching issues from GitHub..."
    state.issues = _fetch_gh_issues(repo, label)
    state.last_gh_fetch = time.monotonic()
    state.message = f"Loaded {len(state.issues)} issues from {repo}"

    running = True
    while running:
        state.action = None

        with Live(console=console, refresh_per_second=4, screen=True) as live:
            while True:
                # Handle keyboard
                key = keys.get_key()
                if key:
                    if key == "q":
                        state.action = "quit"
                        break
                    if key == "c":
                        state.action = "create"
                        break
                    await _handle_key(key, state, sf, redis, config, repo, label)

                # Auto-refresh GitHub every 30s
                if time.monotonic() - state.last_gh_fetch > 30:
                    state.issues = _fetch_gh_issues(repo, label)
                    state.last_gh_fetch = time.monotonic()

                # Fetch task/execution data from DB for all issues
                async with sf() as session:
                    tenant = (await session.execute(
                        select(Tenant).where(Tenant.slug == "cawnex-dogfood")
                    )).scalar_one_or_none()

                    if tenant:
                        tasks = (await session.execute(
                            select(Task).where(Task.tenant_id == tenant.id, Task.source == "github")
                        )).scalars().all()

                        state.task_map = {}
                        for t in tasks:
                            state.task_map[t.source_ref] = {
                                "id": t.id, "status": t.status,
                                "cost": t.total_cost_usd, "tokens": t.total_tokens,
                            }

                        state.executions = []
                        state.events = []
                        if state.expanded_issue is not None:
                            ref = str(state.expanded_issue)
                            task_data = state.task_map.get(ref)
                            if task_data:
                                execs = (await session.execute(
                                    select(Execution)
                                    .where(Execution.task_id == task_data["id"])
                                    .order_by(Execution.created_at.desc())
                                )).scalars().all()
                                state.executions = execs

                                if execs:
                                    exec_ids = [e.id for e in execs]
                                    events = (await session.execute(
                                        select(ExecutionEvent)
                                        .where(ExecutionEvent.execution_id.in_(exec_ids))
                                        .order_by(ExecutionEvent.created_at.desc())
                                        .limit(20)
                                    )).scalars().all()
                                    state.events = events

                if state.selected_idx >= len(state.issues):
                    state.selected_idx = max(0, len(state.issues) - 1)

                layout = _build_layout(state, repo)
                live.update(layout)
                await asyncio.sleep(0.25)

        # Handle actions that need the terminal
        if state.action == "quit":
            running = False
        elif state.action == "create":
            keys.stop()
            await _create_issue_interactive(state, repo, label)
            keys.start()

    await redis.aclose()
    await engine.dispose()


async def _handle_key(key, state, sf, redis, config, repo, label):
    import time
    if key in ("up", "k") and state.selected_idx > 0:
        state.selected_idx -= 1
        state.message = ""
    elif key in ("down", "j") and state.selected_idx < len(state.issues) - 1:
        state.selected_idx += 1
        state.message = ""
    elif key in ("\r", "\n"):  # Enter
        if state.issues:
            issue = state.issues[state.selected_idx]
            num = issue["number"]
            if state.expanded_issue == num:
                state.expanded_issue = None
                state.message = ""
            else:
                state.expanded_issue = num
                state.message = f"Issue #{num}"
    elif key == "r":
        if state.issues:
            issue = state.issues[state.selected_idx]
            num = issue["number"]
            ref = str(num)

            # Check if already has a task
            if ref in state.task_map:
                task_data = state.task_map[ref]
                if task_data["status"] in ("in_progress", "refining"):
                    state.message = f"⚠ Issue #{num} already running"
                    return
                # Re-queue existing task
                r = Redis.from_url(config.get("redis_url", "redis://localhost:6380"), decode_responses=True)
                await r.xadd("cawnex:tasks", {"task_id": str(task_data["id"]), "tenant_id": "1"})
                await r.aclose()
                state.message = f"⚡ Re-queued issue #{num}"
            else:
                # Create new task from GitHub issue
                state.message = f"⚡ Creating task for issue #{num}..."
                task_id = await _create_task_from_issue(issue, config, sf)
                if task_id:
                    state.message = f"⚡ Issue #{num} → task #{task_id} queued!"
                    state.expanded_issue = num
                else:
                    state.message = f"✗ Failed to create task for #{num}"
    elif key == "R":
        import time as _t
        state.issues = _fetch_gh_issues(repo, label)
        state.last_gh_fetch = _t.monotonic()
        state.message = f"Refreshed — {len(state.issues)} issues"


async def _create_task_from_issue(issue: dict, config: dict, sf):
    """Create a DB task from a GitHub issue and queue it."""
    from sqlalchemy import select
    from cawnex_core.models import Tenant, Task, Workflow
    from cawnex_core.enums import TaskSource, TaskStatus

    async with sf() as session:
        tenant = (await session.execute(
            select(Tenant).where(Tenant.slug == "cawnex-dogfood")
        )).scalar_one_or_none()
        if not tenant:
            return None

        workflow = (await session.execute(
            select(Workflow).where(Workflow.tenant_id == tenant.id, Workflow.is_active.is_(True))
        )).scalar_one_or_none()

        labels = [l["name"] for l in issue.get("labels", [])]
        task = Task(
            tenant_id=tenant.id,
            workflow_id=workflow.id if workflow else None,
            source=TaskSource.GITHUB,
            source_ref=str(issue["number"]),
            source_url=issue.get("url", ""),
            title=issue["title"],
            description=issue.get("body"),
            labels=json.dumps(labels),
            status=TaskStatus.PENDING,
            context={
                "repository": config.get("default_repo", ""),
                "branch": "main",
                "issue_number": issue["number"],
            },
        )
        session.add(task)
        await session.commit()
        task_id = task.id

    # Queue
    redis = Redis.from_url(config.get("redis_url", "redis://localhost:6380"), decode_responses=True)
    await redis.xadd("cawnex:tasks", {"task_id": str(task_id), "tenant_id": str(tenant.id)})
    await redis.aclose()
    return task_id


async def _create_issue_interactive(state, repo, label):
    """Temporarily exit Live mode to prompt for issue creation."""
    import time as _t
    from rich.prompt import Prompt

    console.print()
    console.print(Panel("[bold]Create a new GitHub issue[/]", border_style="cyan"))
    console.print()

    title = Prompt.ask("  [cyan]Title[/]")
    if not title.strip():
        console.print("  [dim]Cancelled[/]")
        return

    console.print("  [dim]Body (press Enter twice to finish, or leave empty):[/]")
    body_lines = []
    while True:
        line = input("  ")
        if line == "" and (not body_lines or body_lines[-1] == ""):
            break
        body_lines.append(line)
    body = "\n".join(body_lines).strip()

    # Labels
    add_cawnex_label = Prompt.ask("  Add 'cawnex' label?", choices=["y", "n"], default="y")

    console.print(f"\n  Creating issue on {repo}...", end="")

    cmd = ["gh", "issue", "create", "--repo", repo, "--title", title]
    if body:
        cmd.extend(["--body", body])
    if add_cawnex_label == "y":
        cmd.extend(["--label", "cawnex"])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

    if result.returncode == 0:
        url = result.stdout.strip()
        console.print(f" [green]✓[/]")
        console.print(f"  [dim]{url}[/]")
        state.message = f"✓ Created: {title[:40]}"
    else:
        console.print(f" [red]✗ {result.stderr.strip()[:60]}[/]")
        state.message = "✗ Failed to create issue"

    # Refresh issues
    state.issues = _fetch_gh_issues(repo, label)
    state.last_gh_fetch = _t.monotonic()

    console.print("\n  [dim]Returning to dashboard...[/]")
    await asyncio.sleep(1)


def _build_layout(state, repo):
    layout = Layout()

    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    active = sum(1 for ref, t in state.task_map.items() if t["status"] in ("in_progress", "refining"))
    total_cost = sum(t["cost"] for t in state.task_map.values())

    header = Text()
    header.append("🐦‍⬛ The Murder", style="bold white")
    header.append(f"  │  {now}  │  ", style="dim")
    header.append(repo, style="cyan")
    header.append(f"  │  {len(state.issues)} issues", style="")
    header.append(f"  │  {active} active", style="green" if active else "dim")
    header.append(f"  │  ${total_cost:.4f}", style="yellow")
    if state.message:
        header.append(f"  │  {state.message}", style="bold cyan")

    expanded_issue = None
    if state.expanded_issue is not None:
        expanded_issue = next((i for i in state.issues if i["number"] == state.expanded_issue), None)

    if expanded_issue:
        layout.split_column(
            Layout(Panel(header, style="white"), name="header", size=3),
            Layout(name="detail", size=8),
            Layout(name="body"),
            Layout(name="events", size=min(len(state.events) + 4, 14)),
            Layout(Panel(Text(HELP_TEXT), style="dim"), name="help", size=3),
        )
        layout["body"].split_row(
            Layout(name="issues", ratio=1),
            Layout(name="executions", ratio=1),
        )

        # Detail panel
        body = (expanded_issue.get("body") or "")[:400]
        labels = ", ".join(l["name"] for l in expanded_issue.get("labels", []))
        gh_state = expanded_issue.get("state", "")
        ref = str(expanded_issue["number"])
        task_data = state.task_map.get(ref)

        detail = Text()
        detail.append(f"#{expanded_issue['number']} ", style="cyan bold")
        detail.append(expanded_issue["title"], style="bold")
        detail.append(f"\n\n{body}", style="dim")
        if labels:
            detail.append(f"\n\nLabels: {labels}", style="yellow")
        detail.append(f"\nGitHub: {gh_state}", style="green" if gh_state == "open" else "red")
        if task_data:
            icon, style = STATUS_STYLE.get(task_data["status"], ("❓", ""))
            detail.append(f"  │  Cawnex: {icon} {task_data['status']}", style=style)
            detail.append(f"  │  ${task_data['cost']:.4f}  │  {task_data['tokens']:,} tokens", style="dim")
        else:
            detail.append("  │  [dim]Not yet processed — press 'r' to run[/]")

        layout["detail"].update(Panel(detail, title="Issue Detail", border_style="cyan"))

        # Executions
        exec_table = Table(show_header=True, border_style="dim", expand=True)
        exec_table.add_column("Agent", ratio=2)
        exec_table.add_column("Status", width=14)
        exec_table.add_column("Time", justify="right", width=8)
        exec_table.add_column("Cost", justify="right", width=8)

        if state.executions:
            for ex in state.executions:
                icon, style = STATUS_STYLE.get(ex.status, ("❓", ""))
                duration = f"{ex.duration_seconds:.1f}s" if ex.duration_seconds else "..."
                exec_table.add_row(
                    ex.agent_name[:20],
                    Text(f"{icon} {ex.status}", style=style),
                    duration, f"${ex.cost_usd:.4f}",
                )
        else:
            exec_table.add_row("[dim]—[/]", "[dim]waiting[/]", "—", "—")

        layout["executions"].update(Panel(exec_table, title="Executions", border_style="yellow"))

        # Events
        if state.events:
            lines = []
            for ev in reversed(state.events[:12]):
                ts = ev.created_at.strftime("%H:%M:%S") if ev.created_at else ""
                lines.append(f"[dim]{ts}[/] [{ev.event_type}] {ev.content[:100]}")
            layout["events"].update(Panel("\n".join(lines), title="Events", border_style="green"))
        else:
            layout["events"].update(Panel("[dim]No events yet — press 'r' to run[/]", title="Events", border_style="green"))
    else:
        layout.split_column(
            Layout(Panel(header, style="white"), name="header", size=3),
            Layout(name="issues"),
            Layout(Panel(Text(HELP_TEXT), style="dim"), name="help", size=3),
        )

    # Issues table
    issue_table = Table(show_header=True, border_style="dim", expand=True)
    issue_table.add_column("", width=2)
    issue_table.add_column("#", width=5)
    issue_table.add_column("Title", ratio=3)
    issue_table.add_column("GitHub", width=8)
    issue_table.add_column("Cawnex", width=16)
    issue_table.add_column("Labels", ratio=1)

    for i, iss in enumerate(state.issues):
        ref = str(iss["number"])
        task_data = state.task_map.get(ref)
        selected = "▶" if i == state.selected_idx else " "
        expanded = "▼" if iss["number"] == state.expanded_issue else ""
        sel_style = "bold cyan" if i == state.selected_idx else ""

        gh_state = iss.get("state", "")
        gh_color = "green" if gh_state == "open" else "red"

        if task_data:
            icon, cawnex_style = STATUS_STYLE.get(task_data["status"], ("❓", ""))
            cawnex_text = Text(f"{icon} {task_data['status']}", style=cawnex_style)
        else:
            cawnex_text = Text("—", style="dim")

        labels = ", ".join(l["name"] for l in iss.get("labels", []))

        issue_table.add_row(
            Text(f"{selected}{expanded}", style=sel_style),
            Text(str(iss["number"]), style=sel_style),
            Text(iss["title"][:50], style=sel_style),
            Text(gh_state, style=gh_color),
            cawnex_text,
            Text(labels[:20], style="dim"),
        )

    layout["issues"].update(Panel(issue_table, title=f"Issues — {repo}", border_style="cyan"))

    return layout
