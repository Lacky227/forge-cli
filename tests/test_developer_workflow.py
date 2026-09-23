"""Tests for CI capability, env/docker/health resolution, and plan sections."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from forge.cli.app import app
from forge.cli.flow import _collect_capabilities
from forge.core.config import ConfigError, definition_from_config
from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.presets import PRESETS, definition_from_preset
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import resolve_plan
from tests.cli_testing import invoke_cli, plain_output


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _fastapi(
    *,
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    sql: str | None = "postgresql",
    nosql: str | None = None,
    migrations: bool = True,
    docker: bool = True,
    testing: bool = True,
    linting: bool = True,
    ci: str | None = None,
) -> ProjectDefinition:
    return ProjectDefinition(
        name="demo-api",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="fastapi",
        architecture=architecture,
        capabilities=Capabilities(
            sql_database=sql,
            nosql_database=nosql,
            migrations=migrations and sql is not None,
            docker=docker,
            testing=testing,
            linting=linting,
            ci=ci,
        ),
    )


def _django(
    *,
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    sql: str = "postgresql",
    nosql: str | None = None,
    docker: bool = True,
    ci: str | None = None,
) -> ProjectDefinition:
    return ProjectDefinition(
        name="web",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="django",
        architecture=architecture,
        capabilities=Capabilities(
            sql_database=sql,
            nosql_database=nosql,
            docker=docker,
            testing=True,
            linting=True,
            ci=ci,
        ),
    )


# --- Definition / config -------------------------------------------------


def test_ci_defaults_to_none() -> None:
    caps = Capabilities()
    assert caps.ci is None


def test_ci_github_actions_accepted() -> None:
    caps = Capabilities(ci="github-actions", testing=True)
    assert caps.ci == "github-actions"


def test_ci_unknown_provider_rejected() -> None:
    with pytest.raises(ValidationError, match="ci must be one of"):
        Capabilities(ci="gitlab-ci", testing=True)


def test_ci_requires_testing_or_linting() -> None:
    with pytest.raises(ValidationError, match="ci requires testing or linting"):
        Capabilities(ci="github-actions", testing=False, linting=False)


def test_ci_allowed_with_linting_only() -> None:
    caps = Capabilities(ci="github-actions", testing=False, linting=True)
    assert caps.ci == "github-actions"


def test_legacy_config_without_ci_remains_valid(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: legacy-api
type: rest-api
framework: fastapi
architecture: simple
database: postgresql
migrations: true
testing: true
linting: true
docker: true
""",
    )
    definition = definition_from_config(path)
    assert definition.capabilities.ci is None
    plan = resolve_plan(definition)
    assert plan.features.ci is False
    assert plan.features.ci_provider is None


def test_config_ci_github_actions(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: with-ci
type: rest-api
framework: fastapi
architecture: simple
database: false
testing: true
linting: true
ci: github-actions
""",
    )
    definition = definition_from_config(path)
    assert definition.capabilities.ci == "github-actions"
    plan = resolve_plan(definition)
    assert plan.features.ci is True
    assert plan.features.ci_provider == "github-actions"


def test_config_ci_without_tools_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: bad-ci
type: rest-api
framework: flask
architecture: simple
testing: false
linting: false
ci: github-actions
""",
    )
    with pytest.raises(ConfigError, match="ci requires testing or linting"):
        definition_from_config(path)


def test_config_unknown_ci_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "forge.yaml",
        """
name: bad-ci
type: rest-api
framework: flask
architecture: simple
ci: circleci
""",
    )
    with pytest.raises(ConfigError, match="ci"):
        definition_from_config(path)


# --- Resolver ------------------------------------------------------------


def test_resolve_ci_features() -> None:
    plan = resolve_plan(_fastapi(ci="github-actions"))
    assert plan.features.ci is True
    assert plan.features.ci_provider == "github-actions"


def test_resolve_env_fastapi_postgres_docker() -> None:
    plan = resolve_plan(_fastapi(sql="postgresql", docker=True))
    names = [spec.name for spec in plan.environment_variables]
    assert names == [
        "DATABASE_URL",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ]
    assert "postgresql+psycopg://" in plan.environment_variables[0].example


def test_resolve_env_fastapi_sqlite_no_postgres_compose_vars() -> None:
    plan = resolve_plan(_fastapi(sql="sqlite", docker=True))
    names = [spec.name for spec in plan.environment_variables]
    assert names == ["DATABASE_URL"]
    assert not any(n.startswith("POSTGRES_") for n in names)


def test_resolve_env_fastapi_mongo_only() -> None:
    plan = resolve_plan(
        _fastapi(sql=None, nosql="mongodb", migrations=False, docker=False)
    )
    names = [spec.name for spec in plan.environment_variables]
    assert names == ["MONGODB_URL", "MONGODB_DATABASE"]


def test_resolve_env_fastapi_sql_and_redis() -> None:
    plan = resolve_plan(
        _fastapi(sql="postgresql", nosql="redis", docker=True)
    )
    names = [spec.name for spec in plan.environment_variables]
    assert "DATABASE_URL" in names
    assert "REDIS_URL" in names
    assert "POSTGRES_DB" in names


def test_resolve_env_no_persistence() -> None:
    plan = resolve_plan(
        _fastapi(sql=None, migrations=False, docker=False)
    )
    assert plan.environment_variables == ()


def test_resolve_env_django_postgres() -> None:
    plan = resolve_plan(_django(sql="postgresql"))
    names = [spec.name for spec in plan.environment_variables]
    assert names[:2] == ["DJANGO_SECRET_KEY", "DJANGO_DEBUG"]
    assert "POSTGRES_DB" in names
    assert "POSTGRES_HOST" in names
    assert "DATABASE_URL" not in names


def test_resolve_env_django_sqlite() -> None:
    plan = resolve_plan(_django(sql="sqlite", docker=False))
    names = [spec.name for spec in plan.environment_variables]
    assert names == ["DJANGO_SECRET_KEY", "DJANGO_DEBUG"]


def test_resolve_env_django_with_redis() -> None:
    plan = resolve_plan(_django(sql="sqlite", nosql="redis", docker=False))
    names = [spec.name for spec in plan.environment_variables]
    assert "REDIS_URL" in names
    assert "DJANGO_SECRET_KEY" in names


def test_resolve_docker_services_combined() -> None:
    plan = resolve_plan(
        _fastapi(sql="postgresql", nosql="redis", docker=True)
    )
    assert plan.docker_services == ("db", "redis")


def test_resolve_docker_services_mongodb() -> None:
    plan = resolve_plan(
        _fastapi(sql=None, nosql="mongodb", migrations=False, docker=True)
    )
    assert plan.docker_services == ("mongodb",)


def test_resolve_docker_services_empty_without_docker() -> None:
    plan = resolve_plan(_fastapi(docker=False))
    assert plan.docker_services == ()


def test_resolve_docker_services_app_only() -> None:
    plan = resolve_plan(
        _fastapi(sql=None, migrations=False, docker=True)
    )
    assert plan.features.docker is True
    assert plan.docker_services == ()


def test_resolve_health_paths() -> None:
    assert resolve_plan(_fastapi()).health_path == "/health"
    assert (
        resolve_plan(
            _fastapi(architecture=ArchitectureStyle.MODULAR_MONOLITH)
        ).health_path
        == "/health"
    )
    assert (
        resolve_plan(
            _fastapi(architecture=ArchitectureStyle.CLEAN)
        ).health_path
        == "/health"
    )
    assert (
        resolve_plan(
            ProjectDefinition(
                name="flask-app",
                language=Language.PYTHON,
                project_type=ProjectType.REST_API,
                framework="flask",
                architecture=ArchitectureStyle.SIMPLE,
            )
        ).health_path
        == "/api/health"
    )
    assert resolve_plan(_django()).health_path == "/api/health/"


def test_jinja_context_exposes_new_fields() -> None:
    plan = resolve_plan(_fastapi(ci="github-actions", nosql="redis"))
    ctx = plan.as_jinja_dict()
    assert ctx["ci"] is True
    assert ctx["ci_provider"] == "github-actions"
    assert ctx["health_path"] == "/health"
    assert ctx["docker_services"] == ("db", "redis")
    assert isinstance(ctx["environment_variables"], list)
    assert ctx["environment_variables"][0]["name"] == "DATABASE_URL"


# --- Interactive ---------------------------------------------------------


def test_collect_capabilities_asks_ci_when_testing_enabled() -> None:
    answers = {
        "confirm": {
            "Add a database?": False,
            "Include Docker support?": False,
            "Include testing setup (pytest)?": True,
            "Include Ruff linting?": False,
        },
        "select": {
            "Add CI?": "github-actions",
        },
    }

    def fake_confirm(message: str, default: bool = True) -> bool:
        return answers["confirm"][message]

    def fake_select(message: str, choices: list) -> str:
        return answers["select"][message]

    with (
        patch("forge.cli.flow._confirm", side_effect=fake_confirm),
        patch("forge.cli.flow._select", side_effect=fake_select),
    ):
        caps = _collect_capabilities("fastapi", ProjectType.REST_API)

    assert caps.testing is True
    assert caps.linting is False
    assert caps.ci == "github-actions"


def test_collect_capabilities_skips_ci_when_tools_disabled() -> None:
    def fake_confirm(message: str, default: bool = True) -> bool:
        mapping = {
            "Add a database?": False,
            "Include Docker support?": False,
            "Include testing setup (pytest)?": False,
            "Include Ruff linting?": False,
        }
        return mapping[message]

    def fail_select(message: str, choices: list) -> str:
        raise AssertionError(f"unexpected select: {message}")

    with (
        patch("forge.cli.flow._confirm", side_effect=fake_confirm),
        patch("forge.cli.flow._select", side_effect=fail_select),
    ):
        caps = _collect_capabilities("fastapi", ProjectType.REST_API)

    assert caps.testing is False
    assert caps.linting is False
    assert caps.ci is None


def test_collect_capabilities_ci_no_maps_to_none() -> None:
    def fake_confirm(message: str, default: bool = True) -> bool:
        return message != "Add a database?"

    def fake_select(message: str, choices: list) -> str:
        if message == "Add CI?":
            return "none"
        raise AssertionError(message)

    with (
        patch("forge.cli.flow._confirm", side_effect=fake_confirm),
        patch("forge.cli.flow._select", side_effect=fake_select),
    ):
        caps = _collect_capabilities("flask", ProjectType.REST_API)

    assert caps.ci is None


# --- Plan rendering ------------------------------------------------------


def test_summary_sections_include_ci_env_docker_http() -> None:
    plan = resolve_plan(
        _fastapi(ci="github-actions", sql="postgresql", nosql="redis")
    )
    sections = {
        section.title: dict(section.rows) for section in plan.summary_sections()
    }
    assert sections["Tooling"]["CI"] == "GitHub Actions"
    assert sections["Tooling"]["Docker"] == "yes"
    assert "DATABASE_URL" in sections["Environment"]
    assert sections["Docker"]["Services"] == "db, redis"
    assert sections["HTTP"]["Health"] == "GET /health"


def test_summary_sections_ci_disabled() -> None:
    plan = resolve_plan(_fastapi(ci=None, docker=False, sql=None, migrations=False))
    sections = {
        section.title: dict(section.rows) for section in plan.summary_sections()
    }
    assert sections["Tooling"]["CI"] == "no"
    assert "Docker" not in sections
    assert sections["HTTP"]["Health"] == "GET /health"
    assert "Environment" not in sections


def test_summary_sections_docker_app_only() -> None:
    plan = resolve_plan(_fastapi(sql=None, migrations=False, docker=True))
    sections = {
        section.title: dict(section.rows) for section in plan.summary_sections()
    }
    assert sections["Docker"]["Services"] == "none (app image only)"


def test_plan_cli_shows_new_sections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(
        tmp_path,
        "forge.yaml",
        """
name: planned
type: rest-api
framework: fastapi
architecture: modular-monolith
persistence:
  sql: postgresql
  nosql: redis
migrations: true
testing: true
linting: true
docker: true
ci: github-actions
""",
    )
    monkeypatch.chdir(tmp_path)
    result = invoke_cli(app, ["plan", "--config", str(config)])
    output = plain_output(result)
    assert result.exit_code == 0, output
    assert "GitHub Actions" in output
    assert "DATABASE_URL" in output
    assert "REDIS_URL" in output
    assert "db, redis" in output or ("db" in output and "redis" in output)
    assert "GET /health" in output


def test_plan_cli_django_health_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = invoke_cli(app, ["plan", "--preset", "django-postgres"])
    output = plain_output(result)
    assert result.exit_code == 0, output
    assert "GET /api/health/" in output
    assert "CI:" in output
    assert "no" in output.lower()


# --- Presets -------------------------------------------------------------


@pytest.mark.parametrize("preset_id", [p.id for p in PRESETS])
def test_presets_remain_ci_disabled(preset_id: str) -> None:
    definition = definition_from_preset(preset_id, name=f"p-{preset_id}")
    assert definition.capabilities.ci is None
    plan = resolve_plan(definition)
    assert plan.features.ci is False
    assert plan.features.ci_provider is None
