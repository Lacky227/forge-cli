"""Resolve a ProjectDefinition into a GenerationPlan.

Centralizes framework/capability → generation implications. Does not touch
the filesystem. Raises GenerationError for unsupported or incompatible
combinations before generation begins.
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


def resolve_plan(definition: ProjectDefinition) -> GenerationPlan:
    """Validate and resolve ``definition`` into generation instructions."""
    _assert_generatable(definition)
    _assert_capability_coherence(definition)

    package_name = to_package_name(definition.name)
    features = _resolve_features(definition)
    runtime_deps, dev_deps = _resolve_dependencies(definition, features)
    database_url = _database_url_example(definition, package_name)
    entry_file, app_module, run_command, migrate_command, check_command = (
        _commands_and_entry(definition, package_name)
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
            "Currently supported: Python FastAPI or Django REST API "
            "(simple or modular-monolith)."
        )


def _assert_capability_coherence(definition: ProjectDefinition) -> None:
    caps = definition.capabilities
    framework = definition.framework

    if framework == "django" and caps.orm == _SQLALCHEMY_ORM:
        raise GenerationError(
            "Cannot generate this project:\n\n"
            "Django with SQLAlchemy is not a supported combination.\n"
            "Use Django ORM (and Django migrations) instead."
        )

    if framework == "fastapi" and caps.orm == _DJANGO_ORM:
        raise GenerationError(
            "Cannot generate this project:\n\n"
            "FastAPI with Django ORM is not a supported combination.\n"
            "Use SQLAlchemy (and Alembic) instead."
        )

    if caps.migrations:
        if not caps.database:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Migrations require a compatible database/ORM configuration."
            )
        if framework == "fastapi" and caps.orm != _SQLALCHEMY_ORM:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Alembic requires SQLAlchemy. "
                f"Selected ORM is {caps.orm!r}."
            )
        if framework == "django" and caps.orm != _DJANGO_ORM:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Django migrations require Django ORM. "
                f"Selected ORM is {caps.orm!r}."
            )
        if framework == "django" and caps.orm == _SQLALCHEMY_ORM:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Django does not use Alembic/SQLAlchemy in Forge. "
                "Use Django ORM and Django migrations."
            )


def _resolve_features(definition: ProjectDefinition) -> GenerationFeatures:
    caps = definition.capabilities
    engine = caps.database_engine
    rest_framework = (
        definition.framework == "django"
        and definition.project_type is ProjectType.REST_API
    )
    return GenerationFeatures(
        database=caps.database,
        postgresql=caps.database and engine == "postgresql",
        sqlite=caps.database and engine == "sqlite",
        migrations=caps.migrations,
        docker=caps.docker,
        testing=caps.testing,
        linting=caps.linting,
        rest_framework=rest_framework,
    )


def _resolve_dependencies(
    definition: ProjectDefinition,
    features: GenerationFeatures,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if definition.framework == "fastapi":
        return _fastapi_dependencies(features)
    if definition.framework == "django":
        return _django_dependencies(features)
    raise GenerationError(
        "Cannot generate this project:\n\n"
        f"No dependency mapping for framework {definition.framework!r}."
    )


def _fastapi_dependencies(
    features: GenerationFeatures,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    runtime: list[str] = [
        "fastapi[standard]>=0.115",
        "pydantic-settings>=2.0",
    ]
    if features.database:
        runtime.append("sqlalchemy>=2.0")
        if features.postgresql:
            runtime.append("psycopg[binary]>=3.2")
        if features.migrations:
            runtime.append("alembic>=1.14")

    dev: list[str] = []
    if features.testing:
        dev.extend(["pytest>=8", "httpx>=0.27"])
    if features.linting:
        dev.append("ruff>=0.8")

    return tuple(runtime), tuple(dev)


def _django_dependencies(
    features: GenerationFeatures,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
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

    return tuple(runtime), tuple(dev)


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
            return f"sqlite:///db.sqlite3"
        return ""
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
    package_name: str,
) -> tuple[str, str, str, str | None, str | None]:
    if definition.framework == "fastapi":
        entry_file = f"src/{package_name}/main.py"
        app_module = f"{package_name}.main:app"
        run_command = f"uv run fastapi dev {entry_file}"
        migrate_command = (
            "uv run alembic upgrade head"
            if definition.capabilities.migrations
            else None
        )
        return entry_file, app_module, run_command, migrate_command, None

    if definition.framework == "django":
        entry_file = "manage.py"
        app_module = "config.asgi:application"
        run_command = "uv run python manage.py runserver"
        migrate_command = (
            "uv run python manage.py migrate"
            if definition.capabilities.migrations
            else None
        )
        check_command = "uv run python manage.py check"
        return entry_file, app_module, run_command, migrate_command, check_command

    entry_file = f"src/{package_name}/main.py"
    return entry_file, f"{package_name}.main:app", f"uv run {entry_file}", None, None


def _primary_app(definition: ProjectDefinition) -> str | None:
    if definition.framework != "django":
        return None
    if definition.architecture is ArchitectureStyle.MODULAR_MONOLITH:
        return "apps.core"
    return "core"
