"""cawnex issue — submit a task to the pipeline."""

import asyncio
import click
from rich.console import Console
from rich.live import Live
from rich.table import Table

from cawnex_cli import config as cfg

console = Console()


@click.command()
@click.argument("issue_ref")
@click.option("--repo", default=None, help="Repository (owner/repo). Defaults to config.")
@click.option("--dry-run", is_flag=True, help="Show what would happen without executing.")
@click.option("--watch", is_flag=True, default=True, help="Watch execution in real-time.")
def issue(issue_ref: str, repo: str | None, dry_run: bool, watch: bool):
    """📋 Submit a GitHub issue to the pipeline.

    ISSUE_REF is the issue number (e.g., 42) or URL.
    """
    config = cfg.load_config()
    repo = repo or config.get("default_repo")

    if not repo:
        console.print("[red]No repo configured. Run: cawnex setup repo <owner/repo>[/]")
        return

    # Parse issue ref
    if issue_ref.startswith("http"):
        # Extract number from URL
        issue_number = int(issue_ref.rstrip("/").split("/")[-1])
    else:
        issue_number = int(issue_ref)

    console.print(f"\n🐦‍⬛ Processing {repo}#{issue_number}")

    if dry_run:
        console.print("[yellow]  (dry run — no changes will be made)[/]")

    # Fetch issue from GitHub
    token = config.get("github_token")
    if not token:
        console.print("[red]No GitHub token. Run: cawnex setup github[/]")
        return

    issue_data = asyncio.run(_fetch_issue(repo, issue_number, token))
    if not issue_data:
        console.print(f"[red]Issue #{issue_number} not found in {repo}[/]")
        return

    console.print(f"  📋 {issue_data['title']}")
    console.print(f"  [dim]{issue_data.get('body', '')[:200]}[/]")

    if dry_run:
        console.print("\n[yellow]  Workflow: Refine → Implement → Review → Document[/]")
        console.print("  [dim]Run without --dry-run to execute[/]")
        return

    # Create task and push to Redis
    task_id = asyncio.run(_create_and_queue_task(repo, issue_data, config))
    if task_id:
        console.print(f"\n  ⚡ Task created (id={task_id})")
        console.print("  [dim]The Murder will pick it up. Run 'cawnex roost' to monitor.[/]")
    else:
        console.print("[red]  Failed to create task[/]")


async def _fetch_issue(repo: str, number: int, token: str) -> dict | None:
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://api.github.com/repos/{repo}/issues/{number}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return r.json() if r.status_code == 200 else None


async def _create_and_queue_task(repo: str, issue_data: dict, config: dict) -> int | None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from redis.asyncio import Redis
    from cawnex_core.models import Tenant, Task, Workflow
    from cawnex_core.enums import TaskSource, TaskStatus

    url = config.get("database_url", "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex")
    engine = create_async_engine(url)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with sf() as session:
            tenant = (await session.execute(
                select(Tenant).where(Tenant.slug == "cawnex-dogfood")
            )).scalar_one_or_none()
            if not tenant:
                return None

            workflow = (await session.execute(
                select(Workflow).where(
                    Workflow.tenant_id == tenant.id, Workflow.is_active.is_(True)
                )
            )).scalar_one_or_none()

            task = Task(
                tenant_id=tenant.id,
                workflow_id=workflow.id if workflow else None,
                source=TaskSource.GITHUB,
                source_ref=str(issue_data["number"]),
                source_url=issue_data["html_url"],
                title=issue_data["title"],
                description=issue_data.get("body"),
                status=TaskStatus.PENDING,
                context={"repository": repo, "branch": "main", "issue_number": issue_data["number"]},
            )
            session.add(task)
            await session.commit()
            task_id = task.id

        # Push to Redis Stream
        redis = Redis.from_url(config.get("redis_url", "redis://localhost:6380"), decode_responses=True)
        await redis.xadd("cawnex:tasks", {"task_id": str(task_id), "tenant_id": str(tenant.id)})
        await redis.aclose()

        return task_id
    finally:
        await engine.dispose()
