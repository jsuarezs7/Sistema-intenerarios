from typing import Protocol


class ItineraryReaderPort(Protocol):
    async def list_all(self, token: str) -> list[dict]: ...
