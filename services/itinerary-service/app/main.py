from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from itinerary_shared.auth import TokenService
from itinerary_shared.database import async_database_url
from itinerary_shared.observability import configure
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import router
from app.application.service import ItineraryService
from app.domain.models import AirportUnavailable, BusinessRuleError, ItineraryNotFound
from app.infrastructure.adapters import AirportHttpClient, EventEncoder
from app.infrastructure.database import SqlUnitOfWork
from app.infrastructure.settings import Settings


def create_app(service=None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        if service is not None:
            yield
            return
        engine = create_async_engine(async_database_url(settings.database_url), pool_pre_ping=True)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with httpx.AsyncClient(timeout=30) as client:
            app.state.service = ItineraryService(
                lambda: SqlUnitOfWork(sessions),
                AirportHttpClient(client, settings.airport_service_url),
                EventEncoder(),
            )
            try:
                yield
            finally:
                await engine.dispose()

    app = FastAPI(title="Itinerary Service", version="1.0.0", lifespan=lifespan)
    app.state.service = service
    configure("itinerary-service", app)
    app.include_router(router(TokenService(settings.jwt_secret).dependency()))

    @app.get("/health", tags=["Operations"])
    async def health():
        return {"status": "ok"}

    for error, status, message in [
        (BusinessRuleError, 400, None),
        (ItineraryNotFound, 404, "Itinerary not found"),
        (AirportUnavailable, 503, "Airport validation unavailable"),
        (SQLAlchemyError, 503, "Itinerary storage unavailable"),
    ]:

        def make_handler(code, detail):
            async def handler(request: Request, exc):
                return JSONResponse(status_code=code, content={"detail": detail or str(exc)})

            return handler

        app.add_exception_handler(error, make_handler(status, message))
    return app


app = create_app()
