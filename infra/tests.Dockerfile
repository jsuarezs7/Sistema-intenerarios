# Imagen para ejecutar pytest + cobertura sin instalar Python en el equipo.
# La usa scripts/quality.ps1 cuando no encuentra Python (o con -Docker).
FROM python:3.12-slim
WORKDIR /deps
COPY shared /deps/shared
COPY requirements-dev.txt /deps/
COPY services/airport-service/requirements.txt /deps/airport-service.txt
COPY services/itinerary-service/requirements.txt /deps/itinerary-service.txt
COPY services/api-gateway/requirements.txt /deps/api-gateway.txt
COPY services/notification-function/requirements.txt /deps/notification-function.txt
COPY services/report-function/requirements.txt /deps/report-function.txt
RUN pip install --no-cache-dir /deps/shared -r requirements-dev.txt \
    -r airport-service.txt -r itinerary-service.txt -r api-gateway.txt \
    -r notification-function.txt -r report-function.txt
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /src
