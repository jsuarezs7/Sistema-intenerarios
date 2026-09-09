from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Notification:
    event_id: UUID
    itinerary_id: UUID
    user_id: str
    message: str
    created_at: datetime
