"""Initialize database — drop and recreate all tables."""

import asyncio
from cawnex_core.models.db import create_engine, init_db
from cawnex_core.models.base import Base

# Import all models so they register with Base
from cawnex_core.models import (  # noqa: F401
    Tenant, LLMConfig, Repository, Task, AgentDefinition,
    Workflow, WorkflowStep, Execution, ExecutionEvent, Artifact,
)

DATABASE_URL = "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex"


async def main():
    engine = create_engine(DATABASE_URL)
    print("Dropping existing tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("Creating tables...")
    await init_db(engine)
    print("✅ All tables created!")

    # List tables
    async with engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        ))
        tables = [row[0] for row in result]
        print(f"   Tables: {', '.join(tables)}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
