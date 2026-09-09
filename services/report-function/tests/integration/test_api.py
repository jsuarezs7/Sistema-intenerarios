from unittest.mock import AsyncMock

import respx
from app.application.service import GenerateItineraryReportFunction
from app.domain.models import ItineraryUnavailable
from app.infrastructure.adapters import HttpItineraryReader
from app.main import create_app
from httpx import ASGITransport, AsyncClient


async def test_report_endpoint_and_failure(headers):
    reader = AsyncMock()
    reader.list_all.return_value = []
    service = GenerateItineraryReportFunction(reader)
    async with AsyncClient(
        transport=ASGITransport(app=create_app(service)), base_url="http://test"
    ) as client:
        assert (await client.get("/reports")).status_code == 401
        response = await client.get("/reports", headers=headers)
        assert response.json()["total_itineraries"] == 0
        reader.list_all.side_effect = ItineraryUnavailable()
        assert (await client.get("/reports", headers=headers)).status_code == 503
        assert (await client.get("/health")).status_code == 200


@respx.mock
async def test_report_reader_paginates_and_propagates_jwt():
    page = [{"departure_airport_id": 1, "arrival_airport_id": 2, "duration_days": 2}] * 100
    first = respx.get("http://itinerary/itineraries?offset=0&limit=100").respond(200, json=page)
    respx.get("http://itinerary/itineraries?offset=100&limit=100").respond(200, json=page[:1])
    async with AsyncClient() as client:
        result = await HttpItineraryReader(client, "http://itinerary").list_all("jwt")
        assert len(result) == 101
    assert first.calls.last.request.headers["authorization"] == "Bearer jwt"
