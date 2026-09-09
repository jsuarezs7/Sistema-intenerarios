"""Exercise independent Alembic upgrade/downgrade/upgrade on disposable SQLite DBs."""

import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for service, key, expected in [
    ("itinerary-service", "DATABASE_URL", {"itineraries", "outbox"}),
    ("notification-function", "NOTIFICATION_DATABASE_URL", {"notifications"}),
]:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "migration.db"
        env = {**os.environ, key: "sqlite+aiosqlite:///" + database.as_posix()}
        for direction, revision in [
            ("upgrade", "head"),
            ("downgrade", "base"),
            ("upgrade", "head"),
        ]:
            subprocess.run(
                [sys.executable, "-m", "alembic", direction, revision],
                cwd=root / "services" / service,
                env=env,
                check=True,
            )
            with closing(sqlite3.connect(database)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                assert expected <= tables if direction == "upgrade" else not expected & tables
        print(f"{service}: upgrade / downgrade / upgrade passed")
