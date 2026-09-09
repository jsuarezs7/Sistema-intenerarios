import aio_pika

EXCHANGE = "itinerary.events"
ROUTING_KEY = "itinerary.created.v1"
QUEUE = "notifications.itinerary-created.v1"
DEAD_QUEUE = "notifications.dead"


async def declare_topology(channel):
    exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
    dead = await channel.declare_exchange(
        "itinerary.dead", aio_pika.ExchangeType.DIRECT, durable=True
    )
    dead_queue = await channel.declare_queue(DEAD_QUEUE, durable=True)
    await dead_queue.bind(dead, routing_key="notification.failed")
    queue = await channel.declare_queue(
        QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "itinerary.dead",
            "x-dead-letter-routing-key": "notification.failed",
        },
    )
    await queue.bind(exchange, routing_key=ROUTING_KEY)
    return exchange, queue
