import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from itinerary_shared import observability
from itinerary_shared.auth import Principal, TokenService
from itinerary_shared.broker import DEAD_QUEUE, EXCHANGE, QUEUE, ROUTING_KEY, declare_topology
from itinerary_shared.database import async_database_url
from itinerary_shared.events import ItineraryCreatedEvent
from itinerary_shared.schemas import ItineraryInput
from itinerary_shared.urls import internal_url
from opentelemetry.sdk.trace import TracerProvider
from pydantic import ValidationError

SECRET = "test-signing-key-only-for-tests-123456789"


def test_token_roundtrip_and_short_secret_rejected():
    tokens = TokenService(SECRET)
    assert tokens.verify(tokens.issue("ana")) == "ana"
    with pytest.raises(ValueError):
        TokenService("short")


def test_token_with_empty_subject_is_invalid():
    tokens = TokenService(SECRET)
    now = datetime.now(UTC)
    payload = {
        "sub": "",
        "iss": tokens.issuer,
        "aud": tokens.audience,
        "iat": now,
        "exp": now + timedelta(minutes=1),
    }
    with pytest.raises(jwt.InvalidTokenError):
        tokens.verify(jwt.encode(payload, SECRET, algorithm="HS256"))


async def test_fastapi_dependency_accepts_valid_and_rejects_missing_or_bad_tokens():
    tokens = TokenService(SECRET)
    app = FastAPI()

    @app.get("/me")
    async def me(principal: Principal = Depends(tokens.dependency())):
        return {"user": principal.user_id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        ok = await client.get("/me", headers={"Authorization": "Bearer " + tokens.issue("ana")})
        assert ok.json() == {"user": "ana"}
        missing = await client.get("/me")
        assert missing.status_code == 401
        assert missing.headers["www-authenticate"] == "Bearer"
        bad = await client.get("/me", headers={"Authorization": "Bearer nope"})
        assert bad.status_code == 401


async def test_declare_topology_binds_queue_with_dead_lettering():
    channel = AsyncMock()
    exchange, dead_exchange, dead_queue, queue = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    channel.declare_exchange.side_effect = [exchange, dead_exchange]
    channel.declare_queue.side_effect = [dead_queue, queue]
    assert await declare_topology(channel) == (exchange, queue)
    assert channel.declare_exchange.call_args_list[0].args[0] == EXCHANGE
    assert channel.declare_queue.call_args_list[0].args[0] == DEAD_QUEUE
    assert channel.declare_queue.call_args_list[1].args[0] == QUEUE
    assert channel.declare_queue.call_args_list[1].kwargs["arguments"]["x-dead-letter-exchange"]
    queue.bind.assert_awaited_once_with(exchange, routing_key=ROUTING_KEY)
    dead_queue.bind.assert_awaited_once()


@pytest.mark.parametrize(
    "value,expected",
    [
        ("postgres://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("postgresql://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("sqlite+aiosqlite:///:memory:", "sqlite+aiosqlite:///:memory:"),
    ],
)
def test_async_database_url(value, expected):
    assert async_database_url(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [("itinerary:8000", "http://itinerary:8000"), ("https://x.example/", "https://x.example")],
)
def test_internal_url(value, expected):
    assert internal_url(value) == expected


def test_contracts_validate_inputs():
    ItineraryInput(
        departure_airport_id=1, arrival_airport_id=2, departure_date="2027-01-01", duration_days=3
    )
    with pytest.raises(ValidationError):
        ItineraryInput(
            departure_airport_id=1,
            arrival_airport_id=2,
            departure_date="2027-01-01",
            duration_days=0,
            extra=1,
        )
    with pytest.raises(ValidationError):
        ItineraryCreatedEvent.model_validate({"schema_version": 2})


async def test_configure_adds_json_logging_tracing_and_correlation_header(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318/")
    provider = MagicMock()
    monkeypatch.setattr(observability.trace, "get_tracer_provider", lambda: provider)
    set_provider = MagicMock()
    monkeypatch.setattr(observability.trace, "set_tracer_provider", set_provider)
    instrument = MagicMock()
    monkeypatch.setattr(observability.HTTPXClientInstrumentor, "instrument", instrument)

    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"correlation": observability.correlation_id.get()}

    observability.configure("test-service", app)
    assert isinstance(set_provider.call_args.args[0], TracerProvider)
    instrument.assert_called_once()
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
    assert logging.getLogger().handlers[0].filters[0].filter(record)
    assert hasattr(record, "trace_id") and hasattr(record, "correlation_id")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        kept = await client.get("/ping", headers={"X-Correlation-ID": "abc-123"})
        assert kept.headers["x-correlation-id"] == "abc-123"
        assert kept.json() == {"correlation": "abc-123"}
        replaced = await client.get("/ping", headers={"X-Correlation-ID": "bad value!"})
        assert replaced.headers["x-correlation-id"] != "bad value!"
