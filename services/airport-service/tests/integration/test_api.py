from unittest.mock import AsyncMock

from app.domain.models import Airport, AirportNotFound, AirportUnavailable
from app.main import create_app
from httpx import ASGITransport, AsyncClient


async def test_airport_endpoints_and_auth(headers):
    service = AsyncMock()
    service.list_airports.return_value = [Airport(1, "Airport", "City", None, None, None)]
    service.get.return_value = service.list_airports.return_value[0]
    async with AsyncClient(
        transport=ASGITransport(app=create_app(service)), base_url="http://test"
    ) as client:
        assert (await client.get("/airports")).status_code == 401
        assert (await client.get("/airports", headers=headers)).json()[0]["id"] == 1
        assert (await client.get("/airports/1", headers=headers)).status_code == 200
        assert (await client.get("/airports/0", headers=headers)).status_code == 422
        service.get.side_effect = AirportNotFound()
        assert (await client.get("/airports/999", headers=headers)).status_code == 404
        service.list_airports.side_effect = AirportUnavailable()
        assert (await client.get("/airports", headers=headers)).status_code == 503
        assert (await client.get("/health")).status_code == 200
