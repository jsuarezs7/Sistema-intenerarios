from collections.abc import Mapping

import aio_pika

from app.application.ports import EventPublisher


class RabbitMQEventPublisher(EventPublisher):
    """Adapter: infrastructure implementation of the application EventPublisher port."""

    def __init__(self, exchange, routing_key: str):
        self.exchange = exchange
        self.routing_key = routing_key

    async def publish(
        self,
        payload: bytes,
        *,
        event_id: str,
        event_type: str,
        headers: Mapping[str, str],
    ) -> None:
        await self.exchange.publish(
            aio_pika.Message(
                body=payload,
                content_type="application/json",
                message_id=event_id,
                type=event_type,
                headers=dict(headers),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=self.routing_key,
            mandatory=True,
            timeout=10,
        )
