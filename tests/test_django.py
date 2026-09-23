"""Tests for Django resolution and generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import GenerationError, generate_project, resolve_plan


def _django(
    *,
    name: str = "demo-django",
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    engine: str = "sqlite",
    docker: bool = False,
    testing: bool = True,
    linting: bool = True,
) -> ProjectDefinition:
    """Django REST API definition with only explicit user choices.

    ORM, migrations, and DRF are framework-implied and resolved by
    ``resolve_plan`` — they are intentionally absent from Capabilities.
    """
    return ProjectDefinition(
        name=name,
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="django",
        architecture=architecture,
        capabilities=Capabilities(
            sql_database=engine,
            docker=docker,
            testing=testing,
            linting=linting,
        ),
    )


def test_django_definition_has_no_implied_implementation_fields() -> None:
    definition = _django()
    assert definition.capabilities.orm is None
    assert definition.capabilities.migrations is False
    assert definition.capabilities.database is True
    assert definition.capabilities.database_engine == "sqlite"


def test_resolve_django_rest_implies_orm_migrations_drf() -> None:
    plan = resolve_plan(_django())
    assert plan.features.orm == "django-orm"
    assert plan.features.migration_system == "django"
    assert plan.features.migrations is True
    assert plan.features.rest_framework is True
    assert plan.template_subdir.as_posix() == "python/django/simple"
    assert plan.features.sqlite is True
    assert plan.primary_app == "core"
    assert "django>=5.0" in plan.runtime_dependencies
    assert "djangorestframework>=3.15" in plan.runtime_dependencies
    assert "sqlalchemy" not in " ".join(plan.runtime_dependencies)
    assert "alembic" not in " ".join(plan.runtime_dependencies)
    assert plan.migrate_command == "uv run python manage.py migrate"
    assert plan.check_command == "uv run python manage.py check"
    assert plan.run_command == "uv run python manage.py runserver"


def test_resolve_django_postgres_adds_psycopg() -> None:
    plan = resolve_plan(_django(engine="postgresql", docker=True))
    assert plan.features.postgresql is True
    assert "psycopg[binary]>=3.2" in plan.runtime_dependencies
    assert plan.features.docker is True


def test_resolve_django_modular_app_path() -> None:
    plan = resolve_plan(
        _django(architecture=ArchitectureStyle.MODULAR_MONOLITH)
    )
    assert plan.template_subdir.as_posix() == "python/django/modular-monolith"
    assert plan.primary_app == "apps.core"


def test_reject_django_with_sqlalchemy() -> None:
    definition = ProjectDefinition.model_construct(
        name="bad",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="django",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities.model_construct(
            sql_database="postgresql",
            orm="sqlalchemy",
            migrations=True,
            docker=False,
            testing=False,
            linting=False,
        ),
    )
    with pytest.raises(GenerationError, match="SQLAlchemy"):
        resolve_plan(definition)


def test_reject_fastapi_with_django_orm() -> None:
    definition = ProjectDefinition.model_construct(
        name="bad",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="fastapi",
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


def test_django_dependencies_have_no_duplicates() -> None:
    plan = resolve_plan(_django(engine="postgresql", docker=True))
    assert len(plan.runtime_dependencies) == len(set(plan.runtime_dependencies))
    assert len(plan.dev_dependencies) == len(set(plan.dev_dependencies))


def test_generate_django_simple(tmp_path: Path) -> None:
    result = generate_project(_django(), base_dir=tmp_path)
    root = result.destination
    assert (root / "manage.py").is_file()
    assert (root / "src" / "config" / "settings.py").is_file()
    assert (root / "src" / "core" / "views.py").is_file()
    assert (root / "src" / "core" / "migrations" / "__init__.py").is_file()
    assert not (root / "src" / "apps").exists()
    assert not (root / "alembic.ini").exists()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "django" in pyproject
    assert "djangorestframework" in pyproject
    assert "sqlalchemy" not in pyproject


def test_generate_django_modular(tmp_path: Path) -> None:
    result = generate_project(
        _django(name="mod-django", architecture=ArchitectureStyle.MODULAR_MONOLITH),
        base_dir=tmp_path,
    )
    root = result.destination
    assert (root / "src" / "apps" / "core" / "views.py").is_file()
    assert not (root / "src" / "core").exists()
    settings = (root / "src" / "config" / "settings.py").read_text(encoding="utf-8")
    assert '"apps.core"' in settings


def test_django_invalid_fails_before_fs(tmp_path: Path) -> None:
    definition = ProjectDefinition.model_construct(
        name="future-app",
        language=Language.PYTHON,
        project_type=ProjectType.WORKER,
        framework="django",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities(testing=True, linting=False),
    )
    with pytest.raises(GenerationError, match="Cannot generate"):
        generate_project(definition, base_dir=tmp_path)
    assert not (tmp_path / "future-app").exists()
