# Imagen única para el plan gratuito de Render: los cinco servicios en un contenedor.
# Contexto de compilación: raíz del repositorio.
FROM python:3.12-slim AS builder
WORKDIR /build
COPY shared /shared
COPY services/airport-service/requirements.txt airport.txt
COPY services/api-gateway/requirements.txt gateway.txt
COPY services/itinerary-service/requirements.txt itinerary.txt
COPY services/notification-function/requirements.txt notification.txt
COPY services/report-function/requirements.txt report.txt
RUN python -m venv /venv && /venv/bin/pip install --no-cache-dir /shared \
    -r airport.txt -r gateway.txt -r itinerary.txt -r notification.txt -r report.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FRONTEND_DIR=/frontend
WORKDIR /srv
COPY --from=builder /venv /venv
COPY services /srv/services
COPY frontend /frontend
COPY deploy/render-free/launcher.py /srv/launcher.py
RUN python -m compileall -q /srv && useradd --create-home appuser
USER appuser
ENV PATH="/venv/bin:$PATH"
EXPOSE 8000
CMD ["python", "/srv/launcher.py"]
