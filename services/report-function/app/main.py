from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from itinerary_shared.auth import TokenService
from itinerary_shared.observability import configure

from app.api.routes import router
from app.application.service import GenerateItineraryReportFunction
from app.domain.models import ItineraryUnavailable
from app.infrastructure.adapters import HttpItineraryReader
from app.infrastructure.settings import Settings


def create_app(service=None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        if service is not None:
            yield
            return
        async with httpx.AsyncClient(timeout=15) as client:
            app.state.service = GenerateItineraryReportFunction(
                HttpItineraryReader(client, settings.itinerary_service_url)
            )
            yield

    app = FastAPI(title="Generate Itinerary Report Function", version="1.0.0", lifespan=lifespan)
    app.state.service = service
    configure("report-function", app)
    app.include_router(router(TokenService(settings.jwt_secret).dependency()))

    @app.get("/health", tags=["Operations"])
    async def health():
        return {"status": "ok"}

    @app.exception_handler(ItineraryUnavailable)
    async def unavailable(request: Request, exc):
        return JSONResponse(status_code=503, content={"detail": "Report source unavailable"})

    return app


app = create_app()
