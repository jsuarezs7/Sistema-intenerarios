from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ItineraryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    departure_airport_id: int = Field(gt=0)
    arrival_airport_id: int = Field(gt=0)
    departure_date: date
    duration_days: int = Field(ge=1, le=365)


class ItineraryView(ItineraryInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: str
    created_at: datetime
