from sqlalchemy import String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.users import User


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        expected = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1
        )
        return hmac.compare_digest(expected.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


class SqlUserRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def get_by_username(self, username: str) -> User | None:
        async with self.sessions() as session:
            row = await session.scalar(select(UserRow).where(UserRow.username == username))
            return None if row is None else User(
                row.username, row.name, row.email, row.phone, row.password_hash
            )

    async def create(self, user: User) -> None:
        try:
            async with self.sessions() as session, session.begin():
                session.add(UserRow(**user.__dict__))
                await session.flush()
        except IntegrityError as exc:
            raise ValueError("Username or email is already registered") from exc


class ConsoleSmsSender:
    """Adapter: local SMS implementation that logs instead of calling a provider."""

    async def send(self, phone: str, message: str) -> None:
        import logging

        logging.getLogger(__name__).info(
            "sms_simulated", extra={"phone": phone, "sms_message": message}
        )
