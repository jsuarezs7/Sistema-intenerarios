from datetime import UTC, datetime
from uuid import UUID

from app.domain.models import Notification
from app.domain.ports import NotificationRepositoryPort, SmsSenderPort, UserContactPort


class SendNotificationFunction:
    def __init__(
        self,
        repository: NotificationRepositoryPort,
        contacts: UserContactPort | None = None,
        sms_sender: SmsSenderPort | None = None,
    ):
        self.repository = repository
        self.contacts = contacts
        self.sms_sender = sms_sender

    async def handle(self, event_id: UUID, itinerary_id: UUID, user_id: str) -> bool:
        notification = Notification(
            event_id,
            itinerary_id,
            user_id,
            f"Itinerary {itinerary_id} created. Your trip is ready to plan.",
            datetime.now(UTC),
        )
        inserted = await self.repository.save_once(notification)
        if inserted and self.contacts and self.sms_sender:
            phone = await self.contacts.phone_for(user_id)
            if phone:
                await self.sms_sender.send(phone, notification.message)
        return inserted
