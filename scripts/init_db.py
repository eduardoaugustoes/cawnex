"""Initialize database — create all tables."""

import asyncio
from cawnex_core.models.db import create_engine, init_db

DATABASE_URL = "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex"


async def main():
    engine = create_engine(DATABASE_URL)
    print("Creating tables...")
    await init_db(engine)
    print("✅ All tables created!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
