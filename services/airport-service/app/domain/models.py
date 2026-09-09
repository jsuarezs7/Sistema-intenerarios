from dataclasses import dataclass


@dataclass(frozen=True)
class Airport:
    id: int
    name: str
    city: str
    iata_code: str | None
    latitude: float | None
    longitude: float | None


class AirportUnavailable(Exception):
    pass


class AirportNotFound(Exception):
    pass
