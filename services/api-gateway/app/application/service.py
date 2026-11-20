from app.application.passwords import hash_password, verify_password
from app.domain.models import Credentials, InvalidCredentials, UserAlreadyExists
from app.domain.ports import GatewayPort, IdentityPort
from app.domain.user_ports import UserRepositoryPort


class GatewayService:
    def __init__(
        self,
        identity: IdentityPort,
        upstream: GatewayPort,
        users: UserRepositoryPort | None = None,
    ):
        self.identity = identity
        self.upstream = upstream
        self.users = users

    def login(self, username: str, password: str) -> str:
        if self.users is None:
            return self.identity.authenticate(Credentials(username, password))
        return self._login_registered(username, password)

    async def _login_registered(self, username: str, password: str) -> str:
        user = await self.users.get_by_username(username)
        if user is None:
            return self.identity.authenticate(Credentials(username, password))
        if not verify_password(password, user.password_hash):
            raise InvalidCredentials()
        return self.identity.tokens.issue(user.username)

    async def register(
        self, username: str, name: str, email: str, phone: str, password: str
    ) -> str:
        from app.domain.users import User

        if self.users is None:
            raise RuntimeError("User registration is not configured")
        try:
            await self.users.create(User(username, name, email, phone, hash_password(password)))
        except ValueError as exc:
            raise UserAlreadyExists() from exc
        return self.identity.tokens.issue(username)

    async def forward(
        self, method: str, path: str, token: str, body: bytes = b"", query: str = ""
    ) -> tuple[int, bytes, str]:
        return await self.upstream.forward(method, path, token, body, query)
