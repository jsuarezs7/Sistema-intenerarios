from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Uuid, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.models import Notification


class Base(DeclarativeBase):
    pass


class NotificationRow(Base):
    __tablename__ = "notifications"
    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    itinerary_id: Mapped[UUID] = mapped_column(Uuid)
    user_id: Mapped[str] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SqlNotificationRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def save_once(self, notification: Notification) -> bool:
        from dataclasses import asdict

        try:
            async with self.sessions() as session, session.begin():
                session.add(NotificationRow(**asdict(notification)))
                await session.flush()
            return True
        except IntegrityError:
            # Only the event_id primary key identifies a duplicate; don't hide other failures.
            async with self.sessions() as session:
                existing = await session.scalar(
                    select(NotificationRow).where(
                        NotificationRow.event_id == notification.event_id,
                    )
                )
                if existing is None:
                    raise
            return False
