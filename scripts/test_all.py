"""Run each bounded context in a separate process to isolate its app package."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
failed = []
for service in sorted((root / "services").iterdir()):
    if not (service / "tests").exists():
        continue
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--cov=app", "--cov-report=term-missing", "-q"],
        cwd=service,
        check=False,
    )
    if result.returncode:
        failed.append(service.name)
if failed:
    print("Failed services: " + ", ".join(failed))
sys.exit(bool(failed))
