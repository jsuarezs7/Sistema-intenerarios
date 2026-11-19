from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    username: str
    name: str
    email: str
    phone: str
    password_hash: str
