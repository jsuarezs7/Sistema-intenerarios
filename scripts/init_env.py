"""Create private local development configuration without printing credentials."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
values = (root / ".env.example").read_text(encoding="utf-8")
for key in [
    "POSTGRES_PASSWORD",
    "NOTIFICATION_POSTGRES_PASSWORD",
    "RABBITMQ_PASSWORD",
    "JWT_SECRET",
    "DEMO_PASSWORD",
]:
    values = values.replace(f"\n{key}=\n", f"\n{key}={secrets.token_hex(24)}\n")
try:
    with target.open("x", encoding="utf-8") as output:
        output.write(values)
    print("Created .env. Read DEMO_USERNAME / DEMO_PASSWORD locally to sign in.")
except FileExistsError:
    print(".env already exists; nothing changed.")
