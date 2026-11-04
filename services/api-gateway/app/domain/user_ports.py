from typing import Protocol

from app.domain.users import User


class UserRepositoryPort(Protocol):
    async def get_by_username(self, username: str) -> User | None: ...

    async def create(self, user: User) -> None: ...
