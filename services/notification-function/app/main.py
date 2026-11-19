import asyncio

from fastapi import FastAPI
from itinerary_shared.database import async_database_url
from itinerary_shared.observability import configure
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.service import SendNotificationFunction
from app.infrastructure.consumer import consume
from app.infrastructure.database import SqlNotificationRepository
from app.infrastructure.settings import Settings
from app.infrastructure.users import ConsoleSmsSender, SqlUserContacts

app = FastAPI(title="Notification Function", version="1.0.0")


@app.get("/health", tags=["Operations"])
async def health():
    return {"status": "ok"}


async def run() -> None:
    settings = Settings()
    configure("notification-function")
    engine = create_async_engine(
        async_database_url(settings.notification_database_url), pool_pre_ping=True
    )
    user_engine = (
        create_async_engine(async_database_url(settings.user_database_url), pool_pre_ping=True)
        if settings.user_database_url
        else None
    )
    try:
        function = SendNotificationFunction(
            SqlNotificationRepository(async_sessionmaker(engine, expire_on_commit=False)),
            SqlUserContacts(async_sessionmaker(user_engine, expire_on_commit=False))
            if user_engine
            else None,
            ConsoleSmsSender(),
        )
        await consume(settings.rabbitmq_url, function)
    finally:
        await engine.dispose()
        if user_engine:
            await user_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
