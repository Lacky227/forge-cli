"""Tests for independent SQL / NoSQL persistence model."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge.cli.app import app
from forge.core.config import ConfigError, definition_from_config
from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.presets import definition_from_preset, get_preset
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import generate_project, resolve_plan
from tests.cli_testing import invoke_cli, plain_output

runner = CliRunner()


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _fastapi(
    *,
    sql: str | None = None,
    nosql: str | None = None,
    migrations: bool = False,
    docker: bool = False,
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    name: str = "persist-api",
) -> ProjectDefinition:
    return ProjectDefinition(
        name=name,
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="fastapi",
        architecture=architecture,
        capabilities=Capabilities(
            sql_database=sql,
            nosql_database=nosql,
            migrations=migrations and sql is not None,
            docker=docker,
            testing=True,
            linting=True,
        ),
    )


def test_resolve_nosql_mongodb_only() -> None:
    plan = resolve_plan(_fastapi(nosql="mongodb"))
    assert plan.features.database is False
    assert plan.features.mongodb is True
    assert plan.features.nosql is True
    assert plan.features.nosql_client == "pymongo"
    assert plan.features.orm is None
    assert plan.features.migration_system is None
    deps = " ".join(plan.runtime_dependencies)
    assert "pymongo" in deps
    assert "sqlalchemy" not in deps
    assert "redis" not in deps
    assert plan.mongodb_url_example.startswith("mongodb://")


def test_resolve_nosql_redis_only() -> None:
    plan = resolve_plan(_fastapi(nosql="redis"))
    assert plan.features.redis is True
    assert plan.features.nosql_client == "redis"
    deps = " ".join(plan.runtime_dependencies)
    assert "redis>=" in deps
    assert "pymongo" not in deps
    assert "sqlalchemy" not in deps
    assert plan.redis_url_example.startswith("redis://")


def test_resolve_sql_and_mongodb() -> None:
    plan = resolve_plan(
        _fastapi(sql="postgresql", nosql="mongodb", migrations=True)
    )
    assert plan.features.postgresql is True
    assert plan.features.mongodb is True
    assert plan.features.orm == "sqlalchemy"
    assert plan.features.migration_system == "alembic"
    deps = " ".join(plan.runtime_dependencies)
    assert "sqlalchemy" in deps
    assert "psycopg" in deps
    assert "pymongo" in deps
    assert "redis>=" not in deps


def test_resolve_sqlite_and_redis() -> None:
    plan = resolve_plan(_fastapi(sql="sqlite", nosql="redis", migrations=True))
    assert plan.features.sqlite is True
    assert plan.features.redis is True
    deps = " ".join(plan.runtime_dependencies)
    assert "sqlalchemy" in deps
    assert "redis>=" in deps
    assert "psycopg" not in deps
    assert "pymongo" not in deps


def test_plan_summary_shows_sql_and_nosql_sections() -> None:
    plan = resolve_plan(
        _fastapi(sql="postgresql", nosql="redis", migrations=True)
    )
    sections = {section.title: dict(section.rows) for section in plan.summary_sections()}
    assert "SQL" in sections
    assert sections["SQL"]["Database"] == "PostgreSQL"
    assert sections["SQL"]["ORM"] == "SQLAlchemy"
    assert "NoSQL" in sections
    assert sections["NoSQL"]["Database"] == "Redis"
    assert sections["NoSQL"]["Client"] == "redis"
    assert "Persistence" not in sections


def test_plan_summary_none_when_no_persistence() -> None:
    plan = resolve_plan(_fastapi())
    sections = {section.title: dict(section.rows) for section in plan.summary_sections()}
    assert sections["Persistence"]["Database"] == "none"
    assert "SQL" not in sections
    assert "NoSQL" not in sections


def test_yaml_persistence_sql_only(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "sql.yaml",
        """
name: sql-only
type: rest-api
framework: fastapi
architecture: simple
persistence:
  sql: sqlite
migrations: true
""",
    )
    definition = definition_from_config(path)
    assert definition.capabilities.sql_database == "sqlite"
    assert definition.capabilities.nosql_database is None
    plan = resolve_plan(definition)
    assert plan.features.sqlite is True
    assert plan.features.nosql is False


def test_yaml_persistence_nosql_only(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nosql.yaml",
        """
name: mongo-only
type: rest-api
framework: fastapi
architecture: simple
persistence:
  nosql: mongodb
""",
    )
    definition = definition_from_config(path)
    assert definition.capabilities.sql_database is None
    assert definition.capabilities.nosql_database == "mongodb"


def test_yaml_persistence_combined(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "both.yaml",
        """
name: both-api
type: rest-api
framework: flask
architecture: simple
persistence:
  sql: sqlite
  nosql: redis
migrations: true
""",
    )
    definition = definition_from_config(path)
    assert definition.capabilities.sql_database == "sqlite"
    assert definition.capabilities.nosql_database == "redis"


def test_yaml_legacy_database_still_works(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "legacy.yaml",
        """
name: legacy-api
type: rest-api
framework: fastapi
architecture: simple
database: postgresql
migrations: true
""",
    )
    definition = definition_from_config(path)
    assert definition.capabilities.sql_database == "postgresql"
    assert definition.capabilities.database is True
    assert definition.capabilities.database_engine == "postgresql"


def test_yaml_legacy_plus_nosql(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "hybrid.yaml",
        """
name: hybrid-api
type: rest-api
framework: fastapi
architecture: simple
database: postgresql
persistence:
  nosql: redis
migrations: true
""",
    )
    definition = definition_from_config(path)
    assert definition.capabilities.sql_database == "postgresql"
    assert definition.capabilities.nosql_database == "redis"


def test_yaml_conflicting_legacy_and_persistence(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "conflict.yaml",
        """
name: conflict-api
type: rest-api
framework: fastapi
architecture: simple
database: postgresql
persistence:
  sql: sqlite
""",
    )
    with pytest.raises(ConfigError, match="conflicting persistence"):
        definition_from_config(path)


def test_yaml_conflicting_database_null_and_sql(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "conflict2.yaml",
        """
name: conflict-api
type: rest-api
framework: fastapi
architecture: simple
database: null
persistence:
  sql: postgresql
""",
    )
    with pytest.raises(ConfigError, match="conflicting persistence"):
        definition_from_config(path)


def test_generate_fastapi_mongodb(tmp_path: Path) -> None:
    result = generate_project(
        _fastapi(name="fa-mongo", nosql="mongodb", docker=True),
        base_dir=tmp_path,
    )
    root = result.destination
    pkg = root / "src" / "fa_mongo"
    assert (pkg / "mongodb.py").is_file()
    assert not (pkg / "database.py").exists()
    assert not (pkg / "redis_client.py").exists()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "pymongo" in pyproject
    assert "sqlalchemy" not in pyproject
    env = (root / ".env.example").read_text(encoding="utf-8")
    assert "MONGODB_URL=" in env
    assert "DATABASE_URL=" not in env
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "mongodb:" in compose
    assert "image: mongo:7" in compose
    assert "db:" not in compose or "mongodb:" in compose
    # postgres service named db should be absent
    assert "\n  db:\n" not in compose


def test_generate_fastapi_postgres_redis(tmp_path: Path) -> None:
    result = generate_project(
        _fastapi(
            name="fa-pg-redis",
            sql="postgresql",
            nosql="redis",
            migrations=True,
            docker=True,
        ),
        base_dir=tmp_path,
    )
    root = result.destination
    pkg = root / "src" / "fa_pg_redis"
    assert (pkg / "database.py").is_file()
    assert (pkg / "redis_client.py").is_file()
    assert not (pkg / "mongodb.py").exists()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "sqlalchemy" in pyproject
    assert "redis" in pyproject
    assert "pymongo" not in pyproject
    env = (root / ".env.example").read_text(encoding="utf-8")
    assert "DATABASE_URL=" in env
    assert "REDIS_URL=" in env
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "\n  db:\n" in compose
    assert "\n  redis:\n" in compose


def test_generate_flask_sqlite_mongodb(tmp_path: Path) -> None:
    definition = ProjectDefinition(
        name="fl-sql-mongo",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="flask",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities(
            sql_database="sqlite",
            nosql_database="mongodb",
            migrations=True,
            docker=False,
            testing=True,
            linting=True,
        ),
    )
    result = generate_project(definition, base_dir=tmp_path)
    root = result.destination
    pkg = root / "src" / "fl_sql_mongo"
    assert (pkg / "database.py").is_file()
    assert (pkg / "mongodb.py").is_file()
    assert not (pkg / "redis_client.py").exists()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "sqlalchemy" in pyproject
    assert "pymongo" in pyproject


def test_generate_django_postgres_redis(tmp_path: Path) -> None:
    definition = ProjectDefinition(
        name="dj-pg-redis",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="django",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        capabilities=Capabilities(
            sql_database="postgresql",
            nosql_database="redis",
            docker=True,
            testing=True,
            linting=True,
        ),
    )
    result = generate_project(definition, base_dir=tmp_path)
    root = result.destination
    assert (root / "src" / "apps" / "core" / "redis_client.py").is_file()
    assert not (root / "src" / "apps" / "core" / "mongodb.py").exists()
    settings = (root / "src" / "config" / "settings.py").read_text(encoding="utf-8")
    assert "REDIS_URL" in settings
    assert "django.db.backends.postgresql" in settings
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "redis" in pyproject
    assert "sqlalchemy" not in pyproject.lower()
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "\n  db:\n" in compose
    assert "\n  redis:\n" in compose


def test_generate_clean_mongodb_stays_in_infrastructure(tmp_path: Path) -> None:
    result = generate_project(
        _fastapi(
            name="fa-clean-mongo",
            nosql="mongodb",
            architecture=ArchitectureStyle.CLEAN,
        ),
        base_dir=tmp_path,
    )
    pkg = result.destination / "src" / "fa_clean_mongo"
    assert (pkg / "infrastructure" / "mongodb.py").is_file()
    assert not (pkg / "domain" / "mongodb.py").exists()
    domain = (pkg / "domain" / "health.py").read_text(encoding="utf-8")
    assert "pymongo" not in domain.lower()
    assert "mongodb" not in domain.lower()


def test_generate_no_persistence(tmp_path: Path) -> None:
    result = generate_project(_fastapi(name="no-db"), base_dir=tmp_path)
    root = result.destination
    pkg = root / "src" / "no_db"
    assert not (pkg / "database.py").exists()
    assert not (pkg / "mongodb.py").exists()
    assert not (pkg / "redis_client.py").exists()
    assert not (root / ".env.example").exists()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "sqlalchemy" not in pyproject
    assert "pymongo" not in pyproject
    assert "redis" not in pyproject


def test_existing_sql_presets_unchanged() -> None:
    for preset_id, sql in [
        ("fastapi-postgres", "postgresql"),
        ("fastapi-postgres-clean", "postgresql"),
        ("flask-postgres", "postgresql"),
        ("django-postgres", "postgresql"),
    ]:
        preset = get_preset(preset_id)
        assert preset.sql_database == sql
        assert preset.nosql_database is None
        definition = definition_from_preset(preset_id, name=f"preset-{preset_id}")
        plan = resolve_plan(definition)
        assert plan.features.postgresql is True
        assert plan.features.nosql is False


def test_fastapi_mongo_preset() -> None:
    definition = definition_from_preset("fastapi-mongo", name="mongo-preset")
    assert definition.capabilities.nosql_database == "mongodb"
    assert definition.capabilities.sql_database is None
    plan = resolve_plan(definition)
    assert plan.features.mongodb is True
    assert plan.features.docker is True


def test_cli_plan_shows_nosql(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "plan.yaml",
        """
name: plan-demo
type: rest-api
framework: fastapi
architecture: simple
persistence:
  sql: postgresql
  nosql: mongodb
migrations: true
""",
    )
    result = invoke_cli(app, ["plan", "--config", str(path)])
    assert result.exit_code == 0, result.output
    out = plain_output(result)
    assert "SQL" in out
    assert "PostgreSQL" in out
    assert "NoSQL" in out
    assert "MongoDB" in out
    assert "pymongo" in out


def test_django_rejects_nosql_only() -> None:
    with pytest.raises(Exception, match="require an SQL database"):
        ProjectDefinition(
            name="dj-nosql",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="django",
            architecture=ArchitectureStyle.SIMPLE,
            capabilities=Capabilities(nosql_database="mongodb"),
        )
