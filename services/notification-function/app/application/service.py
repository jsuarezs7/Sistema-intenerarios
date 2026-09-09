from datetime import UTC, datetime
from uuid import UUID

from app.domain.models import Notification
from app.domain.ports import NotificationRepositoryPort


class SendNotificationFunction:
    def __init__(self, repository: NotificationRepositoryPort):
        self.repository = repository

    async def handle(self, event_id: UUID, itinerary_id: UUID, user_id: str) -> bool:
        notification = Notification(
            event_id,
            itinerary_id,
            user_id,
            f"Itinerary {itinerary_id} created. Your trip is ready to plan.",
            datetime.now(UTC),
        )
        return await self.repository.save_once(notification)
