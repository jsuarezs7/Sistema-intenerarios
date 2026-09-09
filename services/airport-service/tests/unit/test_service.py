from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from app.application.service import AirportService
from app.domain.models import Airport, AirportNotFound, AirportUnavailable
from app.infrastructure.adapters import AirportColombiaAdapter, RedisCacheAdapter

AIRPORT = Airport(1, "El Dorado", "Bogotá", "BOG", 4.7, -74.1)
RAW = {
    "id": 1,
    "name": "El Dorado",
    "city": {"name": "Bogotá"},
    "iataCode": "BOG",
    "latitude": -74.1,
    "longitude": 4.7,
}


async def test_cache_hit_does_not_call_external():
    external, cache = AsyncMock(), AsyncMock()
    cache.get.return_value = [AIRPORT]
    assert await AirportService(external, cache).get(1) == AIRPORT
    external.list_airports.assert_not_called()


async def test_miss_writes_fresh_and_stale():
    external, cache = AsyncMock(), AsyncMock()
    cache.get.return_value = None
    external.list_airports.return_value = [AIRPORT]
    assert await AirportService(external, cache).list_airports() == [AIRPORT]
    assert cache.set.await_count == 2


async def test_provider_failure_uses_stale():
    external, cache = AsyncMock(), AsyncMock()
    cache.get.side_effect = [None, [AIRPORT]]
    external.list_airports.side_effect = AirportUnavailable()
    assert await AirportService(external, cache).list_airports() == [AIRPORT]


async def test_cache_failure_does_not_hide_healthy_provider():
    external, cache = AsyncMock(), AsyncMock()
    cache.get.side_effect = ConnectionError()
    cache.set.side_effect = ConnectionError()
    external.list_airports.return_value = [AIRPORT]
    assert await AirportService(external, cache).list_airports() == [AIRPORT]


async def test_no_fallback_is_controlled():
    external, cache = AsyncMock(), AsyncMock()
    cache.get.return_value = None
    external.list_airports.side_effect = AirportUnavailable()
    with pytest.raises(AirportUnavailable):
        await AirportService(external, cache).list_airports()


async def test_not_found():
    cache = AsyncMock()
    cache.get.return_value = []
    with pytest.raises(AirportNotFound):
        await AirportService(AsyncMock(), cache).get(9)


@pytest.mark.parametrize(
    "lat,lon,expected",
    [
        (-74.1, 4.7, (4.7, -74.1)),
        (4.7, -74.1, (4.7, -74.1)),
        (None, "invalid", (None, None)),
        (500, 500, (None, None)),
    ],
)
def test_adapter_coordinates(lat, lon, expected):
    airport = AirportColombiaAdapter.translate({**RAW, "latitude": lat, "longitude": lon})
    assert (airport.latitude, airport.longitude) == expected
    assert airport.city == "Bogotá"


@respx.mock
async def test_retry_then_success():
    route = respx.get("https://example.test/Airport").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=[RAW]),
        ]
    )
    async with httpx.AsyncClient() as client:
        adapter = AirportColombiaAdapter(client, "https://example.test/Airport", backoff=0)
        assert (await adapter.list_airports())[0].id == 1
    assert route.call_count == 2


@respx.mock
async def test_circuit_opens_after_failure_and_skips_network():
    route = respx.get("https://example.test/Airport").respond(503)
    async with httpx.AsyncClient() as client:
        adapter = AirportColombiaAdapter(
            client, "https://example.test/Airport", backoff=0, failure_threshold=1
        )
        for _ in range(2):
            with pytest.raises(AirportUnavailable):
                await adapter.list_airports()
    assert route.call_count == 3
    assert adapter.breaker.opened


@respx.mock
async def test_404_is_not_retried():
    route = respx.get("https://example.test/Airport").respond(404)
    async with httpx.AsyncClient() as client:
        with pytest.raises(AirportUnavailable):
            await AirportColombiaAdapter(
                client, "https://example.test/Airport", backoff=0
            ).list_airports()
    assert route.call_count == 1


async def test_redis_serialization_and_ttl():
    redis = AsyncMock()
    cache = RedisCacheAdapter(redis)
    await cache.set("airports", [AIRPORT], 60)
    redis.get.return_value = redis.set.call_args.args[1]
    assert await cache.get("airports") == [AIRPORT]
    assert redis.set.call_args.kwargs["ex"] == 60
