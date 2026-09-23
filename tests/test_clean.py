"""Tests for Clean Architecture catalog, resolution, and generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.core.catalog import architectures_for, is_generatable
from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import GenerationError, generate_project, resolve_plan


def _fastapi_clean(
    *,
    name: str = "clean-fastapi",
    database: bool = False,
    engine: str = "sqlite",
    migrations: bool = False,
    docker: bool = False,
) -> ProjectDefinition:
    return ProjectDefinition(
        name=name,
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="fastapi",
        architecture=ArchitectureStyle.CLEAN,
        capabilities=Capabilities(
            sql_database=engine if database else None,
            migrations=migrations and database,
            docker=docker,
            testing=True,
            linting=True,
        ),
    )


def _flask_clean(
    *,
    name: str = "clean-flask",
    database: bool = True,
    engine: str = "postgresql",
    migrations: bool = True,
    docker: bool = True,
) -> ProjectDefinition:
    return ProjectDefinition(
        name=name,
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="flask",
        architecture=ArchitectureStyle.CLEAN,
        capabilities=Capabilities(
            sql_database=engine if database else None,
            migrations=migrations and database,
            docker=docker,
            testing=True,
            linting=True,
        ),
    )


def _django_clean(
    *,
    name: str = "clean-django",
    engine: str = "sqlite",
    docker: bool = False,
) -> ProjectDefinition:
    return ProjectDefinition(
        name=name,
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="django",
        architecture=ArchitectureStyle.CLEAN,
        capabilities=Capabilities(
            sql_database=engine,
            docker=docker,
            testing=True,
            linting=True,
        ),
    )


def test_clean_is_offered_for_rest_api() -> None:
    styles = architectures_for(ProjectType.REST_API)
    assert ArchitectureStyle.CLEAN in styles


def test_clean_is_generatable_for_all_web_frameworks() -> None:
    for framework in ("fastapi", "django", "flask"):
        assert is_generatable(
            Language.PYTHON,
            framework,
            ProjectType.REST_API,
            ArchitectureStyle.CLEAN,
        )


def test_resolve_fastapi_clean_no_db() -> None:
    plan = resolve_plan(_fastapi_clean())
    assert plan.template_subdir.as_posix() == "python/fastapi/clean"
    assert plan.features.orm is None
    assert plan.features.migration_system is None
    assert "sqlalchemy" not in " ".join(plan.runtime_dependencies)


def test_resolve_fastapi_clean_sqlite_alembic() -> None:
    plan = resolve_plan(
        _fastapi_clean(database=True, engine="sqlite", migrations=True)
    )
    assert plan.features.orm == "sqlalchemy"
    assert plan.features.migration_system == "alembic"
    assert "alembic>=1.14" in plan.runtime_dependencies


def test_resolve_flask_clean_postgres_alembic() -> None:
    plan = resolve_plan(_flask_clean())
    assert plan.template_subdir.as_posix() == "python/flask/clean"
    assert plan.features.orm == "sqlalchemy"
    assert plan.features.migration_system == "alembic"
    assert plan.features.postgresql is True
    assert "psycopg[binary]>=3.2" in plan.runtime_dependencies


def test_resolve_django_clean_implies_django_stack() -> None:
    plan = resolve_plan(_django_clean())
    assert plan.template_subdir.as_posix() == "python/django/clean"
    assert plan.features.orm == "django-orm"
    assert plan.features.migration_system == "django"
    assert plan.features.rest_framework is True
    assert plan.primary_app == "infrastructure.persistence"
    assert "sqlalchemy" not in " ".join(plan.runtime_dependencies)
    assert "alembic" not in " ".join(plan.runtime_dependencies)
    assert "djangorestframework" in " ".join(plan.runtime_dependencies)


def test_clean_dependencies_deduplicated() -> None:
    plan = resolve_plan(_flask_clean())
    assert len(plan.runtime_dependencies) == len(set(plan.runtime_dependencies))
    assert len(plan.dev_dependencies) == len(set(plan.dev_dependencies))


def test_reject_clean_flask_with_django_orm() -> None:
    definition = ProjectDefinition.model_construct(
        name="bad",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="flask",
        architecture=ArchitectureStyle.CLEAN,
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


def test_generate_fastapi_clean_no_db(tmp_path: Path) -> None:
    result = generate_project(_fastapi_clean(name="fa-clean"), base_dir=tmp_path)
    root = result.destination
    pkg = root / "src" / "fa_clean"
    assert (pkg / "domain" / "health.py").is_file()
    assert (pkg / "application" / "health.py").is_file()
    assert (pkg / "presentation" / "api.py").is_file()
    assert (pkg / "main.py").is_file()
    assert not (pkg / "infrastructure" / "database.py").exists()
    assert not (pkg / "infrastructure" / "persistence").exists()
    assert not (pkg / "application" / "ports.py").exists()
    domain = (pkg / "domain" / "health.py").read_text(encoding="utf-8")
    assert "fastapi" not in domain.lower()
    assert "sqlalchemy" not in domain.lower()


def test_generate_fastapi_clean_sqlite_alembic(tmp_path: Path) -> None:
    result = generate_project(
        _fastapi_clean(
            name="fa-clean-db",
            database=True,
            engine="sqlite",
            migrations=True,
        ),
        base_dir=tmp_path,
    )
    root = result.destination
    pkg = root / "src" / "fa_clean_db"
    assert (pkg / "application" / "ports.py").is_file()
    assert (pkg / "infrastructure" / "database.py").is_file()
    assert (pkg / "infrastructure" / "persistence" / "models.py").is_file()
    assert (root / "alembic.ini").is_file()
    assert (root / "migrations" / "env.py").is_file()


def test_generate_flask_clean_postgres(tmp_path: Path) -> None:
    result = generate_project(_flask_clean(name="fl-clean"), base_dir=tmp_path)
    root = result.destination
    pkg = root / "src" / "fl_clean"
    assert (pkg / "domain" / "health.py").is_file()
    assert (pkg / "presentation" / "api.py").is_file()
    assert (root / "docker-compose.yml").is_file()
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "postgres:16-alpine" in compose


def test_generate_django_clean_sqlite(tmp_path: Path) -> None:
    result = generate_project(_django_clean(name="dj-clean"), base_dir=tmp_path)
    root = result.destination
    assert (root / "src" / "domain" / "health.py").is_file()
    assert (root / "src" / "application" / "health.py").is_file()
    assert (root / "src" / "presentation" / "api" / "views.py").is_file()
    assert (
        root / "src" / "infrastructure" / "persistence" / "models.py"
    ).is_file()
    assert (
        root / "src" / "infrastructure" / "persistence" / "migrations" / "__init__.py"
    ).is_file()
    domain = (root / "src" / "domain" / "health.py").read_text(encoding="utf-8")
    assert "django" not in domain.lower()
    views = (root / "src" / "presentation" / "api" / "views.py").read_text(
        encoding="utf-8"
    )
    assert "get_health_status" in views
    settings = (root / "src" / "config" / "settings.py").read_text(encoding="utf-8")
    assert "infrastructure.persistence" in settings
