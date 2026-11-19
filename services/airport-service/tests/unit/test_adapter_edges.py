import httpx
import pytest
import respx
from app.domain.models import AirportUnavailable
from app.infrastructure.adapters import AirportColombiaAdapter
from app.infrastructure.settings import Settings
from app.main import create_app


@pytest.mark.parametrize("payload", [[], {"not": "a list"}])
@respx.mock
async def test_empty_or_malformed_collection_is_unavailable(payload):
    respx.get("http://api/airports").respond(200, json=payload)
    async with httpx.AsyncClient() as client:
        adapter = AirportColombiaAdapter(client, "http://api/airports", attempts=1)
        with pytest.raises(AirportUnavailable):
            await adapter.list_airports()


async def test_production_lifespan_wires_service():
    app = create_app(settings=Settings(redis_url="redis://localhost:1/0"))
    async with app.router.lifespan_context(app):
        assert app.state.service is not None
