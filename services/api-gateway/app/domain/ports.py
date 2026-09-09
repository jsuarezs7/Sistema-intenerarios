from typing import Protocol

from app.domain.models import Credentials


class IdentityPort(Protocol):
    def authenticate(self, credentials: Credentials) -> str: ...


class GatewayPort(Protocol):
    async def forward(
        self, method: str, path: str, token: str, body: bytes, query: str
    ) -> tuple[int, bytes, str]: ...
