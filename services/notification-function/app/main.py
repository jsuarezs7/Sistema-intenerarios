import asyncio

from itinerary_shared.database import async_database_url
from itinerary_shared.observability import configure
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.service import SendNotificationFunction
from app.infrastructure.consumer import consume
from app.infrastructure.database import SqlNotificationRepository
from app.infrastructure.settings import Settings


async def run() -> None:
    settings = Settings()
    configure("notification-function")
    engine = create_async_engine(
        async_database_url(settings.notification_database_url), pool_pre_ping=True
    )
    try:
        function = SendNotificationFunction(
            SqlNotificationRepository(async_sessionmaker(engine, expire_on_commit=False))
        )
        await consume(settings.rabbitmq_url, function)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
