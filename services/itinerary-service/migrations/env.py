import asyncio
import os

from alembic import context
from app.infrastructure.database import Base
from itinerary_shared.database import async_database_url
from sqlalchemy.ext.asyncio import create_async_engine


def configure(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run():
    engine = create_async_engine(async_database_url(os.environ["DATABASE_URL"]))
    async with engine.connect() as connection:
        await connection.run_sync(configure)
    await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Use online migrations with DATABASE_URL configured")
else:
    asyncio.run(run())
