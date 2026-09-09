FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /service
COPY shared /shared
COPY services/api-gateway/requirements.txt .
RUN pip install --no-cache-dir /shared -r requirements.txt
COPY services/api-gateway/ .
COPY frontend /frontend
ENV FRONTEND_DIR=/frontend
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

