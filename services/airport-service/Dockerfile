FROM python:3.12-slim AS builder
WORKDIR /build
COPY shared /shared
COPY services/airport-service/requirements.txt .
RUN python -m venv /venv && /venv/bin/pip install --no-cache-dir /shared -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /service
COPY --from=builder /venv /venv
COPY services/airport-service/ .
RUN useradd --create-home appuser
USER appuser
ENV PATH="/venv/bin:$PATH"
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
