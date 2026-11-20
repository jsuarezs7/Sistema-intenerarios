import httpx
import pytest
import respx
from app.domain.models import ItineraryUnavailable
from app.infrastructure.adapters import HttpItineraryReader
from app.infrastructure.settings import Settings
from app.main import create_app


@respx.mock
async def test_reader_paginates_until_short_page():
    route = respx.get("http://itinerary/itineraries").mock(
        side_effect=[
            httpx.Response(200, json=[{"n": i} for i in range(100)]),
            httpx.Response(200, json=[{"n": 100}]),
        ]
    )
    async with httpx.AsyncClient() as client:
        items = await HttpItineraryReader(client, "http://itinerary").list_all("jwt")
    assert len(items) == 101
    assert route.calls[1].request.url.params["offset"] == "100"


@pytest.mark.parametrize(
    "response", [httpx.Response(200, json={"not": "a list"}), httpx.Response(500)]
)
@respx.mock
async def test_reader_maps_bad_upstream_to_unavailable(response):
    respx.get("http://itinerary/itineraries").mock(return_value=response)
    async with httpx.AsyncClient() as client:
        with pytest.raises(ItineraryUnavailable):
            await HttpItineraryReader(client, "http://itinerary").list_all("jwt")


async def test_production_lifespan_wires_function():
    app = create_app(settings=Settings())
    async with app.router.lifespan_context(app):
        assert app.state.service is not None
