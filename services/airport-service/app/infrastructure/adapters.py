import json
from dataclasses import asdict
from uuid import uuid4

import httpx
from circuitbreaker import CircuitBreaker, CircuitBreakerError
from redis.asyncio import Redis
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from app.domain.models import Airport, AirportUnavailable


def transient(exc: BaseException) -> bool:
    return isinstance(exc, httpx.TransportError) or (
        isinstance(exc, httpx.HTTPStatusError)
        and (exc.response.status_code >= 500 or exc.response.status_code == 429)
    )


class AirportColombiaAdapter:
    def __init__(
        self,
        client: httpx.AsyncClient,
        url: str,
        attempts: int = 3,
        backoff: float = 0.5,
        failure_threshold: int = 3,
        recovery_timeout: int = 30,
    ):
        self.client, self.url = client, url
        self.attempts, self.backoff = attempts, backoff
        self.breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=Exception,
            name=f"api-colombia-{uuid4()}",
        )
        self._protected_fetch = self.breaker(self._fetch)

    async def _fetch(self) -> list[Airport]:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.attempts),
            wait=wait_exponential(multiplier=self.backoff, max=4),
            retry=retry_if_exception(transient),
            reraise=True,
        ):
            with attempt:
                response = await self.client.get(self.url)
                response.raise_for_status()
                raw = response.json()
                if not isinstance(raw, list) or not raw:
                    raise ValueError("Invalid airport collection")
                return [self.translate(item) for item in raw]
        raise RuntimeError("Retry loop exhausted")

    @staticmethod
    def translate(raw: dict) -> Airport:
        city = raw.get("city") or {}

        def coordinate(key: str, bound: float) -> float | None:
            try:
                value = float(raw.get(key))
                return value if -bound <= value <= bound else None
            except (TypeError, ValueError):
                return None

        latitude = coordinate("latitude", 90)
        longitude = coordinate("longitude", 180)
        # API Colombia has records with swapped axes. Only swap an unambiguous
        # Colombian longitude/latitude pair; preserve correctly oriented records.
        if latitude is not None and longitude is not None:
            if -82 <= latitude <= -66 and -5 <= longitude <= 14:
                latitude, longitude = longitude, latitude
        iata = raw.get("iataCode")
        return Airport(
            id=int(raw["id"]),
            name=str(raw["name"]),
            city=city.get("name", "") if isinstance(city, dict) else str(city),
            iata_code=iata if iata and iata != "N/A" else None,
            latitude=latitude,
            longitude=longitude,
        )

    async def list_airports(self) -> list[Airport]:
        try:
            return await self._protected_fetch()
        except (httpx.HTTPError, CircuitBreakerError, ValueError, KeyError, TypeError) as exc:
            raise AirportUnavailable("Airport provider temporarily unavailable") from exc


class RedisCacheAdapter:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def get(self, key: str) -> list[Airport] | None:
        raw = await self.redis.get(key)
        return [Airport(**item) for item in json.loads(raw)] if raw is not None else None

    async def set(self, key: str, airports: list[Airport], ttl: int) -> None:
        await self.redis.set(key, json.dumps([asdict(item) for item in airports]), ex=ttl)
