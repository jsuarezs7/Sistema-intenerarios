FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /service
COPY shared /shared
COPY services/notification-function/requirements.txt .
RUN pip install --no-cache-dir /shared -r requirements.txt
COPY services/notification-function/ .
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["python", "-m", "app.main"]

