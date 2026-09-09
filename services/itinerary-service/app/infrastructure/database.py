from dataclasses import asdict
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Uuid,
    delete,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.models import Itinerary, OutboxEvent


class Base(DeclarativeBase):
    pass


class ItineraryRow(Base):
    __tablename__ = "itineraries"
    __table_args__ = (
        CheckConstraint("departure_airport_id <> arrival_airport_id"),
        CheckConstraint("duration_days BETWEEN 1 AND 365"),
        Index("ix_itinerary_user_created", "user_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128))
    departure_airport_id: Mapped[int] = mapped_column(Integer)
    arrival_airport_id: Mapped[int] = mapped_column(Integer)
    departure_date: Mapped[date] = mapped_column(Date)
    duration_days: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OutboxRow(Base):
    __tablename__ = "outbox"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    trace_context: Mapped[dict] = mapped_column(JSON)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def to_domain(row: ItineraryRow) -> Itinerary:
    return Itinerary(**{name: getattr(row, name) for name in Itinerary.__dataclass_fields__})


class SqlItineraryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, itinerary: Itinerary) -> None:
        self.session.add(ItineraryRow(**asdict(itinerary)))
        await self.session.flush()

    async def get(self, itinerary_id: UUID, user_id: str) -> Itinerary | None:
        row = await self.session.scalar(
            select(ItineraryRow)
            .where(
                ItineraryRow.id == itinerary_id,
                ItineraryRow.user_id == user_id,
            )
            .with_for_update()
        )
        return to_domain(row) if row else None

    async def list(self, user_id: str, offset: int, limit: int) -> list[Itinerary]:
        rows = await self.session.scalars(
            select(ItineraryRow)
            .where(
                ItineraryRow.user_id == user_id,
            )
            .order_by(ItineraryRow.created_at, ItineraryRow.id)
            .offset(offset)
            .limit(limit)
        )
        return [to_domain(row) for row in rows]

    async def update(self, itinerary: Itinerary) -> None:
        row = await self.session.get(ItineraryRow, itinerary.id)
        for name, value in asdict(itinerary).items():
            setattr(row, name, value)
        await self.session.flush()

    async def delete(self, itinerary_id: UUID, user_id: str) -> bool:
        result = await self.session.execute(
            delete(ItineraryRow).where(
                ItineraryRow.id == itinerary_id,
                ItineraryRow.user_id == user_id,
            )
        )
        return result.rowcount > 0


class SqlOutboxRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, event: OutboxEvent) -> None:
        self.session.add(
            OutboxRow(id=event.id, payload=event.payload, trace_context=event.trace_context)
        )
        await self.session.flush()


class SqlUnitOfWork:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]):
        self.sessions = sessions

    async def __aenter__(self):
        self.session = self.sessions()
        await self.session.begin()
        self.itineraries = SqlItineraryRepository(self.session)
        self.outbox = SqlOutboxRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                await self.session.commit()
            else:
                await self.session.rollback()
        finally:
            await self.session.close()
