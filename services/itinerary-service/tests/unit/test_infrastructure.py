from unittest.mock import AsyncMock, MagicMock

import pytest
from app.infrastructure import outbox_worker
from app.infrastructure.messaging import RabbitMQEventPublisher
from app.infrastructure.settings import Settings
from app.main import create_app


class Stop(BaseException):
    """Escapes the worker's infinite loop (not caught by `except Exception`)."""


async def test_rabbitmq_publisher_sends_persistent_mandatory_message():
    exchange = AsyncMock()
    publisher = RabbitMQEventPublisher(exchange, "itinerary.created")
    await publisher.publish(b"{}", event_id="e1", event_type="T", headers={"a": "b"})
    message = exchange.publish.call_args.args[0]
    assert message.message_id == "e1"
    assert message.type == "T"
    assert message.headers == {"a": "b"}
    assert message.delivery_mode == 2
    assert exchange.publish.call_args.kwargs == {
        "routing_key": "itinerary.created",
        "mandatory": True,
        "timeout": 10,
    }


async def test_worker_retries_after_broker_failure_then_publishes(monkeypatch):
    exchange = AsyncMock()
    connection = MagicMock()
    connection.__aenter__ = AsyncMock(return_value=connection)
    connection.__aexit__ = AsyncMock(return_value=False)
    connection.channel = AsyncMock()
    monkeypatch.setattr(
        outbox_worker.aio_pika,
        "connect_robust",
        AsyncMock(side_effect=[ConnectionError("down"), connection]),
    )
    monkeypatch.setattr(outbox_worker, "declare_topology", AsyncMock(return_value=(exchange, None)))
    batch = AsyncMock(return_value=0)
    monkeypatch.setattr(outbox_worker, "publish_batch", batch)
    sleep = AsyncMock(side_effect=[None, Stop()])
    monkeypatch.setattr(outbox_worker.asyncio, "sleep", sleep)

    with pytest.raises(Stop):
        await outbox_worker.run()

    assert sleep.call_args_list[0].args == (5,)
    publisher = batch.call_args.args[1]
    assert isinstance(publisher, RabbitMQEventPublisher)
    assert publisher.exchange is exchange


async def test_production_lifespan_wires_service_and_health():
    app = create_app(settings=Settings(database_url="sqlite+aiosqlite:///:memory:"))
    async with app.router.lifespan_context(app):
        assert app.state.service is not None
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.get("/health")).json() == {"status": "ok"}
