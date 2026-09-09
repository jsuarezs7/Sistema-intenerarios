from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ItineraryCreatedEvent(BaseModel):
    """Versioned wire contract; domain entities remain framework-independent."""

    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    event_type: Literal["ItineraryCreatedEvent"] = "ItineraryCreatedEvent"
    schema_version: Literal[1] = 1
    occurred_at: datetime
    itinerary_id: UUID
    user_id: str = Field(min_length=1)
    departure_airport_id: int = Field(gt=0)
    arrival_airport_id: int = Field(gt=0)
    departure_date: date
    duration_days: int = Field(ge=1, le=365)
