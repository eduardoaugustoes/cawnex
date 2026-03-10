"""Seed database with test tenant and repo for dogfooding."""

import asyncio

from cryptography.fernet import Fernet
from sqlalchemy import select

from cawnex_core.enums import Provider, BYOLMode, IssueSource, IssueStatus
from cawnex_core.models import Tenant, LLMConfig, Repository, Issue
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

        # Create tenant
        tenant = Tenant(name="Cawnex Dogfood", slug="cawnex-dogfood")
        session.add(tenant)
        await session.flush()

        # Create LLM config (placeholder — real key added later)
        fernet = Fernet(ENCRYPTION_KEY)
        llm_config = LLMConfig(
            tenant_id=tenant.id,
            provider=Provider.ANTHROPIC,
            mode=BYOLMode.API_KEY,
            encrypted_api_key=fernet.encrypt(b"placeholder-key"),
        )
        session.add(llm_config)

        # Create repo
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

        # Create test issue
        issue = Issue(
            tenant_id=tenant.id,
            repository_id=repo.id,
            external_id="1",
            source=IssueSource.MANUAL,
            title="Add GET /health endpoint",
            description="Add a health check endpoint that returns API status, DB connection, Redis connection, and version.",
            status=IssueStatus.PENDING,
        )
        session.add(issue)

        await session.commit()

        print(f"✅ Seeded!")
        print(f"   Tenant: {tenant.name} (id={tenant.id})")
        print(f"   Repo: {repo.github_full_name} (id={repo.id})")
        print(f"   Issue: #{issue.external_id} — {issue.title} (id={issue.id})")
        print(f"   Encryption key: {ENCRYPTION_KEY.decode()}")
        print(f"   (save this key in .env as ENCRYPTION_KEY)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
