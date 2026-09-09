import asyncio
import json
import logging
from datetime import UTC, datetime

import aio_pika
from itinerary_shared.broker import ROUTING_KEY, declare_topology
from itinerary_shared.database import async_database_url
from itinerary_shared.observability import configure, correlation_id
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.database import OutboxRow
from app.infrastructure.settings import Settings

logger = logging.getLogger(__name__)


async def publish_batch(sessions, exchange, batch_size: int = 50) -> int:
    count = 0
    async with sessions() as session, session.begin():
        rows = await session.scalars(
            select(OutboxRow)
            .where(OutboxRow.published_at.is_(None))
            .order_by(OutboxRow.created_at, OutboxRow.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        for row in rows:
            reset = correlation_id.set(row.trace_context.get("correlation_id", ""))
            try:
                with trace.get_tracer(__name__).start_as_current_span(
                    "outbox.publish",
                    context=extract(row.trace_context),
                    kind=trace.SpanKind.PRODUCER,
                ):
                    headers = {"correlation_id": correlation_id.get()}
                    inject(headers)
                    # Confirms precede the marker. Crash => redelivery, never silent loss.
                    await exchange.publish(
                        aio_pika.Message(
                            body=json.dumps(row.payload).encode(),
                            content_type="application/json",
                            message_id=str(row.id),
                            type="ItineraryCreatedEvent",
                            headers=headers,
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        ),
                        routing_key=ROUTING_KEY,
                        mandatory=True,
                        timeout=10,
                    )
                    row.published_at = datetime.now(UTC)
                    count += 1
                    logger.info("outbox_event_published", extra={"event_id": str(row.id)})
            finally:
                correlation_id.reset(reset)
    return count


async def run() -> None:
    settings = Settings()
    configure("itinerary-outbox")
    engine = create_async_engine(async_database_url(settings.database_url), pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        while True:
            try:
                connection = await aio_pika.connect_robust(settings.rabbitmq_url)
                async with connection:
                    channel = await connection.channel(
                        publisher_confirms=True, on_return_raises=True
                    )
                    exchange, _ = await declare_topology(channel)
                    while True:
                        await publish_batch(sessions, exchange)
                        await asyncio.sleep(settings.outbox_poll_seconds)
            except Exception:
                logger.warning("outbox_retry_after_failure")
                await asyncio.sleep(5)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
