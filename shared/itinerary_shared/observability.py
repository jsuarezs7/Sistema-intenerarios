import logging
import os
import re
from contextvars import ContextVar
from uuid import uuid4

from fastapi import FastAPI, Request
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pythonjsonlogger.json import JsonFormatter

correlation_id = ContextVar("correlation_id", default="")


class TraceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = trace.get_current_span().get_span_context()
        record.trace_id = format(context.trace_id, "032x")
        record.span_id = format(context.span_id, "016x")
        record.correlation_id = correlation_id.get()
        return True


def configure(service_name: str, app: FastAPI | None = None) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(span_id)s %(correlation_id)s"
        )
    )
    handler.addFilter(TraceFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    # HTTP access logs may contain query strings; application logs never contain tokens.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint and not isinstance(trace.get_tracer_provider(), TracerProvider):
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces", timeout=5)
            )
        )
        trace.set_tracer_provider(provider)
        HTTPXClientInstrumentor().instrument()
    if app:
        FastAPIInstrumentor.instrument_app(app, excluded_urls="health")

        @app.middleware("http")
        async def correlate(request: Request, call_next):
            supplied = request.headers.get("X-Correlation-ID", "")
            value = supplied if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", supplied) else str(uuid4())
            reset = correlation_id.set(value)
            try:
                response = await call_next(request)
                response.headers["X-Correlation-ID"] = value
                return response
            finally:
                correlation_id.reset(reset)
