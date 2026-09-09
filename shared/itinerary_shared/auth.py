from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: str
    token: str


class TokenService:
    def __init__(
        self,
        secret: str,
        issuer: str = "itinerary-gateway",
        audience: str = "itinerary-services",
        lifetime_minutes: int = 60,
    ):
        if len(secret) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        self.secret, self.issuer, self.audience = secret, issuer, audience
        self.lifetime_minutes = lifetime_minutes

    def issue(self, user_id: str) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": user_id,
                "iss": self.issuer,
                "aud": self.audience,
                "iat": now,
                "exp": now + timedelta(minutes=self.lifetime_minutes),
            },
            self.secret,
            algorithm="HS256",
        )

    def verify(self, token: str) -> str:
        payload = jwt.decode(
            token,
            self.secret,
            algorithms=["HS256"],
            issuer=self.issuer,
            audience=self.audience,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
        if not isinstance(payload["sub"], str) or not payload["sub"]:
            raise jwt.InvalidTokenError("Missing subject")
        return payload["sub"]

    def dependency(self):
        async def authenticate(
            credentials: HTTPAuthorizationCredentials | None = Depends(security),
        ) -> Principal:
            try:
                if credentials is None:
                    raise jwt.InvalidTokenError("Missing bearer token")
                return Principal(self.verify(credentials.credentials), credentials.credentials)
            except jwt.InvalidTokenError as exc:
                raise HTTPException(
                    401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
                ) from exc

        return authenticate
