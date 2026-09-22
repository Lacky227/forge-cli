"""Tests for YAML configuration → ProjectDefinition."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge.cli.app import app
from forge.core.config import ConfigError, definition_from_config, load_forge_config
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import generate_project, resolve_plan
from tests.cli_testing import invoke_cli, plain_output

runner = CliRunner()


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_load_minimal_fastapi_config(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: my-api
type: rest-api
framework: fastapi
architecture: simple
database: false
""",
    )
    definition = definition_from_config(path)
    assert definition.name == "my-api"
    assert definition.language is Language.PYTHON
    assert definition.project_type is ProjectType.REST_API
    assert definition.framework == "fastapi"
    assert definition.architecture is ArchitectureStyle.SIMPLE
    assert definition.capabilities.database is False
    assert definition.capabilities.orm is None
    assert definition.capabilities.testing is True
    assert definition.capabilities.linting is True
    assert definition.capabilities.docker is False


def test_load_full_fastapi_config(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
project:
  name: shop-api
type: rest-api
framework: fastapi
architecture: modular-monolith
database: postgresql
orm: sqlalchemy
migrations: true
testing: true
linting: true
docker: true
""",
    )
    definition = definition_from_config(path)
    assert definition.name == "shop-api"
    assert definition.architecture is ArchitectureStyle.MODULAR_MONOLITH
    assert definition.capabilities.database is True
    assert definition.capabilities.database_engine == "postgresql"
    assert definition.capabilities.orm == "sqlalchemy"
    assert definition.capabilities.migrations is True
    assert definition.capabilities.docker is True
    plan = resolve_plan(definition)
    assert plan.features.orm == "sqlalchemy"
    assert plan.features.migration_system == "alembic"


def test_django_config_omits_implied_fields(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "django.yaml",
        """
name: web
type: rest-api
framework: django
architecture: clean
database: postgresql
testing: true
linting: true
docker: true
""",
    )
    definition = definition_from_config(path)
    assert definition.capabilities.orm is None
    assert definition.capabilities.migrations is False
    plan = resolve_plan(definition)
    assert plan.features.orm == "django-orm"
    assert plan.features.migration_system == "django"
    assert plan.features.rest_framework is True


def test_flask_config_resolves_sqlalchemy(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "flask.yaml",
        """
name: flask-svc
type: rest-api
framework: flask
architecture: simple
database: sqlite
migrations: true
""",
    )
    definition = definition_from_config(path)
    assert definition.capabilities.orm is None
    plan = resolve_plan(definition)
    assert plan.features.orm == "sqlalchemy"
    assert plan.features.migration_system == "alembic"


def test_cli_name_overrides_config_name(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: from-config
type: rest-api
framework: fastapi
architecture: simple
""",
    )
    definition = definition_from_config(path, cli_name="from-cli")
    assert definition.name == "from-cli"


def test_missing_name_errors(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
type: rest-api
framework: fastapi
architecture: simple
""",
    )
    with pytest.raises(ConfigError, match="project name is required"):
        definition_from_config(path)


def test_conflicting_names_error(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: a
project:
  name: b
type: rest-api
framework: fastapi
architecture: simple
""",
    )
    with pytest.raises(ConfigError, match="conflicting project names"):
        load_forge_config(path)


def test_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="configuration file not found"):
        definition_from_config(tmp_path / "missing.yaml")


def test_malformed_yaml(tmp_path: Path) -> None:
    path = _write(tmp_path, "bad.yaml", "framework: [unclosed\n")
    with pytest.raises(ConfigError, match="malformed YAML"):
        load_forge_config(path)


def test_unknown_field_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: x
type: rest-api
framework: fastapi
architecture: simple
rest_framework: true
""",
    )
    with pytest.raises(ConfigError, match="rest_framework"):
        load_forge_config(path)


def test_invalid_enum_value(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: x
type: rest-api
framework: fastapi
architecture: spaceship
""",
    )
    with pytest.raises(ConfigError, match="architecture"):
        load_forge_config(path)


def test_wrong_field_type(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: x
type: rest-api
framework: fastapi
architecture: simple
migrations: yes-please
""",
    )
    with pytest.raises(ConfigError, match="migrations"):
        load_forge_config(path)


def test_database_true_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: x
type: rest-api
framework: fastapi
architecture: simple
database: true
""",
    )
    with pytest.raises(ConfigError, match="engine name"):
        load_forge_config(path)


def test_invalid_django_sqlalchemy_via_config(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: bad
type: rest-api
framework: django
architecture: simple
database: postgresql
orm: sqlalchemy
""",
    )
    with pytest.raises(ConfigError, match="django-orm"):
        definition_from_config(path)


def test_cli_new_with_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _write(
        tmp_path,
        "forge.yaml",
        """
name: isolated-api
type: rest-api
framework: flask
architecture: simple
database: false
docker: false
""",
    )
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "--config", str(config)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "isolated-api").is_dir()
    assert (
        tmp_path / "isolated-api" / "src" / "isolated_api" / "__init__.py"
    ).is_file()
    assert "isolated-api" in result.output


def test_cli_help_mentions_config() -> None:
    result = invoke_cli(app, ["new", "--help"])
    assert result.exit_code == 0
    assert "--config" in plain_output(result)


def test_generate_from_fastapi_config(tmp_path: Path) -> None:
    config = _write(
        tmp_path,
        "fa.yaml",
        """
name: cfg-fastapi
type: rest-api
framework: fastapi
architecture: simple
database: sqlite
migrations: true
docker: false
""",
    )
    definition = definition_from_config(config)
    result = generate_project(definition, base_dir=tmp_path)
    assert (result.destination / "alembic.ini").is_file()
    assert result.plan.features.orm == "sqlalchemy"


def test_generate_from_django_config(tmp_path: Path) -> None:
    config = _write(
        tmp_path,
        "dj.yaml",
        """
name: cfg-django
type: rest-api
framework: django
architecture: simple
database: sqlite
docker: false
""",
    )
    definition = definition_from_config(config)
    result = generate_project(definition, base_dir=tmp_path)
    assert (result.destination / "manage.py").is_file()
    assert result.plan.features.rest_framework is True


def test_generate_from_flask_config(tmp_path: Path) -> None:
    config = _write(
        tmp_path,
        "fl.yaml",
        """
name: cfg-flask
type: rest-api
framework: flask
architecture: modular-monolith
database: postgresql
migrations: true
docker: true
""",
    )
    definition = definition_from_config(config)
    result = generate_project(definition, base_dir=tmp_path)
    assert (result.destination / "docker-compose.yml").is_file()
    assert result.plan.features.migration_system == "alembic"
