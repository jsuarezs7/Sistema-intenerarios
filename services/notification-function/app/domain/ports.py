from typing import Protocol

from app.domain.models import Notification


class NotificationRepositoryPort(Protocol):
    async def save_once(self, notification: Notification) -> bool: ...
