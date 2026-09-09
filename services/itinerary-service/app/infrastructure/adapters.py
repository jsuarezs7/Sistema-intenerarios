import httpx
from itinerary_shared.events import ItineraryCreatedEvent as EventContract
from itinerary_shared.observability import correlation_id
from itinerary_shared.urls import internal_url
from opentelemetry.propagate import inject

from app.domain.models import AirportUnavailable, ItineraryCreatedEvent, OutboxEvent


class AirportHttpClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str):
        self.client, self.base_url = client, internal_url(base_url)

    async def exists(self, airport_id: int, token: str) -> bool:
        try:
            response = await self.client.get(
                f"{self.base_url}/airports/{airport_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Correlation-ID": correlation_id.get(),
                },
            )
            if response.status_code == 404:
                return False
            response.raise_for_status()
            return response.json()["id"] == airport_id
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise AirportUnavailable("Airport validation temporarily unavailable") from exc


class EventEncoder:
    def encode(self, event: ItineraryCreatedEvent) -> OutboxEvent:
        itinerary = event.itinerary
        contract = EventContract(
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            itinerary_id=itinerary.id,
            user_id=itinerary.user_id,
            departure_airport_id=itinerary.departure_airport_id,
            arrival_airport_id=itinerary.arrival_airport_id,
            departure_date=itinerary.departure_date,
            duration_days=itinerary.duration_days,
        )
        headers = {"correlation_id": correlation_id.get()}
        inject(headers)
        return OutboxEvent(event.event_id, contract.model_dump(mode="json"), headers)
