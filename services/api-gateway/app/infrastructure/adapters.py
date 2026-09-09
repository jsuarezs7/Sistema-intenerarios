import hashlib
import hmac

import httpx
from itinerary_shared.auth import TokenService
from itinerary_shared.observability import correlation_id
from itinerary_shared.urls import internal_url

from app.domain.models import Credentials, InvalidCredentials, UpstreamUnavailable


class DemoIdentityAdapter:
    def __init__(self, username: str, password: str, tokens: TokenService):
        self.username, self.password, self.tokens = username, password, tokens

    def authenticate(self, credentials: Credentials) -> str:
        username_ok = hmac.compare_digest(credentials.username.encode(), self.username.encode())
        password_ok = hmac.compare_digest(credentials.password.encode(), self.password.encode())
        if not (username_ok and password_ok):
            raise InvalidCredentials()
        return self.tokens.issue(self.username)


class HttpGatewayAdapter:
    def __init__(
        self, client: httpx.AsyncClient, airport_url: str, itinerary_url: str, report_url: str
    ):
        self.client = client
        self.urls = {"airports": airport_url, "itineraries": itinerary_url, "reports": report_url}

    async def forward(
        self, method: str, path: str, token: str, body: bytes, query: str
    ) -> tuple[int, bytes, str]:
        root = path.strip("/").split("/")[0]
        base = internal_url(self.urls[root])
        try:
            response = await self.client.request(
                method,
                f"{base}{path}" + (f"?{query}" if query else ""),
                content=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-Correlation-ID": correlation_id.get(),
                },
            )
            return (
                response.status_code,
                response.content,
                response.headers.get("content-type", "application/json"),
            )
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable() from exc


class RedisRateLimiter:
    """Atomic fixed windows shared by gateway replicas; fail closed in API middleware."""

    SCRIPT = """
    local count = redis.call('INCR', KEYS[1])
    if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
    return count
    """

    def __init__(self, redis, limit: int, login_limit: int):
        self.redis, self.limit, self.login_limit = redis, limit, login_limit

    async def allow(self, address: str, login: bool) -> bool:
        digest = hashlib.sha256(address.encode()).hexdigest()
        key = f"gateway:rate:{'login' if login else 'api'}:{digest}"
        count = await self.redis.eval(self.SCRIPT, 1, key, 60)
        return count <= (self.login_limit if login else self.limit)
