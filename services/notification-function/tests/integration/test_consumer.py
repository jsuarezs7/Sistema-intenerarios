from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from app.application.service import SendNotificationFunction
from app.infrastructure.consumer import process_message
from app.infrastructure.database import Base, NotificationRow, SqlNotificationRepository
from itinerary_shared.events import ItineraryCreatedEvent
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def message():
    event = ItineraryCreatedEvent(
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        itinerary_id=uuid4(),
        user_id="student",
        departure_airport_id=1,
        arrival_airport_id=2,
        departure_date="2027-01-01",
        duration_days=2,
    )
    msg = AsyncMock()
    msg.body = event.model_dump_json().encode()
    msg.headers = {}
    return msg


async def test_redelivery_stores_one_notification_and_acks_after_commit():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine)
    function = SendNotificationFunction(SqlNotificationRepository(sessions))
    msg = message()

    async def verify_commit():
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(NotificationRow)) == 1

    msg.ack.side_effect = verify_commit
    await process_message(msg, function)
    await process_message(msg, function)
    assert msg.ack.await_count == 2
    msg.reject.assert_not_called()
    await engine.dispose()


async def test_malformed_event_dead_letters():
    msg = message()
    msg.body = b'{"schema_version": 2}'
    function = AsyncMock()
    await process_message(msg, function)
    msg.reject.assert_awaited_once_with(requeue=False)
    function.handle.assert_not_called()
    msg.ack.assert_not_called()


async def test_storage_failure_requeues(monkeypatch):
    monkeypatch.setattr("app.infrastructure.consumer.asyncio.sleep", AsyncMock())
    msg, function = message(), AsyncMock()
    function.handle.side_effect = ConnectionError()
    await process_message(msg, function)
    msg.nack.assert_awaited_once_with(requeue=True)
    msg.ack.assert_not_called()
