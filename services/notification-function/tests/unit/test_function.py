from unittest.mock import AsyncMock
from uuid import uuid4

from app.application.service import SendNotificationFunction


async def test_notification_uses_event_id_as_idempotency_key():
    repository = AsyncMock()
    repository.save_once.return_value = True
    event_id, itinerary_id = uuid4(), uuid4()
    assert await SendNotificationFunction(repository).handle(event_id, itinerary_id, "student")
    notification = repository.save_once.call_args.args[0]
    assert notification.event_id == event_id
    assert notification.itinerary_id == itinerary_id
    assert "created" in notification.message
