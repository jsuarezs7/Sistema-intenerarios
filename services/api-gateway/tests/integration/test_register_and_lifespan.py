from unittest.mock import AsyncMock

from app.domain.models import UserAlreadyExists
from app.infrastructure.settings import Settings
from app.main import create_app
from httpx import ASGITransport, AsyncClient

REGISTER = {
    "username": "ana_01",
    "name": "Ana Pérez",
    "email": "ana@example.com",
    "phone": "+57 300 111 2233",
    "password": "long-password-1",
}


def _app(service):
    limiter = AsyncMock()
    limiter.allow.return_value = True
    return create_app(service, limiter)


async def test_register_returns_token_and_conflict_maps_to_409(headers):
    service = AsyncMock()
    service.register.return_value = "new-token"
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://t"
    ) as client:
        created = await client.post("/api/auth/register", json=REGISTER)
        assert created.status_code == 201
        assert created.json()["access_token"] == "new-token"
        service.register.side_effect = UserAlreadyExists()
        assert (await client.post("/api/auth/register", json=REGISTER)).status_code == 409
        assert (
            await client.post("/api/auth/register", json={**REGISTER, "password": "short"})
        ).status_code == 422


async def test_airport_detail_and_upstream_401_sets_bearer_challenge(headers):
    service = AsyncMock()
    service.forward.return_value = (401, b'{"detail":"no"}', "application/json")
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://t"
    ) as client:
        response = await client.get("/api/airports/7", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert service.forward.call_args.args[:2] == ("GET", "/airports/7")


async def test_production_lifespan_builds_real_adapters_and_closes_them():
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:", redis_url="redis://localhost:1/0"
    )
    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        assert app.state.service.users is not None
        assert app.state.limiter is not None
