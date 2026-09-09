import httpx
from itinerary_shared.observability import correlation_id
from itinerary_shared.urls import internal_url

from app.domain.models import ItineraryUnavailable


class HttpItineraryReader:
    def __init__(self, client: httpx.AsyncClient, base_url: str):
        self.client, self.base_url = client, internal_url(base_url)

    async def list_all(self, token: str) -> list[dict]:
        result = []
        try:
            while True:
                response = await self.client.get(
                    f"{self.base_url}/itineraries",
                    params={"offset": len(result), "limit": 100},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Correlation-ID": correlation_id.get(),
                    },
                )
                response.raise_for_status()
                page = response.json()
                if not isinstance(page, list):
                    raise ValueError("Expected itinerary list")
                result.extend(page)
                if len(page) < 100:
                    return result
        except (httpx.HTTPError, ValueError) as exc:
            raise ItineraryUnavailable("Report source temporarily unavailable") from exc
