"""Run every service in one container (Render's free plan only offers web services).

The heavy libraries are imported once and each service runs in a forked process, so they
share that memory and fit in 512 MB. Each service keeps its own `app` package, process and
HTTP/AMQP boundaries; only the gateway listens on a public address.
"""

import asyncio
import gc
import importlib
import logging
import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(os.getenv("SERVICES_DIR", "/srv/services"))
PRELOAD = (
    "aio_pika",
    "alembic.command",
    "alembic.config",
    "asyncpg",
    "circuitbreaker",
    "fastapi",
    "fastapi.staticfiles",
    "httpx",
    "itinerary_shared.auth",
    "itinerary_shared.broker",
    "itinerary_shared.database",
    "itinerary_shared.events",
    "itinerary_shared.observability",
    "itinerary_shared.schemas",
    "pydantic_settings",
    "redis.asyncio",
    "sqlalchemy.dialects.postgresql.asyncpg",
    "sqlalchemy.ext.asyncio",
    "tenacity",
    "uvicorn",
)
log = logging.getLogger("launcher")
children: dict[int, str] = {}


def spawn(name: str, service: str, target) -> int:
    pid = os.fork()
    if pid:
        children[pid] = name
        return pid
    code = 1
    try:
        for number in (signal.SIGTERM, signal.SIGINT):
            signal.signal(number, signal.SIG_DFL)
        os.chdir(ROOT / service)
        sys.path.insert(0, str(ROOT / service))
        target()
        code = 0
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else 1
    except BaseException:
        log.exception("%s failed", name)
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


def http(port: int, host: str = "127.0.0.1"):
    def target():
        import uvicorn

        uvicorn.run("app.main:app", host=host, port=port)

    return target


def worker(module: str):
    return lambda: asyncio.run(importlib.import_module(module).run())


def migrate():
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")


async def ensure_database(admin_url: str, name: str) -> None:
    """Free plan allows one Postgres instance: keep notifications as a separate database in it."""
    from itinerary_shared.database import async_database_url
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(async_database_url(admin_url), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            query = text("SELECT 1 FROM pg_database WHERE datname = :name")
            if await connection.scalar(query, {"name": name}) is None:
                await connection.execute(text(f'CREATE DATABASE "{name}"'))
                log.info("database %s created", name)
    finally:
        await engine.dispose()


def prepare_environment() -> None:
    from itinerary_shared.database import async_database_url
    from sqlalchemy.engine import make_url

    main_url = os.environ["DATABASE_URL"]
    if not os.getenv("NOTIFICATION_DATABASE_URL"):
        url = make_url(async_database_url(main_url)).set(database="notifications")
        os.environ["NOTIFICATION_DATABASE_URL"] = url.render_as_string(hide_password=False)
        wait_success(
            spawn("prepare-db", "", lambda: asyncio.run(ensure_database(main_url, "notifications")))
        )
    os.environ.setdefault("USER_DATABASE_URL", main_url)
    os.environ["AIRPORT_SERVICE_URL"] = "http://127.0.0.1:8001"
    os.environ["ITINERARY_SERVICE_URL"] = "http://127.0.0.1:8002"
    os.environ["REPORT_SERVICE_URL"] = "http://127.0.0.1:8003"


def wait_success(pid: int) -> None:
    _, status = os.waitpid(pid, 0)
    name = children.pop(pid)
    if os.waitstatus_to_exitcode(status) != 0:
        raise SystemExit(f"{name} failed; see the log above")


def stop() -> None:
    for pid in children:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    started = time.monotonic()
    for module in PRELOAD:
        importlib.import_module(module)
    gc.collect()
    gc.freeze()  # Keep preloaded objects in shared (copy-on-write) pages.

    prepare_environment()
    for service in ("itinerary-service", "notification-function"):
        wait_success(spawn(f"migrate-{service}", service, migrate))

    stopping = False

    def on_signal(*_):
        nonlocal stopping
        stopping = True
        stop()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    spawn("airport-service", "airport-service", http(8001))
    spawn("itinerary-service", "itinerary-service", http(8002))
    spawn("report-function", "report-function", http(8003))
    if os.getenv("RABBITMQ_URL"):
        spawn("outbox-worker", "itinerary-service", worker("app.infrastructure.outbox_worker"))
        spawn("notification-function", "notification-function", worker("app.main"))
    else:
        log.warning("RABBITMQ_URL is empty: outbox and notifications are disabled")
    spawn("api-gateway", "api-gateway", http(int(os.getenv("PORT", "8000")), "0.0.0.0"))
    log.info("all processes launched in %.1f s", time.monotonic() - started)

    result = 0
    while children:
        pid, status = os.wait()
        name = children.pop(pid, "unknown")
        if not stopping:  # One failure restarts the whole container.
            log.error("%s exited with %s", name, os.waitstatus_to_exitcode(status))
            stopping, result = True, 1
            stop()
    return result


if __name__ == "__main__":
    sys.exit(main())
