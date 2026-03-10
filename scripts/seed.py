"""Seed database with dogfood tenant, code-shipping workflow, and agent templates."""

import asyncio

from cryptography.fernet import Fernet
from sqlalchemy import select

from cawnex_core.enums import Provider, BYOLMode, TaskSource, TaskStatus
from cawnex_core.models import (
    Tenant, LLMConfig, Repository, Task,
    AgentDefinition, Workflow, WorkflowStep,
)
from cawnex_core.models.db import create_engine, create_session_factory

DATABASE_URL = "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex"
ENCRYPTION_KEY = Fernet.generate_key()


async def main():
    engine = create_engine(DATABASE_URL)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        # Check if already seeded
        result = await session.execute(select(Tenant).where(Tenant.slug == "cawnex-dogfood"))
        if result.scalar_one_or_none():
            print("⚠️  Already seeded. Skipping.")
            await engine.dispose()
            return

        # === TENANT ===
        tenant = Tenant(name="Cawnex Dogfood", slug="cawnex-dogfood")
        session.add(tenant)
        await session.flush()

        # === LLM CONFIG (placeholder) ===
        fernet = Fernet(ENCRYPTION_KEY)
        llm_config = LLMConfig(
            tenant_id=tenant.id,
            provider=Provider.ANTHROPIC,
            mode=BYOLMode.API_KEY,
            encrypted_api_key=fernet.encrypt(b"placeholder-key"),
        )
        session.add(llm_config)

        # === REPOSITORY (for code workflow context) ===
        repo = Repository(
            tenant_id=tenant.id,
            github_full_name="eduardoaugustoes/cawnex",
            default_branch="main",
            clone_url="https://github.com/eduardoaugustoes/cawnex.git",
            language="python",
            framework="fastapi",
        )
        session.add(repo)
        await session.flush()

        # === AGENT DEFINITIONS (templates) ===
        agents = {}

        agents["refinement"] = AgentDefinition(
            tenant_id=tenant.id,
            name="Refinement Agent",
            slug="refinement",
            description="Analyzes raw tasks and produces structured briefs with acceptance criteria.",
            system_prompt="You are a requirements analyst. Given a task, produce a clear brief with acceptance criteria.",
            model="claude-opus-4-6",
            tool_packs=["filesystem", "web_search"],
            max_tokens=8000,
            max_time_seconds=300,
            workspace_type="temp_dir",
        )

        agents["developer"] = AgentDefinition(
            tenant_id=tenant.id,
            name="Code Developer",
            slug="developer",
            description="Implements code changes based on refined briefs. Creates branches and PRs.",
            system_prompt="You are a senior software developer. Implement the requested changes.",
            model="claude-opus-4-6",
            tool_packs=["filesystem", "shell", "git", "github"],
            max_tokens=16000,
            max_time_seconds=900,
            workspace_type="git_worktree",
        )

        agents["reviewer"] = AgentDefinition(
            tenant_id=tenant.id,
            name="QA Reviewer",
            slug="reviewer",
            description="Reviews artifacts against acceptance criteria. Approves or rejects with feedback.",
            system_prompt="You are a QA engineer. Review the code against the acceptance criteria.",
            model="claude-sonnet-4-6",
            tool_packs=["filesystem", "shell", "git"],
            max_tokens=8000,
            max_time_seconds=300,
            workspace_type="temp_dir",
        )

        agents["documenter"] = AgentDefinition(
            tenant_id=tenant.id,
            name="Documentation Agent",
            slug="documenter",
            description="Updates documentation to reflect changes made by other agents.",
            system_prompt="You are a technical writer. Update documentation to reflect recent changes.",
            model="claude-haiku-4-6",
            tool_packs=["filesystem", "git"],
            max_tokens=4000,
            max_time_seconds=180,
            workspace_type="temp_dir",
        )

        for agent in agents.values():
            session.add(agent)
        await session.flush()

        # === WORKFLOW: Code Shipping ===
        workflow = Workflow(
            tenant_id=tenant.id,
            name="Code Shipping",
            slug="code-shipping",
            description="Issue → Refine → Implement → Review → Document",
            trigger_config={
                "source": "github",
                "event": "issue_labeled",
                "filters": {"label": "cawnex"},
            },
        )
        session.add(workflow)
        await session.flush()

        # Workflow steps
        steps = [
            WorkflowStep(
                workflow_id=workflow.id,
                agent_id=agents["refinement"].id,
                order=1,
                name="Refine",
                input_from="task",
                requires_approval=True,
                on_reject="fail",
                on_fail="fail",
            ),
            WorkflowStep(
                workflow_id=workflow.id,
                agent_id=agents["developer"].id,
                order=2,
                name="Implement",
                input_from="previous_step",
                requires_approval=False,
                on_reject="fail",
                on_fail="retry",
            ),
            WorkflowStep(
                workflow_id=workflow.id,
                agent_id=agents["reviewer"].id,
                order=3,
                name="Review",
                input_from="previous_step",
                requires_approval=False,
                on_reject="goto:Implement",
                on_fail="fail",
            ),
            WorkflowStep(
                workflow_id=workflow.id,
                agent_id=agents["documenter"].id,
                order=4,
                name="Document",
                input_from="previous_step",
                requires_approval=False,
                on_reject="fail",
                on_fail="skip",
            ),
        ]
        for step in steps:
            session.add(step)

        # === TEST TASK ===
        task = Task(
            tenant_id=tenant.id,
            workflow_id=workflow.id,
            source=TaskSource.MANUAL,
            source_ref="1",
            title="Add GET /health endpoint",
            description="Add a health check endpoint that returns API status, DB connection, Redis connection, and version.",
            status=TaskStatus.PENDING,
            context={
                "repository": "eduardoaugustoes/cawnex",
                "branch": "main",
            },
        )
        session.add(task)

        await session.commit()

        print("✅ Seeded!")
        print(f"   Tenant: {tenant.name} (id={tenant.id})")
        print(f"   Repo: {repo.github_full_name} (id={repo.id})")
        print(f"   Agents: {', '.join(a.name for a in agents.values())}")
        print(f"   Workflow: {workflow.name} ({len(steps)} steps)")
        print(f"   Task: '{task.title}'")
        print(f"   Encryption key: {ENCRYPTION_KEY.decode()}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
