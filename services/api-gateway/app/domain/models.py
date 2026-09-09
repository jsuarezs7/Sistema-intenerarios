from dataclasses import dataclass


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str


class InvalidCredentials(Exception):
    pass


class UpstreamUnavailable(Exception):
    pass
