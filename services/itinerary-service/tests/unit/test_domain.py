from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
import respx
from app.application.service import ItineraryService
from app.domain.models import AirportUnavailable, BusinessRuleError, Itinerary
from app.infrastructure.adapters import AirportHttpClient, EventEncoder


@pytest.mark.parametrize(
    "departure,arrival,duration", [(1, 1, 3), (0, 2, 3), (1, 2, 0), (1, 2, 366)]
)
def test_business_rules(departure, arrival, duration):
    with pytest.raises(BusinessRuleError):
        Itinerary(
            uuid4(), "student", departure, arrival, date(2027, 1, 1), duration, datetime.now(UTC)
        )


async def test_missing_airport_prevents_transaction():
    airports, factory = AsyncMock(), Mock()
    airports.exists.return_value = False
    service = ItineraryService(factory, airports, EventEncoder())
    with pytest.raises(BusinessRuleError):
        await service.create("student", "token", 1, 2, date(2027, 1, 1), 3)
    factory.assert_not_called()


@respx.mock
async def test_airport_http_validation_propagates_token():
    route = respx.get("http://airport/airports/1").respond(200, json={"id": 1})
    async with httpx.AsyncClient() as client:
        adapter = AirportHttpClient(client, "http://airport")
        assert await adapter.exists(1, "jwt")
        assert route.calls.last.request.headers["authorization"] == "Bearer jwt"
        route.respond(404)
        assert not await adapter.exists(1, "jwt")
        route.respond(503)
        with pytest.raises(AirportUnavailable):
            await adapter.exists(1, "jwt")
