import os

import pytest
from app.application.passwords import hash_password, verify_password
from app.application.service import GatewayService
from app.domain.models import InvalidCredentials, UserAlreadyExists
from app.domain.users import User
from app.infrastructure.adapters import DemoIdentityAdapter
from app.infrastructure.users import Base, SqlUserRepository
from itinerary_shared.auth import TokenService
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def repository():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield SqlUserRepository(async_sessionmaker(engine, expire_on_commit=False))
    await engine.dispose()


def test_password_hash_roundtrip_and_rejections():
    encoded = hash_password("correct horse battery")
    assert encoded.startswith("scrypt$")
    assert verify_password("correct horse battery", encoded)
    assert not verify_password("wrong", encoded)
    assert not verify_password("x", "bcrypt$00$00")
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("x", "scrypt$zz$00")


async def test_sql_user_repository_create_get_and_duplicate(repository):
    user = User("ana", "Ana", "ana@example.com", "+573001112233", "hash")
    assert await repository.get_by_username("ana") is None
    await repository.create(user)
    assert await repository.get_by_username("ana") == user
    with pytest.raises(ValueError):
        await repository.create(user)


async def test_service_register_and_login_with_registered_users(repository):
    tokens = TokenService(os.environ["JWT_SECRET"])
    service = GatewayService(
        DemoIdentityAdapter("student", "test-password-only", tokens), None, repository
    )
    token = await service.register(
        "ana", "Ana", "ana@example.com", "+573001112233", "long-password-1"
    )
    assert tokens.verify(token) == "ana"
    assert tokens.verify(await service.login("ana", "long-password-1")) == "ana"
    with pytest.raises(InvalidCredentials):
        await service.login("ana", "bad-password")
    # Unknown users fall back to the demo identity.
    assert tokens.verify(await service.login("student", "test-password-only")) == "student"
    with pytest.raises(UserAlreadyExists):
        await service.register("ana", "Ana", "ana@example.com", "+573001112233", "long-password-1")


async def test_register_without_repository_is_not_configured():
    service = GatewayService(None, None)
    with pytest.raises(RuntimeError):
        await service.register("ana", "Ana", "ana@example.com", "+573001112233", "long-password-1")
