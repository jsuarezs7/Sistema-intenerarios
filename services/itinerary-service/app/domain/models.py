from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


class BusinessRuleError(Exception):
    pass


class ItineraryNotFound(Exception):
    pass


class AirportUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Itinerary:
    id: UUID
    user_id: str
    departure_airport_id: int
    arrival_airport_id: int
    departure_date: date
    duration_days: int
    created_at: datetime

    def __post_init__(self) -> None:
        if self.departure_airport_id == self.arrival_airport_id:
            raise BusinessRuleError("Departure and arrival airports must be different")
        if self.departure_airport_id <= 0 or self.arrival_airport_id <= 0:
            raise BusinessRuleError("Airport identifiers must be positive")
        if not 1 <= self.duration_days <= 365:
            raise BusinessRuleError("Duration must be between 1 and 365 days")


@dataclass(frozen=True)
class ItineraryCreatedEvent:
    event_id: UUID
    itinerary: Itinerary
    occurred_at: datetime


@dataclass(frozen=True)
class OutboxEvent:
    id: UUID
    payload: dict
    trace_context: dict[str, str]
