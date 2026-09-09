import os
from unittest.mock import AsyncMock

import httpx
import respx
from app.application.service import GatewayService
from app.infrastructure.adapters import DemoIdentityAdapter, HttpGatewayAdapter
from app.main import create_app
from httpx import ASGITransport, AsyncClient
from itinerary_shared.auth import TokenService


@respx.mock
async def test_login_proxy_jwt_errors_and_limiter(headers):
    upstream_client = AsyncClient()
    tokens = TokenService(os.environ["JWT_SECRET"])
    service = GatewayService(
        DemoIdentityAdapter("student", "test-password-only", tokens),
        HttpGatewayAdapter(upstream_client, "http://airport", "http://itinerary", "http://report"),
    )
    limiter = AsyncMock()
    limiter.allow.return_value = True
    app = create_app(service, limiter)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/airports")).status_code == 401
        login = await client.post(
            "/api/auth/login", json={"username": "student", "password": "test-password-only"}
        )
        assert login.status_code == 200
        assert tokens.verify(login.json()["access_token"]) == "student"
        assert (
            await client.post("/api/auth/login", json={"username": "student", "password": "bad"})
        ).status_code == 401
        route = respx.get("http://airport/airports").respond(200, json=[{"id": 1}])
        result = await client.get(
            "/api/airports", headers={**headers, "X-Correlation-ID": "test-correlation"}
        )
        assert result.json() == [{"id": 1}]
        assert route.calls.last.request.headers["authorization"] == headers["Authorization"]
        assert route.calls.last.request.headers["x-correlation-id"] == "test-correlation"
        assert result.headers["cache-control"] == "no-store"
        route.mock(side_effect=httpx.ConnectError("offline"))
        assert (await client.get("/api/airports", headers=headers)).status_code == 503
        limiter.allow.return_value = False
        assert (await client.get("/api/airports", headers=headers)).status_code == 429
        limiter.allow.side_effect = ConnectionError()
        assert (await client.get("/api/airports", headers=headers)).status_code == 503
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/")).status_code == 200
    await upstream_client.aclose()


@respx.mock
async def test_crud_routes_forward_status_body_and_pagination(headers):
    async with AsyncClient() as upstream:
        service = GatewayService(
            None, HttpGatewayAdapter(upstream, "http://a", "http://i", "http://r")
        )
        limiter = AsyncMock()
        limiter.allow.return_value = True
        async with AsyncClient(
            transport=ASGITransport(app=create_app(service, limiter)), base_url="http://test"
        ) as client:
            respx.get("http://i/itineraries?offset=0&limit=10").respond(200, json=[])
            assert (
                await client.get("/api/itineraries?offset=0&limit=10", headers=headers)
            ).json() == []
            body = {
                "departure_airport_id": 1,
                "arrival_airport_id": 2,
                "departure_date": "2027-01-01",
                "duration_days": 2,
            }
            route = respx.post("http://i/itineraries").respond(201, json=body)
            assert (
                await client.post("/api/itineraries", json=body, headers=headers)
            ).status_code == 201
            assert b"departure_airport_id" in route.calls.last.request.content
            itinerary_id = "00000000-0000-0000-0000-000000000001"
            path = "/itineraries/" + itinerary_id
            respx.get("http://i" + path).respond(404, json={"detail": "Itinerary not found"})
            assert (await client.get("/api" + path, headers=headers)).status_code == 404
            respx.put("http://i" + path).respond(200, json=body)
            assert (await client.put("/api" + path, json=body, headers=headers)).status_code == 200
            respx.delete("http://i" + path).respond(204)
            assert (await client.delete("/api" + path, headers=headers)).status_code == 204
            respx.get("http://r/reports").respond(200, json={"total_itineraries": 0})
            assert (await client.get("/api/reports", headers=headers)).json()[
                "total_itineraries"
            ] == 0
