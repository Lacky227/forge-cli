"""Resolve a ProjectDefinition into a GenerationPlan.

Centralizes framework implications and capability → generation mapping.
Does not touch the filesystem. Raises GenerationError for unsupported or
incompatible combinations before generation begins.

``ProjectDefinition`` = explicit user intent.
``GenerationPlan`` = resolved implementation (ORM, migrations, deps, …).
"""

from __future__ import annotations

from pathlib import Path

from forge.core import catalog
from forge.core.definition import ProjectDefinition
from forge.core.naming import to_package_name
from forge.core.types import ArchitectureStyle, ProjectType
from forge.generator.errors import GenerationError
from forge.generator.plan import GenerationFeatures, GenerationPlan

_SQLALCHEMY_ORM = "sqlalchemy"
_DJANGO_ORM = "django-orm"
_ALEMBIC = "alembic"
_DJANGO_MIGRATIONS = "django"
# Frameworks that use SQLAlchemy + optional Alembic when a database is selected.
_SQLALCHEMY_FRAMEWORKS = frozenset({"fastapi", "flask"})


def resolve_plan(definition: ProjectDefinition) -> GenerationPlan:
    """Validate and resolve ``definition`` into generation instructions."""
    _assert_generatable(definition)
    _assert_capability_coherence(definition)

    package_name = to_package_name(definition.name)
    features = _resolve_features(definition)
    runtime_deps, dev_deps = _resolve_dependencies(definition, features)
    database_url = _database_url_example(definition, package_name)
    entry_file, app_module, run_command, migrate_command, check_command = (
        _commands_and_entry(definition, features, package_name)
    )
    primary_app = _primary_app(definition)

    return GenerationPlan(
        definition=definition,
        package_name=package_name,
        template_subdir=Path(
            definition.language.value,
            definition.framework,
            definition.architecture.value,
        ),
        features=features,
        runtime_dependencies=runtime_deps,
        dev_dependencies=dev_deps,
        database_url_example=database_url,
        app_module=app_module,
        entry_file=entry_file,
        run_command=run_command,
        architecture_label=catalog.ARCHITECTURE_LABELS[definition.architecture],
        framework_label=catalog.FRAMEWORK_LABELS.get(
            definition.framework, definition.framework
        ),
        migrate_command=migrate_command,
        check_command=check_command,
        primary_app=primary_app,
    )


def _assert_generatable(definition: ProjectDefinition) -> None:
    if not catalog.is_generatable(
        definition.language,
        definition.framework,
        definition.project_type,
        definition.architecture,
    ):
        raise GenerationError(
            "Cannot generate this project:\n\n"
            "Generation is not implemented yet for "
            f"{definition.language.value}/{definition.framework}/"
            f"{definition.project_type.value}/"
            f"{definition.architecture.value}.\n"
            "Currently supported: Python FastAPI, Django, or Flask REST API "
            "(simple, modular-monolith, or clean)."
        )


def _assert_capability_coherence(definition: ProjectDefinition) -> None:
    """Validate explicit user choices against framework constraints.

    Framework-implied values are applied in ``_resolve_features``; this step
    only rejects incoherent *explicit* combinations (e.g. Django + SQLAlchemy).
    """
    caps = definition.capabilities
    framework = definition.framework

    if caps.orm == _SQLALCHEMY_ORM and framework == "django":
        raise GenerationError(
            "Cannot generate this project:\n\n"
            "Django with SQLAlchemy is not a supported combination.\n"
            "Use Django ORM (and Django migrations) instead."
        )

    if caps.orm == _DJANGO_ORM and framework in _SQLALCHEMY_FRAMEWORKS:
        raise GenerationError(
            "Cannot generate this project:\n\n"
            f"{catalog.FRAMEWORK_LABELS.get(framework, framework)} with "
            "Django ORM is not a supported combination.\n"
            "Use SQLAlchemy (and Alembic) instead."
        )

    if caps.migrations and framework == "django":
        # Django migrations are implied; an explicit migrations=True is fine.
        # Reject only when an incompatible ORM was also stated.
        if caps.orm == _SQLALCHEMY_ORM:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Django does not use Alembic/SQLAlchemy in Forge. "
                "Use Django ORM and Django migrations."
            )

    if caps.migrations and framework in _SQLALCHEMY_FRAMEWORKS:
        if caps.orm is not None and caps.orm != _SQLALCHEMY_ORM:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Alembic requires SQLAlchemy. "
                f"Selected ORM is {caps.orm!r}."
            )
        if not caps.database:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Migrations require a compatible database/ORM configuration."
            )


def _resolve_features(definition: ProjectDefinition) -> GenerationFeatures:
    caps = definition.capabilities
    engine = caps.database_engine
    orm = _resolve_orm(definition)
    migration_system = _resolve_migration_system(definition, orm)
    rest_framework = (
        definition.framework == "django"
        and definition.project_type is ProjectType.REST_API
    )
    return GenerationFeatures(
        database=caps.database,
        postgresql=caps.database and engine == "postgresql",
        sqlite=caps.database and engine == "sqlite",
        migrations=migration_system is not None,
        docker=caps.docker,
        testing=caps.testing,
        linting=caps.linting,
        orm=orm,
        migration_system=migration_system,
        rest_framework=rest_framework,
    )


def _resolve_orm(definition: ProjectDefinition) -> str | None:
    caps = definition.capabilities
    if not caps.database:
        return None
    if caps.orm is not None:
        return caps.orm
    return catalog.default_orm_for(definition.framework)


def _resolve_migration_system(
    definition: ProjectDefinition,
    orm: str | None,
) -> str | None:
    """Map framework + explicit choices to a concrete migration implementation."""
    caps = definition.capabilities
    if not caps.database or orm is None:
        return None

    if definition.framework == "django":
        if orm != _DJANGO_ORM:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Django migrations require Django ORM. "
                f"Selected ORM is {orm!r}."
            )
        return _DJANGO_MIGRATIONS

    if definition.framework in _SQLALCHEMY_FRAMEWORKS:
        if not caps.migrations:
            return None
        if orm != _SQLALCHEMY_ORM:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Alembic requires SQLAlchemy. "
                f"Selected ORM is {orm!r}."
            )
        return _ALEMBIC

    return None


def _resolve_dependencies(
    definition: ProjectDefinition,
    features: GenerationFeatures,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if definition.framework == "fastapi":
        runtime, dev = _fastapi_dependencies(features)
    elif definition.framework == "django":
        runtime, dev = _django_dependencies(features)
    elif definition.framework == "flask":
        runtime, dev = _flask_dependencies(features)
    else:
        raise GenerationError(
            "Cannot generate this project:\n\n"
            f"No dependency mapping for framework {definition.framework!r}."
        )
    return _dedupe(runtime), _dedupe(dev)


def _dedupe(items: list[str]) -> tuple[str, ...]:
    """Preserve order while removing duplicate dependency declarations."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


def _fastapi_dependencies(
    features: GenerationFeatures,
) -> tuple[list[str], list[str]]:
    runtime: list[str] = [
        "fastapi[standard]>=0.115",
        "pydantic-settings>=2.0",
    ]
    if features.database:
        if features.orm == _SQLALCHEMY_ORM:
            runtime.append("sqlalchemy>=2.0")
        if features.postgresql:
            runtime.append("psycopg[binary]>=3.2")
        if features.migration_system == _ALEMBIC:
            runtime.append("alembic>=1.14")

    dev: list[str] = []
    if features.testing:
        dev.extend(["pytest>=8", "httpx>=0.27"])
    if features.linting:
        dev.append("ruff>=0.8")

    return runtime, dev


def _django_dependencies(
    features: GenerationFeatures,
) -> tuple[list[str], list[str]]:
    runtime: list[str] = [
        "django>=5.0",
        "python-dotenv>=1.0",
    ]
    if features.rest_framework:
        runtime.append("djangorestframework>=3.15")
    if features.postgresql:
        runtime.append("psycopg[binary]>=3.2")

    dev: list[str] = []
    if features.testing:
        dev.extend(["pytest>=8", "pytest-django>=4.8"])
    if features.linting:
        dev.append("ruff>=0.8")

    return runtime, dev


def _flask_dependencies(
    features: GenerationFeatures,
) -> tuple[list[str], list[str]]:
    """Flask is intentionally minimal — persistence deps only when selected."""
    runtime: list[str] = [
        "flask>=3.0",
        "python-dotenv>=1.0",
    ]
    if features.database:
        if features.orm == _SQLALCHEMY_ORM:
            runtime.append("sqlalchemy>=2.0")
        if features.postgresql:
            runtime.append("psycopg[binary]>=3.2")
        if features.migration_system == _ALEMBIC:
            runtime.append("alembic>=1.14")

    dev: list[str] = []
    if features.testing:
        dev.append("pytest>=8")
    if features.linting:
        dev.append("ruff>=0.8")

    return runtime, dev


def _database_url_example(definition: ProjectDefinition, package_name: str) -> str:
    caps = definition.capabilities
    if not caps.database:
        return ""
    if definition.framework == "django":
        if caps.database_engine == "postgresql":
            return (
                "postgres://postgres:postgres@localhost:5432/"
                f"{package_name}"
            )
        if caps.database_engine == "sqlite":
            return "sqlite:///db.sqlite3"
        return ""
    # FastAPI / Flask (SQLAlchemy)
    if caps.database_engine == "postgresql":
        return (
            "postgresql+psycopg://postgres:postgres@localhost:5432/"
            f"{package_name}"
        )
    if caps.database_engine == "sqlite":
        return f"sqlite:///./{package_name}.db"
    return ""


def _commands_and_entry(
    definition: ProjectDefinition,
    features: GenerationFeatures,
    package_name: str,
) -> tuple[str, str, str, str | None, str | None]:
    if definition.framework == "fastapi":
        entry_file = f"src/{package_name}/main.py"
        app_module = f"{package_name}.main:app"
        run_command = f"uv run fastapi dev {entry_file}"
        migrate_command = (
            "uv run alembic upgrade head"
            if features.migration_system == _ALEMBIC
            else None
        )
        return entry_file, app_module, run_command, migrate_command, None

    if definition.framework == "django":
        entry_file = "manage.py"
        app_module = "config.asgi:application"
        run_command = "uv run python manage.py runserver"
        migrate_command = (
            "uv run python manage.py migrate"
            if features.migration_system == _DJANGO_MIGRATIONS
            else None
        )
        check_command = "uv run python manage.py check"
        return entry_file, app_module, run_command, migrate_command, check_command

    if definition.framework == "flask":
        entry_file = f"src/{package_name}/__init__.py"
        app_module = f"{package_name}:create_app"
        run_command = (
            f"uv run flask --app {package_name}:create_app run --debug"
        )
        migrate_command = (
            "uv run alembic upgrade head"
            if features.migration_system == _ALEMBIC
            else None
        )
        return entry_file, app_module, run_command, migrate_command, None

    entry_file = f"src/{package_name}/main.py"
    return entry_file, f"{package_name}.main:app", f"uv run {entry_file}", None, None


def _primary_app(definition: ProjectDefinition) -> str | None:
    if definition.framework != "django":
        return None
    if definition.architecture is ArchitectureStyle.CLEAN:
        # Django models live in the infrastructure persistence package.
        return "infrastructure.persistence"
    if definition.architecture is ArchitectureStyle.MODULAR_MONOLITH:
        return "apps.core"
    return "core"
