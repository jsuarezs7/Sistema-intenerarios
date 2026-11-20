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


class SqlUserRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def get_by_username(self, username: str) -> User | None:
        async with self.sessions() as session:
            row = await session.scalar(select(UserRow).where(UserRow.username == username))
            return (
                None
                if row is None
                else User(row.username, row.name, row.email, row.phone, row.password_hash)
            )

    async def create(self, user: User) -> None:
        try:
            async with self.sessions() as session, session.begin():
                session.add(UserRow(**user.__dict__))
                await session.flush()
        except IntegrityError as exc:
            raise ValueError("Username or email is already registered") from exc
