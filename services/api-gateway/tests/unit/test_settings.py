from pathlib import Path

from app.infrastructure.settings import _default_frontend_dir


def test_default_frontend_dir_for_repo_layout():
    path = Path(_default_frontend_dir())
    assert path.name == "frontend"


def test_default_frontend_dir_for_container_layout(monkeypatch):
    class _ResolvedPath:
        parents = (
            Path("/service/app/infrastructure"),
            Path("/service/app"),
            Path("/service"),
            Path("/"),
        )

    monkeypatch.setattr("app.infrastructure.settings.Path.resolve", lambda _: _ResolvedPath())
    assert _default_frontend_dir() == "/frontend"
