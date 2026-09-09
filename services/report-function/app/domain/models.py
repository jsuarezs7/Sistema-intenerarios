from dataclasses import dataclass


@dataclass(frozen=True)
class ItineraryReport:
    total_itineraries: int
    total_duration_days: int
    average_duration_days: float
    routes: dict[str, int]


class ItineraryUnavailable(Exception):
    pass
