from collections.abc import Callable
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from app.domain.models import (
    BusinessRuleError,
    Itinerary,
    ItineraryCreatedEvent,
    ItineraryNotFound,
)
from app.domain.ports import AirportClientPort, EventEncoderPort, UnitOfWorkPort


class ItineraryService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWorkPort],
        airports: AirportClientPort,
        encoder: EventEncoderPort,
    ):
        self.uow_factory = uow_factory
        self.airports = airports
        self.encoder = encoder

    async def _validate(self, itinerary: Itinerary, token: str) -> None:
        for airport_id in (itinerary.departure_airport_id, itinerary.arrival_airport_id):
            if not await self.airports.exists(airport_id, token):
                raise BusinessRuleError(f"Airport {airport_id} does not exist")

    async def create(
        self,
        user_id: str,
        token: str,
        departure_airport_id: int,
        arrival_airport_id: int,
        departure_date: date,
        duration_days: int,
    ) -> Itinerary:
        now = datetime.now(UTC)
        itinerary = Itinerary(
            uuid4(),
            user_id,
            departure_airport_id,
            arrival_airport_id,
            departure_date,
            duration_days,
            now,
        )
        await self._validate(itinerary, token)
        event = self.encoder.encode(ItineraryCreatedEvent(uuid4(), itinerary, now))
        async with self.uow_factory() as uow:
            await uow.itineraries.add(itinerary)
            await uow.outbox.add(event)
        return itinerary

    async def get(self, itinerary_id: UUID, user_id: str) -> Itinerary:
        async with self.uow_factory() as uow:
            itinerary = await uow.itineraries.get(itinerary_id, user_id)
            if itinerary is None:
                raise ItineraryNotFound(itinerary_id)
            return itinerary

    async def list(self, user_id: str, offset: int = 0, limit: int = 100) -> list[Itinerary]:
        async with self.uow_factory() as uow:
            return await uow.itineraries.list(user_id, offset, limit)

    async def update(
        self,
        itinerary_id: UUID,
        user_id: str,
        token: str,
        departure_airport_id: int,
        arrival_airport_id: int,
        departure_date: date,
        duration_days: int,
    ) -> Itinerary:
        existing = await self.get(itinerary_id, user_id)
        updated = Itinerary(
            existing.id,
            user_id,
            departure_airport_id,
            arrival_airport_id,
            departure_date,
            duration_days,
            existing.created_at,
        )
        await self._validate(updated, token)
        async with self.uow_factory() as uow:
            # Lock inside the write transaction to avoid resurrecting a deleted record.
            if await uow.itineraries.get(itinerary_id, user_id) is None:
                raise ItineraryNotFound(itinerary_id)
            await uow.itineraries.update(updated)
        return updated

    async def delete(self, itinerary_id: UUID, user_id: str) -> None:
        async with self.uow_factory() as uow:
            if not await uow.itineraries.delete(itinerary_id, user_id):
                raise ItineraryNotFound(itinerary_id)
