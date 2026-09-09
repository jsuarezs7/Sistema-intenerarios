import logging

from app.domain.models import Airport, AirportNotFound, AirportUnavailable
from app.domain.ports import AirportExternalPort, CachePort

logger = logging.getLogger(__name__)


class AirportService:
    def __init__(
        self,
        external: AirportExternalPort,
        cache: CachePort,
        ttl: int = 3600,
        stale_ttl: int = 86400,
    ):
        self.external = external
        self.cache = cache
        self.ttl = ttl
        self.stale_ttl = stale_ttl

    async def _cached(self, key: str) -> list[Airport] | None:
        try:
            return await self.cache.get(key)
        except Exception:
            logger.warning("airport_cache_read_failed")
            return None

    async def list_airports(self) -> list[Airport]:
        cached = await self._cached("airports:fresh")
        if cached is not None:
            return cached
        try:
            airports = await self.external.list_airports()
        except AirportUnavailable:
            stale = await self._cached("airports:stale")
            if stale is not None:
                logger.warning("airport_stale_fallback")
                return stale
            raise
        try:
            await self.cache.set("airports:stale", airports, self.stale_ttl)
            await self.cache.set("airports:fresh", airports, self.ttl)
        except Exception:
            logger.warning("airport_cache_write_failed")
        return airports

    async def get(self, airport_id: int) -> Airport:
        for airport in await self.list_airports():
            if airport.id == airport_id:
                return airport
        raise AirportNotFound(airport_id)
