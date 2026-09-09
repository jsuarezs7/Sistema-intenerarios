from unittest.mock import AsyncMock

import pytest
from app.application.service import GenerateItineraryReportFunction


@pytest.mark.parametrize(
    "items,total,days,average",
    [
        ([], 0, 0, 0),
        (
            [
                {"departure_airport_id": 1, "arrival_airport_id": 2, "duration_days": 3},
                {"departure_airport_id": 1, "arrival_airport_id": 2, "duration_days": 4},
            ],
            2,
            7,
            3.5,
        ),
    ],
)
async def test_report_metrics(items, total, days, average):
    reader = AsyncMock()
    reader.list_all.return_value = items
    report = await GenerateItineraryReportFunction(reader).generate("token")
    assert (report.total_itineraries, report.total_duration_days, report.average_duration_days) == (
        total,
        days,
        average,
    )
    reader.list_all.assert_awaited_once_with("token")
    if items:
        assert report.routes["1 → 2"] == 2
