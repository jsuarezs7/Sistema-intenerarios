"""Verify the real Compose stack, including committed outbox and notification."""

import asyncio
import subprocess
from pathlib import Path
from uuid import UUID

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENV = dotenv_values(ROOT / ".env")
COMPOSE = [
    "docker",
    "compose",
    "--env-file",
    str(ROOT / ".env"),
    "-f",
    str(ROOT / "infra/docker-compose.yml"),
]


def database_value(service: str, user: str, database: str, sql: str) -> str:
    result = subprocess.run(
        [*COMPOSE, "exec", "-T", service, "psql", "-U", user, "-d", database, "-tAc", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


async def main() -> None:
    base = "http://localhost:" + ENV.get("GATEWAY_PORT", "8000")
    async with httpx.AsyncClient(base_url=base, timeout=35) as client:
        for _ in range(60):
            try:
                response = await client.get("/health")
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(2)
        response = await client.post(
            "/api/auth/login",
            json={
                "username": ENV["DEMO_USERNAME"],
                "password": ENV["DEMO_PASSWORD"],
            },
        )
        response.raise_for_status()
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        airports = await client.get("/api/airports")
        airports.raise_for_status()
        first, second = airports.json()[:2]
        body = {
            "departure_airport_id": first["id"],
            "arrival_airport_id": second["id"],
            "departure_date": "2027-01-15",
            "duration_days": 4,
        }
        response = await client.post("/api/itineraries", json=body)
        assert response.status_code == 201, response.text
        itinerary_id = str(UUID(response.json()["id"]))
        try:
            response = await client.get("/api/itineraries/" + itinerary_id)
            assert response.status_code == 200
            response = await client.put(
                "/api/itineraries/" + itinerary_id, json={**body, "duration_days": 5}
            )
            assert response.status_code == 200
            report = await client.get("/api/reports")
            assert report.status_code == 200
            assert report.json()["total_itineraries"] >= 1
            for _ in range(30):
                count = await asyncio.to_thread(
                    database_value,
                    "notification-db",
                    "notifications",
                    "notifications",
                    f"SELECT count(*) FROM notifications WHERE itinerary_id = '{itinerary_id}'",
                )
                if count == "1":
                    break
                await asyncio.sleep(2)
            assert count == "1", "Notification not persisted within 60 seconds"
            published = await asyncio.to_thread(
                database_value,
                "postgres",
                ENV.get("POSTGRES_USER", "itinerary"),
                ENV.get("POSTGRES_DB", "itineraries"),
                f"SELECT count(*) FROM outbox WHERE payload->>'itinerary_id' = '{itinerary_id}' AND published_at IS NOT NULL",
            )
            assert published == "1", "Outbox event not marked as published"
            print(
                "PASS: login, airports, CRUD, report, confirmed outbox and persisted notification"
            )
        finally:
            response = await client.delete("/api/itineraries/" + itinerary_id)
            assert response.status_code == 204


if __name__ == "__main__":
    asyncio.run(main())
