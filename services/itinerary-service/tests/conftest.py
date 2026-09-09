import os

os.environ["JWT_SECRET"] = "test-signing-key-only-for-tests-123456789"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["NOTIFICATION_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["RABBITMQ_URL"] = "amqp://localhost/"
os.environ["DEMO_USERNAME"] = "student"
os.environ["DEMO_PASSWORD"] = "test-password-only"
os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)

import pytest
from itinerary_shared.auth import TokenService


@pytest.fixture
def token():
    return TokenService(os.environ["JWT_SECRET"]).issue("student")


@pytest.fixture
def headers(token):
    return {"Authorization": "Bearer " + token}
