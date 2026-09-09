from collections import Counter

from app.domain.models import ItineraryReport
from app.domain.ports import ItineraryReaderPort


class GenerateItineraryReportFunction:
    def __init__(self, reader: ItineraryReaderPort):
        self.reader = reader

    async def generate(self, token: str) -> ItineraryReport:
        itineraries = await self.reader.list_all(token)
        total = len(itineraries)
        days = sum(item["duration_days"] for item in itineraries)
        routes = Counter(
            f"{item['departure_airport_id']} → {item['arrival_airport_id']}" for item in itineraries
        )
        return ItineraryReport(total, days, round(days / total, 2) if total else 0.0, dict(routes))
