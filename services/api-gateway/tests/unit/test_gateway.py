import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
from app.application.service import GatewayService
from app.domain.models import InvalidCredentials
from app.infrastructure.adapters import DemoIdentityAdapter, RedisRateLimiter
from itinerary_shared.auth import TokenService


def test_login():
    tokens = TokenService(os.environ["JWT_SECRET"])
    service = GatewayService(DemoIdentityAdapter("student", "test-password-only", tokens), Mock())
    assert tokens.verify(service.login("student", "test-password-only")) == "student"
    with pytest.raises(InvalidCredentials):
        service.login("student", "wrong")


def test_expired_wrong_audience_and_unsigned_tokens_rejected():
    tokens = TokenService(os.environ["JWT_SECRET"])
    payload = {
        "sub": "student",
        "iss": tokens.issuer,
        "aud": tokens.audience,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) - timedelta(seconds=1),
    }
    with pytest.raises(jwt.ExpiredSignatureError):
        tokens.verify(jwt.encode(payload, tokens.secret, algorithm="HS256"))
    payload["exp"] = datetime.now(UTC) + timedelta(minutes=1)
    payload["aud"] = "wrong"
    with pytest.raises(jwt.InvalidAudienceError):
        tokens.verify(jwt.encode(payload, tokens.secret, algorithm="HS256"))
    with pytest.raises(jwt.InvalidTokenError):
        tokens.verify(jwt.encode(payload, key="", algorithm="none"))


async def test_shared_rate_limit_is_atomic_and_separates_login():
    redis = AsyncMock()
    redis.eval.side_effect = [1, 3, 6]
    limiter = RedisRateLimiter(redis, limit=5, login_limit=2)
    assert await limiter.allow("127.0.0.1", False)
    assert not await limiter.allow("127.0.0.1", True)
    assert not await limiter.allow("127.0.0.1", False)
    assert "EXPIRE" in redis.eval.call_args.args[0]
