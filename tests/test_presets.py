"""Tests for the preset catalog and preset → ProjectDefinition path."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from forge.cli.app import app
from forge.core.presets import (
    PRESETS,
    PresetError,
    definition_from_preset,
    get_preset,
    list_presets,
)
from forge.core.types import ArchitectureStyle
from forge.generator import generate_project, resolve_plan
from tests.cli_testing import invoke_cli, plain_output

runner = CliRunner()


def test_preset_ids_unique() -> None:
    ids = [p.id for p in PRESETS]
    assert len(ids) == len(set(ids))


def test_every_preset_has_description() -> None:
    for preset in list_presets():
        assert preset.id
        assert preset.title.strip()
        assert preset.description.strip()


def test_every_preset_resolves_to_valid_definition() -> None:
    for preset in PRESETS:
        definition = definition_from_preset(preset.id, name=f"proj-{preset.id}")
        assert definition.name == f"proj-{preset.id}"
        assert definition.framework == preset.framework
        assert definition.architecture is preset.architecture
        # Presets must not encode framework-implied ORM on the definition.
        assert definition.capabilities.orm is None


@pytest.mark.parametrize("preset_id", [p.id for p in PRESETS])
def test_preset_resolves_plan(preset_id: str) -> None:
    definition = definition_from_preset(preset_id, name=f"ok-{preset_id}")
    plan = resolve_plan(definition)
    assert plan.definition is definition
    assert plan.framework_label
    assert plan.template_subdir


def test_django_preset_implies_orm_migrations_drf() -> None:
    definition = definition_from_preset("django-postgres", name="dj-preset")
    assert definition.capabilities.orm is None
    assert definition.capabilities.migrations is False
    plan = resolve_plan(definition)
    assert plan.features.orm == "django-orm"
    assert plan.features.migration_system == "django"
    assert plan.features.rest_framework is True


def test_fastapi_preset_implies_sqlalchemy_alembic() -> None:
    definition = definition_from_preset("fastapi-postgres", name="fa-preset")
    assert definition.capabilities.orm is None
    assert definition.capabilities.migrations is True
    plan = resolve_plan(definition)
    assert plan.features.orm == "sqlalchemy"
    assert plan.features.migration_system == "alembic"
    assert definition.architecture is ArchitectureStyle.MODULAR_MONOLITH


def test_fastapi_clean_preset_architecture() -> None:
    definition = definition_from_preset(
        "fastapi-postgres-clean", name="fa-clean"
    )
    assert definition.architecture is ArchitectureStyle.CLEAN
    plan = resolve_plan(definition)
    assert "clean" in plan.template_subdir.as_posix()


def test_flask_preset_implies_sqlalchemy() -> None:
    definition = definition_from_preset("flask-postgres", name="fl-preset")
    assert definition.capabilities.orm is None
    plan = resolve_plan(definition)
    assert plan.features.orm == "sqlalchemy"
    assert plan.features.migration_system == "alembic"


def test_unknown_preset_error() -> None:
    with pytest.raises(PresetError, match="unknown preset") as excinfo:
        get_preset("fastapi-prod")
    message = str(excinfo.value)
    assert "fastapi-postgres" in message
    assert "django-postgres" in message


def test_preset_requires_name() -> None:
    with pytest.raises(PresetError, match="project name is required"):
        definition_from_preset("fastapi-postgres", name=None)
    with pytest.raises(PresetError, match="project name is required"):
        definition_from_preset("fastapi-postgres", name="  ")


def test_cli_preset_generates_without_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with patch("forge.cli.app.run_new_flow") as interactive:
        result = runner.invoke(
            app, ["new", "preset-api", "--preset", "fastapi-postgres"]
        )
    assert result.exit_code == 0, result.output
    interactive.assert_not_called()
    assert (tmp_path / "preset-api").is_dir()
    assert "Preset:" in result.output
    assert "FastAPI + PostgreSQL" in result.output
    assert "Created" in result.output
    assert (
        tmp_path / "preset-api" / "src" / "preset_api" / "api" / "routes"
    ).is_dir()


def test_cli_preset_short_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "short-api", "-p", "flask-postgres"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "short-api").is_dir()


def test_cli_preset_rejects_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "forge.yaml"
    config.write_text(
        "name: x\ntype: rest-api\nframework: flask\narchitecture: simple\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["new", "x", "--preset", "flask-postgres", "--config", str(config)],
    )
    assert result.exit_code == 1
    assert "cannot be used together" in result.output
    assert "Traceback" not in result.output


def test_cli_unknown_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "x", "--preset", "nope"])
    assert result.exit_code == 1
    assert "unknown preset" in result.output
    assert "fastapi-postgres" in result.output
    assert "Traceback" not in result.output


def test_cli_preset_requires_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "--preset", "django-postgres"])
    assert result.exit_code == 1
    assert "project name is required" in result.output


def test_cli_help_mentions_preset() -> None:
    result = invoke_cli(app, ["new", "--help"])
    output = plain_output(result)
    assert result.exit_code == 0
    assert "--preset" in output
    assert "-p" in output


def test_generate_fastapi_preset(tmp_path: Path) -> None:
    definition = definition_from_preset("fastapi-postgres", name="gen-fa")
    result = generate_project(definition, base_dir=tmp_path)
    assert (result.destination / "pyproject.toml").is_file()
    assert (result.destination / "alembic.ini").is_file()
    assert (result.destination / "Dockerfile").is_file()
    assert result.plan.features.orm == "sqlalchemy"


def test_generate_fastapi_clean_preset(tmp_path: Path) -> None:
    definition = definition_from_preset(
        "fastapi-postgres-clean", name="gen-fa-clean"
    )
    result = generate_project(definition, base_dir=tmp_path)
    root = result.destination / "src" / "gen_fa_clean"
    assert (root / "domain").is_dir()
    assert (root / "application").is_dir()
    assert (root / "infrastructure").is_dir()
    assert (root / "presentation").is_dir()


def test_generate_django_preset(tmp_path: Path) -> None:
    definition = definition_from_preset("django-postgres", name="gen-dj")
    result = generate_project(definition, base_dir=tmp_path)
    assert (result.destination / "manage.py").is_file()
    assert result.plan.features.rest_framework is True
    assert result.plan.features.orm == "django-orm"


def test_generate_flask_preset(tmp_path: Path) -> None:
    definition = definition_from_preset("flask-postgres", name="gen-fl")
    result = generate_project(definition, base_dir=tmp_path)
    assert (result.destination / "pyproject.toml").is_file()
    assert result.plan.features.orm == "sqlalchemy"
    assert (result.destination / "docker-compose.yml").is_file()
