from unittest.mock import AsyncMock

from app import main
from app.application.service import SendNotificationFunction


async def test_worker_composes_its_repository_and_consumer(monkeypatch):
    consumer = AsyncMock()
    monkeypatch.setattr(main, "consume", consumer)
    await main.run()
    consumer.assert_awaited_once()
    assert isinstance(consumer.call_args.args[1], SendNotificationFunction)
