"""cawnex init — first-run setup wizard."""

from __future__ import annotations

import asyncio
import subprocess
import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from cryptography.fernet import Fernet

from cawnex_cli import config as cfg

console = Console()

BANNER = """[bold white]
   ██████╗ █████╗ ██╗    ██╗███╗   ██╗███████╗██╗  ██╗
  ██╔════╝██╔══██╗██║    ██║████╗  ██║██╔════╝╚██╗██╔╝
  ██║     ███████║██║ █╗ ██║██╔██╗ ██║█████╗   ╚███╔╝
  ██║     ██╔══██║██║███╗██║██║╚██╗██║██╔══╝   ██╔██╗
  ╚██████╗██║  ██║╚███╔███╔╝██║ ╚████║███████╗██╔╝ ██╗
   ╚═════╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝
[/][dim]  Coordinated Intelligence • First-run setup[/]
"""


@click.command()
def init():
    """🥚 First-run setup — configure infrastructure, LLM keys, and repos."""
    console.print(BANNER)

    if cfg.is_setup_complete():
        if not Confirm.ask("[yellow]Cawnex is already configured. Re-run setup?[/]", default=False):
            return

    console.print()
    console.print(Panel("[bold]Let's hatch your murder.[/]\n\n"
        "This wizard will:\n"
        "  1. Start infrastructure (PostgreSQL + Redis)\n"
        "  2. Generate encryption keys\n"
        "  3. Connect your Anthropic API key\n"
        "  4. Connect your GitHub account\n"
        "  5. Initialize the database\n"
        "  6. Link your first repository",
        title="🐦‍⬛ Setup", border_style="white"))

    # Step 1: Infrastructure
    console.print("\n[bold cyan]Step 1/6 — Infrastructure[/]")
    _step_infrastructure()

    # Step 2: Encryption key
    console.print("\n[bold cyan]Step 2/6 — Encryption[/]")
    _step_encryption()

    # Step 3: LLM Provider
    console.print("\n[bold cyan]Step 3/6 — LLM Provider (BYOL)[/]")
    _step_llm_provider()

    # Step 4: GitHub
    console.print("\n[bold cyan]Step 4/6 — GitHub[/]")
    _step_github()

    # Step 5: Database
    console.print("\n[bold cyan]Step 5/6 — Database[/]")
    _step_database()

    # Step 6: Repository
    console.print("\n[bold cyan]Step 6/6 — Repository[/]")
    _step_repository()

    # Done
    console.print()
    console.print(Panel(
        "[bold green]✅ Cawnex is ready![/]\n\n"
        "Next steps:\n"
        "  [bold]cawnex status[/]     — Check system health\n"
        "  [bold]cawnex agents[/]     — List your crows\n"
        "  [bold]cawnex run[/]        — Start the worker\n"
        "  [bold]cawnex issue <n>[/]  — Run an issue through the pipeline\n\n"
        "[dim]Config saved to ~/.cawnex/config.json[/]",
        title="🐦‍⬛ Setup Complete", border_style="green",
    ))


def _step_infrastructure():
    """Check/start Docker containers."""
    # Check Docker
    result = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if result.returncode != 0:
        console.print("[red]  ✗ Docker not running. Please start Docker and retry.[/]")
        raise click.Abort()
    console.print("  ✓ Docker is running")

    # Check if containers exist
    result = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        capture_output=True, text=True, cwd=_find_project_root(),
    )

    db_url = "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex"
    redis_url = "redis://localhost:6380"

    if "cawnex-db" not in result.stdout and "db" not in result.stdout:
        if Confirm.ask("  Start PostgreSQL + Redis containers?", default=True):
            subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=_find_project_root(),
            )
            console.print("  ✓ Containers started")
        else:
            db_url = Prompt.ask("  PostgreSQL URL", default=db_url)
            redis_url = Prompt.ask("  Redis URL", default=redis_url)
    else:
        console.print("  ✓ Containers already running")

    cfg.set_key("database_url", db_url)
    cfg.set_key("redis_url", redis_url)


def _step_encryption():
    """Generate or load Fernet key."""
    existing = cfg.get("fernet_key")
    if existing:
        console.print(f"  ✓ Encryption key exists ({existing[:8]}...)")
        if not Confirm.ask("  Generate a new key?", default=False):
            return

    key = Fernet.generate_key().decode()
    cfg.set_key("fernet_key", key)
    console.print(f"  ✓ Generated encryption key: [dim]{key[:12]}...[/]")
    console.print("  [dim]Your BYOL API keys are encrypted with this key.[/]")


def _step_llm_provider():
    """Choose between API key and subscription mode."""
    existing_mode = cfg.get("llm_mode")
    if existing_mode:
        console.print(f"  Current mode: [cyan]{existing_mode}[/]")
        if not Confirm.ask("  Reconfigure?", default=False):
            return

    console.print()
    console.print("  How do you want to run agents?")
    console.print()
    console.print("  [bold cyan][1][/] API Key — paste your sk-ant-... key (pay per token)")
    console.print("  [bold green][2][/] Claude Max Subscription — agents run via Claude Code CLI (unlimited)")
    console.print()

    choice = Prompt.ask("  Choice", choices=["1", "2"], default="2")

    if choice == "2":
        _step_subscription()
    else:
        _step_api_key()


def _step_subscription():
    """Configure Claude Max subscription mode."""
    console.print()
    console.print("  [bold green]Subscription mode[/] — agents run via Claude Code CLI")
    console.print("  [dim]No API key needed. Your Max subscription covers all usage.[/]")

    # Check if Claude Code is available
    console.print("  Checking Claude Code CLI...", end="")
    result = subprocess.run(
        ["npx", "@anthropic-ai/claude-code", "--version"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        version = result.stdout.strip()
        console.print(f" [green]✓ {version}[/]")
    else:
        console.print(" [red]✗ Not found[/]")
        console.print("  [dim]Install with: npm install -g @anthropic-ai/claude-code[/]")

    # Check if logged in
    console.print("  Checking login status...", end="")
    result = subprocess.run(
        ["npx", "@anthropic-ai/claude-code", "--print", "--output-format", "json",
         "--no-session-persistence", "--allowedTools", "", "-p", "hi"],
        capture_output=True, text=True, timeout=30,
    )
    import json as _json
    try:
        out = _json.loads(result.stdout.strip().split("\n")[-1])
        if "Not logged in" in out.get("result", ""):
            console.print(" [yellow]⚠ Not logged in[/]")
            console.print()
            console.print("  [bold]Run this to log in:[/]")
            console.print("  [cyan]npx @anthropic-ai/claude-code /login[/]")
            console.print()
            if not Confirm.ask("  Continue anyway?", default=True):
                raise click.Abort()
        else:
            console.print(" [green]✓ Logged in[/]")
    except Exception:
        console.print(" [yellow]⚠ Could not verify[/]")

    cfg.set_key("llm_mode", "subscription")
    cfg.set_key("use_subscription", True)
    console.print("  [green]✓ Subscription mode configured[/]")


def _step_api_key():
    """Validate and store Anthropic API key."""
    existing = cfg.get("anthropic_api_key")
    if existing:
        masked = existing[:12] + "..." + existing[-4:]
        console.print(f"  Existing key: [dim]{masked}[/]")
        if not Confirm.ask("  Replace it?", default=False):
            cfg.set_key("llm_mode", "api_key")
            cfg.set_key("use_subscription", False)
            return

    api_key = Prompt.ask("  Anthropic API key", password=True)
    if not api_key.startswith("sk-ant-"):
        console.print("[yellow]  ⚠ Key doesn't start with sk-ant-. Proceeding anyway.[/]")

    # Validate
    console.print("  Validating key...", end="")
    valid = asyncio.run(_validate_anthropic_key(api_key))
    if valid:
        console.print(" [green]✓ Valid[/]")
        cfg.set_key("anthropic_api_key", api_key)
        cfg.set_key("llm_mode", "api_key")
        cfg.set_key("use_subscription", False)

        # Also encrypt it for DB storage
        fernet = Fernet(cfg.get("fernet_key").encode())
        encrypted = fernet.encrypt(api_key.encode()).decode()
        cfg.set_key("anthropic_api_key_encrypted", encrypted)
    else:
        console.print(" [red]✗ Invalid[/]")
        if not Confirm.ask("  Save anyway?", default=False):
            raise click.Abort()
        cfg.set_key("anthropic_api_key", api_key)
        cfg.set_key("llm_mode", "api_key")
        cfg.set_key("use_subscription", False)


async def _validate_anthropic_key(api_key: str) -> bool:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)
    try:
        await client.messages.create(
            model="claude-haiku-4-6", max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        return True
    except anthropic.AuthenticationError:
        return False
    except Exception:
        return True  # Network errors ≠ invalid key


def _step_github():
    """Configure GitHub PAT."""
    existing = cfg.get("github_token")
    if existing:
        masked = existing[:8] + "..." + existing[-4:]
        console.print(f"  Existing token: [dim]{masked}[/]")
        if not Confirm.ask("  Replace it?", default=False):
            return

    token = Prompt.ask("  GitHub Personal Access Token (repo scope)", password=True)

    # Quick validation
    console.print("  Validating token...", end="")
    valid = asyncio.run(_validate_github_token(token))
    if valid:
        console.print(" [green]✓ Valid[/]")
    else:
        console.print(" [yellow]⚠ Could not validate (may still work)[/]")

    cfg.set_key("github_token", token)


async def _validate_github_token(token: str) -> bool:
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {token}"},
            )
            return r.status_code == 200
        except Exception:
            return False


def _step_database():
    """Initialize database tables and seed data."""
    import sys
    sys.path.insert(0, str(_find_project_root() / "scripts"))

    console.print("  Creating tables...")
    try:
        asyncio.run(_init_db())
        console.print("  ✓ Tables created")
    except Exception as e:
        console.print(f"  [red]✗ {e}[/]")
        raise click.Abort()

    if Confirm.ask("  Seed with dogfood tenant + agents?", default=True):
        try:
            asyncio.run(_seed_db())
            console.print("  ✓ Seeded")
        except Exception as e:
            console.print(f"  [yellow]⚠ {e}[/]")


async def _init_db():
    from cawnex_core.models.db import create_engine, init_db
    from cawnex_core.models import (  # noqa: F401
        Tenant, LLMConfig, Repository, Task, AgentDefinition,
        Workflow, WorkflowStep, Execution, ExecutionEvent, Artifact,
    )
    engine = create_engine(cfg.get("database_url"))
    await init_db(engine)
    await engine.dispose()


async def _seed_db():
    from cryptography.fernet import Fernet
    from sqlalchemy import select
    from cawnex_core.enums import Provider, BYOLMode, TaskSource, TaskStatus
    from cawnex_core.models import (
        Tenant, LLMConfig, Repository, Task,
        AgentDefinition, Workflow, WorkflowStep,
    )
    from cawnex_core.models.db import create_engine, create_session_factory

    engine = create_engine(cfg.get("database_url"))
    sf = create_session_factory(engine)

    async with sf() as session:
        existing = await session.execute(select(Tenant).where(Tenant.slug == "cawnex-dogfood"))
        if existing.scalar_one_or_none():
            console.print("  [dim]Already seeded[/]")
            await engine.dispose()
            return

        tenant = Tenant(name="Cawnex Dogfood", slug="cawnex-dogfood")
        session.add(tenant)
        await session.flush()

        # LLM config with real key if available
        fernet_key = cfg.get("fernet_key", "").encode()
        api_key = cfg.get("anthropic_api_key", "placeholder")
        fernet = Fernet(fernet_key) if fernet_key else Fernet(Fernet.generate_key())
        encrypted = fernet.encrypt(api_key.encode())

        llm = LLMConfig(
            tenant_id=tenant.id, provider=Provider.ANTHROPIC,
            mode=BYOLMode.API_KEY, encrypted_api_key=encrypted,
        )
        session.add(llm)

        # Agents
        agents = {
            "refinement": AgentDefinition(
                tenant_id=tenant.id, name="Refinement Agent", slug="refinement",
                description="Analyzes tasks → structured briefs with acceptance criteria.",
                system_prompt="You are a senior requirements analyst. Given a task, produce a clear brief with acceptance criteria, affected files, and implementation notes.",
                model="claude-sonnet-4-6", tool_packs=["filesystem", "shell"],
                max_tokens=8000, max_time_seconds=300, workspace_type="temp_dir",
            ),
            "developer": AgentDefinition(
                tenant_id=tenant.id, name="Code Developer", slug="developer",
                description="Implements code changes, creates branches and commits.",
                system_prompt="You are a senior software developer. Implement the requested changes following the project's conventions. Write clean, tested code. Commit with clear messages.",
                model="claude-sonnet-4-6", tool_packs=["filesystem", "shell", "git"],
                max_tokens=16000, max_time_seconds=900, workspace_type="git_worktree",
            ),
            "reviewer": AgentDefinition(
                tenant_id=tenant.id, name="QA Reviewer", slug="reviewer",
                description="Reviews code against acceptance criteria.",
                system_prompt="You are a QA engineer. Review the code changes against the acceptance criteria. Check for bugs, edge cases, and code quality. Approve or reject with specific feedback.",
                model="claude-sonnet-4-6", tool_packs=["filesystem", "shell", "git"],
                max_tokens=8000, max_time_seconds=300, workspace_type="temp_dir",
            ),
            "documenter": AgentDefinition(
                tenant_id=tenant.id, name="Documentation Agent", slug="documenter",
                description="Updates documentation after code changes.",
                system_prompt="You are a technical writer. Update documentation to reflect the changes made. Keep docs concise and accurate.",
                model="claude-haiku-4-6", tool_packs=["filesystem", "git"],
                max_tokens=4000, max_time_seconds=180, workspace_type="temp_dir",
            ),
        }
        for a in agents.values():
            session.add(a)
        await session.flush()

        # Workflow
        wf = Workflow(
            tenant_id=tenant.id, name="Code Shipping", slug="code-shipping",
            description="Issue → Refine → Implement → Review → Document",
            trigger_config={"source": "github", "event": "issue_labeled", "filters": {"label": "cawnex"}},
        )
        session.add(wf)
        await session.flush()

        steps = [
            WorkflowStep(workflow_id=wf.id, agent_id=agents["refinement"].id, order=1, name="Refine",
                         input_from="task", requires_approval=True, on_fail="fail"),
            WorkflowStep(workflow_id=wf.id, agent_id=agents["developer"].id, order=2, name="Implement",
                         input_from="previous_step", on_fail="retry"),
            WorkflowStep(workflow_id=wf.id, agent_id=agents["reviewer"].id, order=3, name="Review",
                         input_from="previous_step", on_reject="goto:Implement", on_fail="fail"),
            WorkflowStep(workflow_id=wf.id, agent_id=agents["documenter"].id, order=4, name="Document",
                         input_from="previous_step", on_fail="skip"),
        ]
        for s in steps:
            session.add(s)

        await session.commit()

    await engine.dispose()


def _step_repository():
    """Connect first repository."""
    repo = Prompt.ask("  GitHub repository (owner/repo)", default="eduardoaugustoes/cawnex")
    cfg.set_key("default_repo", repo)
    console.print(f"  ✓ Default repo: {repo}")

    # Try to connect via API
    token = cfg.get("github_token")
    if token:
        console.print("  Fetching repo metadata...", end="")
        info = asyncio.run(_fetch_repo(repo, token))
        if info:
            console.print(f" [green]✓[/] ({info.get('language', '?')})")
            asyncio.run(_save_repo_to_db(repo, info))
        else:
            console.print(" [yellow]⚠ Could not fetch (will try later)[/]")


async def _fetch_repo(repo: str, token: str) -> dict | None:
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"https://api.github.com/repos/{repo}",
                headers={"Authorization": f"Bearer {token}"},
            )
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None


async def _save_repo_to_db(repo: str, info: dict):
    from sqlalchemy import select
    from cawnex_core.models import Tenant, Repository
    from cawnex_core.models.db import create_engine, create_session_factory

    engine = create_engine(cfg.get("database_url"))
    sf = create_session_factory(engine)
    async with sf() as session:
        tenant = (await session.execute(
            select(Tenant).where(Tenant.slug == "cawnex-dogfood")
        )).scalar_one_or_none()
        if not tenant:
            await engine.dispose()
            return

        existing = (await session.execute(
            select(Repository).where(
                Repository.github_full_name == repo,
                Repository.tenant_id == tenant.id,
            )
        )).scalar_one_or_none()

        if not existing:
            r = Repository(
                tenant_id=tenant.id,
                github_full_name=repo,
                default_branch=info.get("default_branch", "main"),
                clone_url=info.get("clone_url", f"https://github.com/{repo}.git"),
                language=info.get("language"),
            )
            session.add(r)
            await session.commit()

    await engine.dispose()


def _find_project_root() -> "Path":
    from pathlib import Path
    # Walk up from CLI package to find docker-compose.yml
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "docker-compose.yml").exists():
            return parent
    # Fallback
    return Path.cwd()
