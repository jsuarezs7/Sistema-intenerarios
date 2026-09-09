from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from itinerary_shared.auth import TokenService
from itinerary_shared.observability import configure
from redis.asyncio import Redis

from app.api.routes import router
from app.application.service import AirportService
from app.domain.models import AirportNotFound, AirportUnavailable
from app.infrastructure.adapters import AirportColombiaAdapter, RedisCacheAdapter
from app.infrastructure.settings import Settings


def create_app(service=None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        if service is not None:
            yield
            return
        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            app.state.service = AirportService(
                AirportColombiaAdapter(client, settings.airport_api_url),
                RedisCacheAdapter(redis),
                settings.cache_ttl,
                settings.stale_cache_ttl,
            )
            try:
                yield
            finally:
                await redis.aclose()

    app = FastAPI(title="Airport Service", version="1.0.0", lifespan=lifespan)
    app.state.service = service
    configure("airport-service", app)
    app.include_router(router(TokenService(settings.jwt_secret).dependency()))

    @app.get("/health", tags=["Operations"])
    async def health():
        return {"status": "ok"}

    @app.exception_handler(AirportUnavailable)
    async def unavailable(request: Request, exc):
        return JSONResponse(status_code=503, content={"detail": "Airport provider unavailable"})

    @app.exception_handler(AirportNotFound)
    async def missing(request: Request, exc):
        return JSONResponse(status_code=404, content={"detail": "Airport not found"})

    return app


app = create_app()
