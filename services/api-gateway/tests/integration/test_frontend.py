from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from app.infrastructure.settings import Settings
from app.main import create_app
from httpx import ASGITransport, AsyncClient


@pytest.mark.parametrize("custom_directory", [False, True])
async def test_frontend_assets_from_any_working_directory(monkeypatch, tmp_path, custom_directory):
    source = Path(__file__).resolve().parents[4] / "frontend"
    monkeypatch.delenv("FRONTEND_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    if custom_directory:
        for name in ("index.html", "styles.css", "app.js"):
            (tmp_path / name).write_bytes((source / name).read_bytes())
        settings = Settings(frontend_dir=str(tmp_path))
    else:
        settings = Settings()
    app = create_app(AsyncMock(), AsyncMock(), settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        index = await client.get("/")
        assert index.status_code == 200
        assert "/static/styles.css" in index.text
        assert "/static/app.js" in index.text
        for name, types in (
            ("styles.css", {"text/css"}),
            ("app.js", {"text/javascript", "application/javascript"}),
        ):
            response = await client.get("/static/" + name)
            assert response.status_code == 200
            assert response.headers["content-type"].split(";")[0] in types
            assert response.content == (source / name).read_bytes()
            assert response.headers["x-content-type-options"] == "nosniff"
        assert (await client.get("/static/missing.js")).status_code == 404


def test_incomplete_frontend_fails_at_startup(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    with pytest.raises(RuntimeError, match="styles.css, app.js"):
        create_app(AsyncMock(), AsyncMock(), Settings(frontend_dir=str(tmp_path)))
