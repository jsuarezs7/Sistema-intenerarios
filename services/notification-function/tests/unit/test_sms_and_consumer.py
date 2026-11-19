import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app import main
from app.application.service import SendNotificationFunction
from app.domain.models import Notification
from app.infrastructure import consumer
from app.infrastructure.database import SqlNotificationRepository
from app.infrastructure.users import ConsoleSmsSender, SqlUserContacts
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class Stop(BaseException):
    """Escapes the consumer's infinite loop (not caught by `except Exception`)."""


@pytest.mark.parametrize(
    "inserted,phone,sent",
    [(True, "+573001112233", True), (True, None, False), (False, "+57", False)],
)
async def test_sms_sent_only_for_new_notifications_with_phone(inserted, phone, sent):
    repository, contacts, sms = AsyncMock(), AsyncMock(), AsyncMock()
    repository.save_once.return_value = inserted
    contacts.phone_for.return_value = phone
    function = SendNotificationFunction(repository, contacts, sms)
    assert await function.handle(uuid4(), uuid4(), "ana") is inserted
    assert sms.send.called is sent


async def test_sql_user_contacts_reads_phone_from_users_table():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.execute(text("CREATE TABLE users (username TEXT PRIMARY KEY, phone TEXT)"))
        await connection.execute(text("INSERT INTO users VALUES ('ana', '+573001112233')"))
    contacts = SqlUserContacts(async_sessionmaker(engine))
    assert await contacts.phone_for("ana") == "+573001112233"
    assert await contacts.phone_for("nobody") is None
    await engine.dispose()


async def test_console_sms_sender_logs_instead_of_sending(caplog):
    with caplog.at_level(logging.INFO):
        await ConsoleSmsSender().send("+573001112233", "hola")
    assert "sms_simulated" in caplog.text


async def test_integrity_error_that_is_not_a_duplicate_is_raised():
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.begin.side_effect = IntegrityError("insert", {}, Exception("other constraint"))
    session.scalar = AsyncMock(return_value=None)
    repository = SqlNotificationRepository(lambda: session)
    notification = Notification(uuid4(), uuid4(), "ana", "msg", datetime.now(UTC))
    with pytest.raises(IntegrityError):
        await repository.save_once(notification)


async def test_consume_reconnects_after_failure_and_processes_messages(monkeypatch):
    message = object()

    class Messages:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if getattr(self, "done", False):
                raise Stop()
            self.done = True
            return message

    queue = MagicMock()
    queue.iterator.return_value = Messages()
    connection = MagicMock()
    connection.__aenter__ = AsyncMock(return_value=connection)
    connection.__aexit__ = AsyncMock(return_value=False)
    connection.channel = AsyncMock()
    monkeypatch.setattr(
        consumer.aio_pika, "connect_robust", AsyncMock(side_effect=[ConnectionError(), connection])
    )
    monkeypatch.setattr(consumer, "declare_topology", AsyncMock(return_value=(None, queue)))
    sleep = AsyncMock()
    monkeypatch.setattr(consumer.asyncio, "sleep", sleep)
    process = AsyncMock()
    monkeypatch.setattr(consumer, "process_message", process)

    with pytest.raises(Stop):
        await consumer.consume("amqp://test/", "function")

    sleep.assert_awaited_once_with(5)
    process.assert_awaited_once_with(message, "function")


async def test_worker_wires_user_contacts_when_configured(monkeypatch):
    monkeypatch.setenv("USER_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    consume = AsyncMock()
    monkeypatch.setattr(main, "consume", consume)
    await main.run()
    function = consume.call_args.args[1]
    assert isinstance(function.contacts, SqlUserContacts)
    assert isinstance(function.sms_sender, ConsoleSmsSender)


async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://t") as client:
        assert (await client.get("/health")).json() == {"status": "ok"}
