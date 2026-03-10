"""cawnex project — manage projects, vision board, repos."""

from __future__ import annotations

import asyncio
import re
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

from cawnex_cli import config as cfg

console = Console()


def _get_db_url() -> str:
    return cfg.get("database_url", "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex")


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"


# === DB helpers ===

async def _get_session():
    from cawnex_core.models.db import create_engine, create_session_factory
    engine = create_engine(_get_db_url())
    sf = create_session_factory(engine)
    return engine, sf


async def _get_tenant(session):
    from sqlalchemy import select
    from cawnex_core.models import Tenant
    result = await session.execute(select(Tenant).where(Tenant.slug == "cawnex-dogfood"))
    return result.scalar_one_or_none()


async def _get_llm_provider():
    """Get the LLM provider based on tenant config."""
    from sqlalchemy import select
    from cawnex_core.models import LLMConfig
    from cawnex_providers.registry import ProviderRegistry

    engine, sf = await _get_session()
    async with sf() as session:
        config = (await session.execute(select(LLMConfig))).scalar_one_or_none()
        if not config:
            raise click.ClickException("No LLM config found. Run: cawnex init")

        fernet_key = cfg.get("fernet_key", "")
        provider = ProviderRegistry.get_for_tenant(
            mode=config.mode,
            provider=config.provider,
            encrypted_key=config.encrypted_api_key if config.mode == "api_key" else None,
            fernet_key=fernet_key.encode() if fernet_key else None,
        )
    await engine.dispose()
    return provider


# === Commands ===

@click.group()
def project():
    """📁 Manage projects — create, list, vision board, repos."""
    pass


@project.command("list")
def project_list():
    """List all projects."""
    asyncio.run(_project_list())


async def _project_list():
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from cawnex_core.models.project import Project, ProjectRepository

    engine, sf = await _get_session()
    async with sf() as session:
        tenant = await _get_tenant(session)
        if not tenant:
            console.print("[red]No tenant found. Run: cawnex init[/]")
            await engine.dispose()
            return

        projects = (await session.execute(
            select(Project)
            .where(Project.tenant_id == tenant.id)
            .options(
                selectinload(Project.vision),
                selectinload(Project.milestones),
                selectinload(Project.project_repositories).selectinload(ProjectRepository.repository),
            )
            .order_by(Project.created_at.desc())
        )).scalars().unique().all()

    await engine.dispose()

    if not projects:
        console.print("[dim]No projects yet. Create one: cawnex project create \"My App\"[/]")
        return

    table = Table(title="📁 Projects", show_header=True, border_style="dim")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Slug", style="cyan")
    table.add_column("Status")
    table.add_column("Repos", justify="right")
    table.add_column("Milestones", justify="right")
    table.add_column("Vision")

    status_colors = {"draft": "yellow", "active": "green", "paused": "dim", "archived": "dim"}

    for p in projects:
        repos = len(p.project_repositories) if p.project_repositories else 0
        milestones = len(p.milestones) if p.milestones else 0
        has_vision = "✓" if (p.vision and p.vision.content) else "—"
        color = status_colors.get(p.status, "white")
        table.add_row(
            str(p.id), p.name, p.slug,
            f"[{color}]{p.status}[/]",
            str(repos), str(milestones), has_vision,
        )

    console.print(table)


@project.command("create")
@click.argument("name")
def project_create(name: str):
    """Create a new project."""
    asyncio.run(_project_create(name))


async def _project_create(name: str):
    from sqlalchemy import select
    from cawnex_core.models.project import Project, Vision

    engine, sf = await _get_session()
    async with sf() as session:
        tenant = await _get_tenant(session)
        if not tenant:
            console.print("[red]No tenant found. Run: cawnex init[/]")
            await engine.dispose()
            return

        slug = _slugify(name)

        # Check uniqueness
        existing = (await session.execute(
            select(Project).where(Project.tenant_id == tenant.id, Project.slug == slug)
        )).scalar_one_or_none()
        if existing:
            console.print(f"[red]Project with slug '{slug}' already exists[/]")
            await engine.dispose()
            return

        project = Project(tenant_id=tenant.id, name=name, slug=slug, status="draft")
        session.add(project)
        await session.flush()

        vision = Vision(project_id=project.id, content="", version=0)
        session.add(vision)
        await session.commit()

        console.print(f"[green]✓ Created project:[/] {name} [dim](slug: {slug}, id: {project.id})[/]")

    await engine.dispose()


@project.command("vision")
@click.option("--project", "-p", "project_slug", default=None, help="Project slug (auto-picks if only one)")
@click.option("--show", is_flag=True, help="Just print the vision document")
def project_vision(project_slug: str | None, show: bool):
    """💬 Vision board — chat with AI to build your product vision."""
    asyncio.run(_project_vision(project_slug, show))


async def _project_vision(project_slug: str | None, show_only: bool):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from cawnex_core.models.project import Project, Vision, VisionMessage, Milestone

    engine, sf = await _get_session()

    async with sf() as session:
        tenant = await _get_tenant(session)
        if not tenant:
            console.print("[red]No tenant found. Run: cawnex init[/]")
            await engine.dispose()
            return

        # Find project
        query = select(Project).where(Project.tenant_id == tenant.id).options(
            selectinload(Project.vision),
            selectinload(Project.milestones),
            selectinload(Project.project_repositories),
        )

        if project_slug:
            query = query.where(Project.slug == project_slug)

        projects = (await session.execute(query)).scalars().unique().all()

        if not projects:
            if project_slug:
                console.print(f"[red]Project '{project_slug}' not found[/]")
            else:
                console.print("[dim]No projects. Create one: cawnex project create \"My App\"[/]")
            await engine.dispose()
            return

        if len(projects) == 1:
            proj = projects[0]
        else:
            # Prompt user to pick
            console.print("[bold]Select a project:[/]")
            for i, p in enumerate(projects, 1):
                console.print(f"  [{i}] {p.name} [dim]({p.slug})[/]")
            choice = Prompt.ask("Project", choices=[str(i) for i in range(1, len(projects) + 1)])
            proj = projects[int(choice) - 1]

        # Load messages
        msgs = (await session.execute(
            select(VisionMessage)
            .where(VisionMessage.project_id == proj.id)
            .order_by(VisionMessage.created_at)
        )).scalars().all()

    await engine.dispose()

    if show_only:
        _show_vision(proj)
        return

    # Interactive chat
    await _vision_chat(proj, list(msgs))


def _show_vision(proj):
    """Print the vision document."""
    if not proj.vision or not proj.vision.content:
        console.print(f"[dim]No vision document for {proj.name}. Use: cawnex project vision[/]")
        return

    console.print(Panel(
        Markdown(proj.vision.content),
        title=f"📋 {proj.name} — Vision (v{proj.vision.version})",
        border_style="cyan",
    ))


async def _vision_chat(proj, messages: list):
    """Interactive vision chat in the terminal."""
    from cawnex_core.models.project import VisionMessage, Vision

    console.print()
    console.print(Panel(
        f"[bold]{proj.name}[/] — Vision Board\n"
        f"[dim]Chat with AI to build your product vision. Type 'quit' to exit.[/]\n"
        f"[dim]Type 'apply <n>' to apply message #n to the vision. Type 'show' to view the document.[/]",
        border_style="cyan",
    ))

    # Show recent messages
    if messages:
        console.print(f"\n[dim]— Recent conversation ({len(messages)} messages) —[/]\n")
        for msg in messages[-6:]:  # Show last 6
            _print_message(msg)

    provider = await _get_llm_provider()
    ai_messages = []  # Track for apply

    while True:
        console.print()
        try:
            user_input = Prompt.ask("[bold cyan]You[/]")
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input.strip():
            continue

        cmd = user_input.strip().lower()
        if cmd in ("quit", "exit", "q"):
            break

        if cmd == "show":
            await _reload_and_show(proj.id)
            continue

        if cmd.startswith("apply"):
            parts = cmd.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(ai_messages):
                    await _apply_message(proj.id, ai_messages[idx])
                    console.print("[green]✓ Applied to vision[/]")
                else:
                    console.print(f"[red]Message #{parts[1]} not found. Valid: 1-{len(ai_messages)}[/]")
            else:
                console.print("[dim]Usage: apply <message_number>[/]")
            continue

        # Save user message + call LLM
        console.print()
        with console.status("[dim]Thinking...[/]"):
            try:
                # Save user message
                engine, sf = await _get_session()
                async with sf() as session:
                    user_msg = VisionMessage(
                        project_id=proj.id, role="user",
                        content=user_input.strip(), applied=False,
                    )
                    session.add(user_msg)
                    await session.commit()
                await engine.dispose()

                # Build prompt
                system = _build_system_prompt(proj)
                history = _build_history(messages, user_input.strip())

                response = await provider.complete(
                    system=system,
                    messages=history,
                    max_tokens=4096,
                )

                # Save assistant message
                engine, sf = await _get_session()
                async with sf() as session:
                    ai_msg = VisionMessage(
                        project_id=proj.id, role="assistant",
                        content=response.content, applied=False,
                    )
                    session.add(ai_msg)
                    await session.flush()
                    msg_id = ai_msg.id
                    await session.commit()
                await engine.dispose()

                # Track for apply
                ai_messages.append(msg_id)
                msg_num = len(ai_messages)

                # Update local history
                messages.append(type("Msg", (), {"role": "user", "content": user_input.strip()})())
                messages.append(type("Msg", (), {"role": "assistant", "content": response.content, "id": msg_id})())

                console.print(Panel(
                    Markdown(response.content),
                    title=f"🐦‍⬛ AI [dim](message #{msg_num} — type 'apply {msg_num}' to use)[/]",
                    border_style="green",
                ))

            except Exception as e:
                console.print(f"[red]Error: {e}[/]")

    console.print("\n[dim]Session ended.[/]")


def _print_message(msg):
    role = getattr(msg, "role", "user")
    content = getattr(msg, "content", "")
    if role == "user":
        console.print(f"[bold cyan]You:[/] {content[:200]}{'...' if len(content) > 200 else ''}")
    else:
        console.print(Panel(
            Markdown(content[:500] + ("..." if len(content) > 500 else "")),
            title="🐦‍⬛ AI",
            border_style="green",
        ))


def _build_system_prompt(proj) -> str:
    vision_content = proj.vision.content if proj.vision else "(empty)"
    milestones = ", ".join(m.name for m in (proj.milestones or []))
    return (
        "You are a product strategist AI helping build a project vision document.\n"
        f"\n## Current Vision\n{vision_content}\n"
        f"\n## Project: {proj.name}"
        f"\n## Milestones: {milestones or 'None'}\n"
        "\n## Guidelines\n"
        "- Write clear, actionable markdown\n"
        "- When suggesting changes, output the FULL updated vision document\n"
        "- Be opinionated — challenge weak assumptions\n"
        "- Match the user's language\n"
    )


def _build_history(messages, current_input: str) -> list[dict]:
    history = []
    for msg in messages[-20:]:
        role = getattr(msg, "role", "user")
        content = getattr(msg, "content", "")
        history.append({"role": role, "content": content})
    history.append({"role": "user", "content": current_input})
    return history


async def _apply_message(project_id: int, message_id: int):
    from sqlalchemy import select
    from cawnex_core.models.project import Vision, VisionMessage

    engine, sf = await _get_session()
    async with sf() as session:
        msg = (await session.execute(
            select(VisionMessage).where(VisionMessage.id == message_id)
        )).scalar_one_or_none()
        vision = (await session.execute(
            select(Vision).where(Vision.project_id == project_id)
        )).scalar_one_or_none()

        if msg and vision:
            vision.content = msg.content
            vision.version += 1
            msg.applied = True
            await session.commit()
    await engine.dispose()


async def _reload_and_show(project_id: int):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from cawnex_core.models.project import Project

    engine, sf = await _get_session()
    async with sf() as session:
        proj = (await session.execute(
            select(Project).where(Project.id == project_id)
            .options(selectinload(Project.vision))
        )).scalar_one_or_none()
    await engine.dispose()

    if proj:
        _show_vision(proj)
