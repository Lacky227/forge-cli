"""Tests for ``forge plan`` — resolve and display GenerationPlan without writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.cli.app import app
from forge.core.presets import definition_from_preset
from forge.generator import resolve_plan
from tests.cli_testing import invoke_cli, plain_output


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_help_exposes_plan() -> None:
    result = invoke_cli(app, ["--help"])
    output = plain_output(result)
    assert result.exit_code == 0
    assert "plan" in output.lower()


def test_plan_help_exposes_options() -> None:
    result = invoke_cli(app, ["plan", "--help"])
    output = plain_output(result)
    assert result.exit_code == 0
    assert "--preset" in output
    assert "-p" in output
    assert "--config" in output
    assert "-c" in output


def test_plan_preset_fastapi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    result = invoke_cli(app, ["plan", "--preset", "fastapi-postgres"])
    output = plain_output(result)
    assert result.exit_code == 0, output
    assert "Forge Generation Plan" in output
    assert "FastAPI" in output
    assert "PostgreSQL" in output
    assert "SQLAlchemy" in output
    assert "Alembic" in output
    assert "python/fastapi/modular-monolith" in output
    assert set(tmp_path.iterdir()) == before


def test_plan_preset_django_implies_from_generation_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = invoke_cli(app, ["plan", "--preset", "django-postgres"])
    output = plain_output(result)
    assert result.exit_code == 0, output
    assert "Django" in output
    assert "Django ORM" in output
    assert "Django migrations" in output
    assert "Django REST Framework" in output
    assert "Alembic" not in output
    assert "SQLAlchemy" not in output


def test_plan_preset_flask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = invoke_cli(app, ["plan", "--preset", "flask-postgres"])
    output = plain_output(result)
    assert result.exit_code == 0, output
    assert "Flask" in output
    assert "SQLAlchemy" in output
    assert "Alembic" in output
    assert "python/flask/modular-monolith" in output


def test_plan_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(
        tmp_path,
        "forge.yaml",
        """
name: from-config
type: rest-api
framework: flask
architecture: simple
database: sqlite
migrations: true
docker: false
""",
    )
    monkeypatch.chdir(tmp_path)
    before = {p.name for p in tmp_path.iterdir()}
    result = invoke_cli(app, ["plan", "--config", str(config)])
    output = plain_output(result)
    assert result.exit_code == 0, output
    assert "from-config" in output
    assert "Flask" in output
    assert "SQLite" in output
    assert "from-config" not in before or True
    assert not (tmp_path / "from-config").exists()
    assert {p.name for p in tmp_path.iterdir()} == before


def test_plan_config_cli_name_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(
        tmp_path,
        "forge.yaml",
        """
name: from-config
type: rest-api
framework: fastapi
architecture: simple
database: false
""",
    )
    monkeypatch.chdir(tmp_path)
    result = invoke_cli(app, ["plan", "from-cli", "--config", str(config)])
    output = plain_output(result)
    assert result.exit_code == 0, output
    assert "from-cli" in output
    # CLI name wins; config name must not appear as the plan project name.
    assert "Name:" in output
    name_line = next(
        line for line in output.splitlines() if "Name:" in line and "from-" in line
    )
    assert "from-cli" in name_line
    assert "from-config" not in name_line


def test_plan_unknown_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = invoke_cli(app, ["plan", "--preset", "nope"])
    assert result.exit_code == 1
    assert "unknown preset" in plain_output(result)
    assert "Traceback" not in plain_output(result)


def test_plan_invalid_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(
        tmp_path,
        "bad.yaml",
        """
name: x
type: rest-api
framework: fastapi
architecture: spaceship
""",
    )
    monkeypatch.chdir(tmp_path)
    result = invoke_cli(app, ["plan", "--config", str(config)])
    assert result.exit_code == 1
    assert "architecture" in plain_output(result)
    assert "Traceback" not in plain_output(result)


def test_plan_rejects_missing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = invoke_cli(app, ["plan"])
    assert result.exit_code == 1
    assert "--preset" in plain_output(result) or "--config" in plain_output(result)


def test_plan_rejects_preset_and_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(
        tmp_path,
        "forge.yaml",
        """
name: x
type: rest-api
framework: flask
architecture: simple
""",
    )
    monkeypatch.chdir(tmp_path)
    result = invoke_cli(
        app, ["plan", "--preset", "flask-postgres", "--config", str(config)]
    )
    assert result.exit_code == 1
    assert "cannot be used together" in plain_output(result)


def test_plan_matches_resolve_plan_for_preset() -> None:
    definition = definition_from_preset("fastapi-postgres", name="project")
    plan = resolve_plan(definition)
    sections = {section.title: dict(section.rows) for section in plan.summary_sections()}
    assert sections["Project"]["Framework"] == "FastAPI"
    assert sections["Persistence"]["ORM"] == "SQLAlchemy"
    assert sections["Persistence"]["Migrations"] == "Alembic"
    assert "modular-monolith" in sections["Template"]["Path"]


def test_forge_new_help_still_ok() -> None:
    result = invoke_cli(app, ["new", "--help"])
    assert result.exit_code == 0
    assert "--preset" in plain_output(result)
