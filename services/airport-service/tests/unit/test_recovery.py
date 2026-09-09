import httpx
import pytest
import respx
from app.domain.models import AirportUnavailable
from app.infrastructure.adapters import AirportColombiaAdapter


@respx.mock
async def test_circuit_recovers_on_successful_probe(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("circuitbreaker.monotonic", lambda: clock[0])
    route = respx.get("https://example.test/Airport").respond(503)
    async with httpx.AsyncClient() as client:
        adapter = AirportColombiaAdapter(
            client,
            "https://example.test/Airport",
            attempts=1,
            failure_threshold=1,
            recovery_timeout=30,
            backoff=0,
        )
        with pytest.raises(AirportUnavailable):
            await adapter.list_airports()
        clock[0] += 31
        route.respond(200, json=[{"id": 1, "name": "Recovered", "latitude": 4, "longitude": -74}])
        assert (await adapter.list_airports())[0].name == "Recovered"
        assert adapter.breaker.closed
    assert route.call_count == 2
