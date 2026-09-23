"""Tests for Flask resolution and generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import GenerationError, generate_project, resolve_plan


def _flask(
    *,
    name: str = "demo-flask",
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    database: bool = False,
    engine: str = "sqlite",
    migrations: bool = False,
    docker: bool = False,
    testing: bool = True,
    linting: bool = True,
    orm: str | None = None,
) -> ProjectDefinition:
    """Flask definition with only explicit user choices (no implied ORM)."""
    return ProjectDefinition(
        name=name,
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="flask",
        architecture=architecture,
        capabilities=Capabilities(
            sql_database=engine if database else None,
            orm=orm,
            migrations=migrations and database,
            docker=docker,
            testing=testing,
            linting=linting,
        ),
    )


def test_resolve_flask_no_database() -> None:
    plan = resolve_plan(_flask())
    assert plan.template_subdir.as_posix() == "python/flask/simple"
    assert plan.features.database is False
    assert plan.features.orm is None
    assert plan.features.migration_system is None
    assert plan.features.rest_framework is False
    joined = " ".join(plan.runtime_dependencies)
    assert "flask>=3.0" in joined
    assert "sqlalchemy" not in joined
    assert "alembic" not in joined
    assert "psycopg" not in joined
    assert plan.run_command.startswith("uv run flask --app")
    assert plan.migrate_command is None


def test_resolve_flask_sqlite() -> None:
    plan = resolve_plan(_flask(database=True, engine="sqlite"))
    assert plan.features.sqlite is True
    assert plan.features.orm == "sqlalchemy"
    assert plan.features.migration_system is None
    assert "sqlalchemy>=2.0" in plan.runtime_dependencies
    assert "alembic" not in " ".join(plan.runtime_dependencies)
    assert "psycopg" not in " ".join(plan.runtime_dependencies)
    assert plan.database_url_example.startswith("sqlite:///")


def test_resolve_flask_postgresql() -> None:
    plan = resolve_plan(_flask(database=True, engine="postgresql"))
    assert plan.features.postgresql is True
    assert plan.features.orm == "sqlalchemy"
    assert "psycopg[binary]>=3.2" in plan.runtime_dependencies
    assert "postgresql+psycopg://" in plan.database_url_example


def test_resolve_flask_with_explicit_sqlalchemy() -> None:
    plan = resolve_plan(_flask(database=True, engine="sqlite", orm="sqlalchemy"))
    assert plan.features.orm == "sqlalchemy"


def test_resolve_flask_alembic() -> None:
    plan = resolve_plan(
        _flask(database=True, engine="sqlite", migrations=True)
    )
    assert plan.features.migration_system == "alembic"
    assert plan.features.migrations is True
    assert "alembic>=1.14" in plan.runtime_dependencies
    assert plan.migrate_command == "uv run alembic upgrade head"


def test_resolve_flask_postgres_alembic() -> None:
    plan = resolve_plan(
        _flask(
            database=True,
            engine="postgresql",
            migrations=True,
            docker=True,
        )
    )
    assert plan.features.orm == "sqlalchemy"
    assert plan.features.migration_system == "alembic"
    assert plan.features.postgresql is True
    assert plan.features.docker is True
    deps = plan.runtime_dependencies
    assert "sqlalchemy>=2.0" in deps
    assert "alembic>=1.14" in deps
    assert "psycopg[binary]>=3.2" in deps


def test_reject_flask_with_django_orm() -> None:
    definition = ProjectDefinition.model_construct(
        name="bad",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="flask",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities.model_construct(
            sql_database="postgresql",
            orm="django-orm",
            migrations=True,
            docker=False,
            testing=False,
            linting=False,
        ),
    )
    with pytest.raises(GenerationError, match="Django ORM"):
        resolve_plan(definition)


def test_reject_flask_migrations_without_database() -> None:
    with pytest.raises(Exception, match="migrations require"):
        ProjectDefinition(
            name="bad",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="flask",
            architecture=ArchitectureStyle.SIMPLE,
            capabilities=Capabilities(
                sql_database=None,
                migrations=True,
            ),
        )


def test_flask_dependencies_have_no_duplicates() -> None:
    plan = resolve_plan(
        _flask(database=True, engine="postgresql", migrations=True, docker=True)
    )
    assert len(plan.runtime_dependencies) == len(set(plan.runtime_dependencies))
    assert len(plan.dev_dependencies) == len(set(plan.dev_dependencies))


def test_generate_flask_simple_no_db(tmp_path: Path) -> None:
    result = generate_project(_flask(name="flask-plain"), base_dir=tmp_path)
    root = result.destination
    assert (root / "src" / "flask_plain" / "__init__.py").is_file()
    assert (root / "src" / "flask_plain" / "routes.py").is_file()
    assert not (root / "src" / "flask_plain" / "database.py").exists()
    assert not (root / "alembic.ini").exists()
    assert not (root / "Dockerfile").exists()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "flask" in pyproject
    assert "sqlalchemy" not in pyproject
    routes = (root / "src" / "flask_plain" / "routes.py").read_text(encoding="utf-8")
    assert "/api/health" in routes


def test_generate_flask_simple_sqlite_alembic(tmp_path: Path) -> None:
    result = generate_project(
        _flask(
            name="flask-sqlite",
            database=True,
            engine="sqlite",
            migrations=True,
        ),
        base_dir=tmp_path,
    )
    root = result.destination
    assert (root / "src" / "flask_sqlite" / "database.py").is_file()
    assert (root / "alembic.ini").is_file()
    assert (root / "migrations" / "env.py").is_file()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "sqlalchemy" in pyproject
    assert "alembic" in pyproject
    assert "psycopg" not in pyproject


def test_generate_flask_modular_postgres_alembic(tmp_path: Path) -> None:
    result = generate_project(
        _flask(
            name="flask-mod",
            architecture=ArchitectureStyle.MODULAR_MONOLITH,
            database=True,
            engine="postgresql",
            migrations=True,
            docker=True,
        ),
        base_dir=tmp_path,
    )
    root = result.destination
    assert (root / "src" / "flask_mod" / "api" / "routes" / "health.py").is_file()
    assert (root / "src" / "flask_mod" / "core" / "database.py").is_file()
    assert (root / "src" / "flask_mod" / "models" / "base.py").is_file()
    assert (root / "Dockerfile").is_file()
    assert (root / "docker-compose.yml").is_file()
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "postgres:16-alpine" in compose
    assert "alembic.ini" in (root / "Dockerfile").read_text(encoding="utf-8") or (
        root / "alembic.ini"
    ).is_file()


def test_generate_flask_docker_compose(tmp_path: Path) -> None:
    result = generate_project(
        _flask(
            name="flask-docker",
            database=True,
            engine="postgresql",
            migrations=True,
            docker=True,
        ),
        base_dir=tmp_path,
    )
    compose = (result.destination / "docker-compose.yml").read_text(encoding="utf-8")
    assert "services:" in compose
    assert "db:" in compose
    assert "api:" in compose
