import asyncio
import logging

import aio_pika
from itinerary_shared.broker import declare_topology
from itinerary_shared.events import ItineraryCreatedEvent
from itinerary_shared.observability import correlation_id
from opentelemetry import trace
from opentelemetry.propagate import extract
from pydantic import ValidationError

logger = logging.getLogger(__name__)


async def process_message(message, function) -> None:
    try:
        event = ItineraryCreatedEvent.model_validate_json(message.body)
    except (ValidationError, ValueError):
        logger.warning("invalid_event_dead_lettered")
        await message.reject(requeue=False)
        return
    headers = message.headers or {}
    reset = correlation_id.set(str(headers.get("correlation_id", ""))[:64])
    try:
        with trace.get_tracer(__name__).start_as_current_span(
            "notification.consume",
            context=extract(headers),
            kind=trace.SpanKind.CONSUMER,
        ):
            try:
                inserted = await function.handle(event.event_id, event.itinerary_id, event.user_id)
            except Exception:
                logger.warning("notification_storage_unavailable")
                await asyncio.sleep(2)
                await message.nack(requeue=True)
                return
            logger.info(
                "notification_simulated" if inserted else "duplicate_event_ignored",
                extra={"event_id": str(event.event_id)},
            )
            # Commit is complete before acknowledgment.
            await message.ack()
    finally:
        correlation_id.reset(reset)


async def consume(url: str, function) -> None:
    while True:
        try:
            connection = await aio_pika.connect_robust(url)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=10)
                _, queue = await declare_topology(channel)
                async with queue.iterator() as messages:
                    async for message in messages:
                        await process_message(message, function)
        except Exception:
            logger.warning("notification_broker_reconnecting")
            await asyncio.sleep(5)
