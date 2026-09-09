import os
from unittest.mock import AsyncMock

import pytest
from app.application.service import ItineraryService
from app.domain.models import AirportUnavailable
from app.infrastructure.adapters import EventEncoder
from app.infrastructure.database import (
    Base,
    ItineraryRow,
    OutboxRow,
    SqlOutboxRepository,
    SqlUnitOfWork,
)
from app.infrastructure.outbox_worker import publish_batch
from app.main import create_app
from httpx import ASGITransport, AsyncClient
from itinerary_shared.auth import TokenService
from itinerary_shared.events import ItineraryCreatedEvent
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BODY = {
    "departure_airport_id": 1,
    "arrival_airport_id": 2,
    "departure_date": "2027-01-01",
    "duration_days": 4,
}


@pytest.fixture
async def system():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    airports = AsyncMock()
    airports.exists.return_value = True
    service = ItineraryService(lambda: SqlUnitOfWork(sessions), airports, EventEncoder())
    async with AsyncClient(
        transport=ASGITransport(app=create_app(service)), base_url="http://test"
    ) as client:
        yield client, sessions, airports
    await engine.dispose()


async def test_crud_persists_event_and_enforces_ownership(system, headers):
    client, sessions, _ = system
    response = await client.post("/itineraries", json=BODY, headers=headers)
    assert response.status_code == 201, response.text
    itinerary = response.json()
    async with sessions() as session:
        events = list(await session.scalars(select(OutboxRow)))
        assert len(events) == 1
        event = ItineraryCreatedEvent.model_validate(events[0].payload)
        assert str(event.itinerary_id) == itinerary["id"]
        assert events[0].published_at is None
    path = "/itineraries/" + itinerary["id"]
    assert (await client.get(path, headers=headers)).json()["id"] == itinerary["id"]
    assert len((await client.get("/itineraries", headers=headers)).json()) == 1
    other = {"Authorization": "Bearer " + TokenService(os.environ["JWT_SECRET"]).issue("other")}
    assert (await client.get(path, headers=other)).status_code == 404
    assert (await client.get("/itineraries", headers=other)).json() == []
    assert (await client.put(path, json=BODY, headers=other)).status_code == 404
    assert (await client.delete(path, headers=other)).status_code == 404
    updated = await client.put(path, json={**BODY, "duration_days": 9}, headers=headers)
    assert updated.json()["duration_days"] == 9
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(OutboxRow)) == 1
    assert (await client.delete(path, headers=headers)).status_code == 204
    assert (await client.get(path, headers=headers)).status_code == 404


async def test_outbox_failure_rolls_back_itinerary(system, headers, monkeypatch):
    client, sessions, _ = system
    from sqlalchemy.exc import SQLAlchemyError

    monkeypatch.setattr(
        SqlOutboxRepository, "add", AsyncMock(side_effect=SQLAlchemyError("failure"))
    )
    assert (await client.post("/itineraries", json=BODY, headers=headers)).status_code == 503
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ItineraryRow)) == 0
        assert await session.scalar(select(func.count()).select_from(OutboxRow)) == 0


async def test_validation_statuses(system, headers):
    client, sessions, airports = system
    assert (await client.post("/itineraries", json=BODY)).status_code == 401
    assert (
        await client.post("/itineraries", json={**BODY, "duration_days": 0}, headers=headers)
    ).status_code == 422
    assert (
        await client.post("/itineraries", json={**BODY, "departure_date": "bad"}, headers=headers)
    ).status_code == 422
    assert (
        await client.post("/itineraries", json={**BODY, "arrival_airport_id": 1}, headers=headers)
    ).status_code == 400
    airports.exists.return_value = False
    assert (await client.post("/itineraries", json=BODY, headers=headers)).status_code == 400
    airports.exists.side_effect = AirportUnavailable()
    assert (await client.post("/itineraries", json=BODY, headers=headers)).status_code == 503
    assert (await client.get("/itineraries?limit=101", headers=headers)).status_code == 422
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ItineraryRow)) == 0


async def test_worker_confirms_before_marking_and_failed_delivery_retries(system, headers):
    client, sessions, _ = system
    await client.post("/itineraries", json=BODY, headers=headers)
    exchange = AsyncMock()
    exchange.publish.side_effect = ConnectionError("broker offline")
    with pytest.raises(ConnectionError):
        await publish_batch(sessions, exchange)
    async with sessions() as session:
        assert (await session.scalar(select(OutboxRow))).published_at is None
    exchange.publish.side_effect = None
    assert await publish_batch(sessions, exchange) == 1
    assert await publish_batch(sessions, exchange) == 0
    async with sessions() as session:
        assert (await session.scalar(select(OutboxRow))).published_at is not None
    message = exchange.publish.call_args.args[0]
    assert message.delivery_mode == 2
    ItineraryCreatedEvent.model_validate_json(message.body)
