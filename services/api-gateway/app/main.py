from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itinerary_shared.auth import TokenService
from itinerary_shared.database import async_database_url
from itinerary_shared.observability import configure
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import router
from app.application.service import GatewayService
from app.domain.models import InvalidCredentials, UpstreamUnavailable, UserAlreadyExists
from app.infrastructure.adapters import DemoIdentityAdapter, HttpGatewayAdapter, RedisRateLimiter
from app.infrastructure.settings import Settings
from app.infrastructure.users import SqlUserRepository


def create_app(service=None, limiter=None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    tokens = TokenService(settings.jwt_secret)

    @asynccontextmanager
    async def lifespan(app):
        if service is not None and limiter is not None:
            yield
            return
        redis = Redis.from_url(settings.redis_url, socket_timeout=2, socket_connect_timeout=2)
        engine = create_async_engine(async_database_url(settings.database_url), pool_pre_ping=True)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with httpx.AsyncClient(timeout=60) as client:
            app.state.service = service or GatewayService(
                DemoIdentityAdapter(settings.demo_username, settings.demo_password, tokens),
                HttpGatewayAdapter(
                    client,
                    settings.airport_service_url,
                    settings.itinerary_service_url,
                    settings.report_service_url,
                ),
                SqlUserRepository(sessions),
            )
            app.state.limiter = limiter or RedisRateLimiter(
                redis,
                settings.rate_limit,
                settings.login_rate_limit,
            )
            try:
                yield
            finally:
                await redis.aclose()
                await engine.dispose()

    app = FastAPI(title="Sistema de Itinerarios · Gateway", version="1.0.0", lifespan=lifespan)
    app.state.service, app.state.limiter = service, limiter
    configure("api-gateway", app)

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            try:
                # Do not trust arbitrary X-Forwarded-For headers.
                address = request.client.host if request.client else "unknown"
                allowed = await request.app.state.limiter.allow(
                    address,
                    request.url.path == "/api/auth/login",
                )
            except Exception:
                return JSONResponse(status_code=503, content={"detail": "Rate limiter unavailable"})
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": "60"},
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(router(tokens.dependency()), prefix="/api")
    frontend = Path(settings.frontend_dir).resolve()
    required_assets = ("index.html", "styles.css", "app.js")
    missing_assets = [name for name in required_assets if not (frontend / name).is_file()]
    if missing_assets:
        raise RuntimeError(
            f"Frontend files missing in {frontend}: {', '.join(missing_assets)}. "
            "Check FRONTEND_DIR and the gateway Docker build context."
        )
    app.mount("/static", StaticFiles(directory=frontend), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(frontend / "index.html")

    @app.get("/health", tags=["Operations"])
    async def health():
        return {"status": "ok"}

    @app.exception_handler(InvalidCredentials)
    async def unauthorized(request: Request, exc):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(UpstreamUnavailable)
    async def unavailable(request: Request, exc):
        return JSONResponse(status_code=503, content={"detail": "Upstream service unavailable"})

    @app.exception_handler(UserAlreadyExists)
    async def conflict(request: Request, exc):
        return JSONResponse(
            status_code=409, content={"detail": "Username or email is already registered"}
        )

    return app


app = create_app()
