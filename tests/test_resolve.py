"""Tests for ProjectDefinition → GenerationPlan resolution."""

from __future__ import annotations

import pytest

from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import GenerationError, resolve_plan


def _fastapi(
    *,
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    database: bool = True,
    engine: str = "postgresql",
    migrations: bool = True,
    docker: bool = True,
    testing: bool = True,
    linting: bool = True,
    orm: str | None = None,
) -> ProjectDefinition:
    """Build a FastAPI definition with only explicit user choices by default."""
    return ProjectDefinition(
        name="demo-api",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="fastapi",
        architecture=architecture,
        capabilities=Capabilities(
            database=database,
            database_engine=engine if database else None,
            orm=orm,
            migrations=migrations and database,
            docker=docker,
            testing=testing,
            linting=linting,
        ),
    )


def test_resolve_fastapi_postgres_stack() -> None:
    plan = resolve_plan(_fastapi())
    assert plan.package_name == "demo_api"
    assert plan.template_subdir.as_posix() == "python/fastapi/simple"
    assert plan.features.database is True
    assert plan.features.postgresql is True
    assert plan.features.migrations is True
    assert plan.features.orm == "sqlalchemy"
    assert plan.features.migration_system == "alembic"
    assert "fastapi[standard]>=0.115" in plan.runtime_dependencies
    assert "sqlalchemy>=2.0" in plan.runtime_dependencies
    assert "psycopg[binary]>=3.2" in plan.runtime_dependencies
    assert "alembic>=1.14" in plan.runtime_dependencies
    assert "pytest>=8" in plan.dev_dependencies
    assert "ruff>=0.8" in plan.dev_dependencies
    assert plan.run_command.startswith("uv run fastapi dev")
    assert "postgresql+psycopg://" in plan.database_url_example


def test_resolve_sqlite_has_no_psycopg() -> None:
    plan = resolve_plan(_fastapi(engine="sqlite"))
    assert plan.features.sqlite is True
    assert plan.features.postgresql is False
    assert "psycopg" not in " ".join(plan.runtime_dependencies)
    assert plan.database_url_example.startswith("sqlite:///")


def test_resolve_no_database_omits_db_deps() -> None:
    plan = resolve_plan(_fastapi(database=False, migrations=False, docker=False))
    assert plan.features.database is False
    assert plan.features.orm is None
    assert plan.features.migration_system is None
    joined = " ".join(plan.runtime_dependencies)
    assert "sqlalchemy" not in joined
    assert "alembic" not in joined
    assert plan.features.env_example is False


def test_resolve_modular_template_path() -> None:
    plan = resolve_plan(
        _fastapi(architecture=ArchitectureStyle.MODULAR_MONOLITH)
    )
    assert plan.template_subdir.as_posix() == "python/fastapi/modular-monolith"


def test_resolve_rejects_unsupported_framework() -> None:
    definition = ProjectDefinition(
        name="flask-app",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="flask",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities(testing=True, linting=False),
    )
    with pytest.raises(GenerationError, match="Cannot generate this project"):
        resolve_plan(definition)


def test_resolve_rejects_migrations_without_sqlalchemy_orm() -> None:
    definition = ProjectDefinition.model_construct(
        name="broken",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="fastapi",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities.model_construct(
            database=True,
            database_engine="postgresql",
            orm="django-orm",
            migrations=True,
            docker=False,
            testing=False,
            linting=False,
        ),
    )
    with pytest.raises(GenerationError, match="Django ORM"):
        resolve_plan(definition)


def test_fastapi_definition_omits_implied_orm() -> None:
    """ProjectDefinition stores Alembic choice, not a required ORM field."""
    definition = _fastapi()
    assert definition.capabilities.orm is None
    assert definition.capabilities.migrations is True
    plan = resolve_plan(definition)
    assert plan.features.orm == "sqlalchemy"
    assert plan.features.migration_system == "alembic"


def test_dependencies_have_no_duplicates() -> None:
    plan = resolve_plan(_fastapi())
    assert len(plan.runtime_dependencies) == len(set(plan.runtime_dependencies))
    assert len(plan.dev_dependencies) == len(set(plan.dev_dependencies))
