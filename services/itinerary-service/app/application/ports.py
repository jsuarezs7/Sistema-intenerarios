from collections.abc import Mapping
from typing import Protocol


class EventPublisher(Protocol):
    """Application port for publishing integration events."""

    async def publish(
        self,
        payload: bytes,
        *,
        event_id: str,
        event_type: str,
        headers: Mapping[str, str],
    ) -> None: ...
