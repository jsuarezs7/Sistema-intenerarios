from typing import Protocol

from app.domain.models import Airport


class AirportRepositoryPort(Protocol):
    async def list_airports(self) -> list[Airport]: ...


class AirportExternalPort(AirportRepositoryPort, Protocol):
    pass


class CachePort(Protocol):
    async def get(self, key: str) -> list[Airport] | None: ...
    async def set(self, key: str, airports: list[Airport], ttl: int) -> None: ...
