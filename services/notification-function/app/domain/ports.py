from typing import Protocol

from app.domain.models import Notification


class NotificationRepositoryPort(Protocol):
    async def save_once(self, notification: Notification) -> bool: ...


class UserContactPort(Protocol):
    async def phone_for(self, user_id: str) -> str | None: ...


class SmsSenderPort(Protocol):
    async def send(self, phone: str, message: str) -> None: ...
