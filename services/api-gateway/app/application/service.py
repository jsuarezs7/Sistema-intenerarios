from app.domain.models import Credentials
from app.domain.ports import GatewayPort, IdentityPort


class GatewayService:
    def __init__(self, identity: IdentityPort, upstream: GatewayPort):
        self.identity = identity
        self.upstream = upstream

    def login(self, username: str, password: str) -> str:
        return self.identity.authenticate(Credentials(username, password))

    async def forward(
        self, method: str, path: str, token: str, body: bytes = b"", query: str = ""
    ) -> tuple[int, bytes, str]:
        return await self.upstream.forward(method, path, token, body, query)
