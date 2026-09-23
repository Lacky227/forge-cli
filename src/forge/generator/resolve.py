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
from forge.generator.plan import EnvVarSpec, GenerationFeatures, GenerationPlan

_SQLALCHEMY_ORM = "sqlalchemy"
_DJANGO_ORM = "django-orm"
_ALEMBIC = "alembic"
_DJANGO_MIGRATIONS = "django"
# Frameworks that use SQLAlchemy + optional Alembic when SQL is selected.
_SQLALCHEMY_FRAMEWORKS = frozenset({"fastapi", "flask"})


def resolve_plan(definition: ProjectDefinition) -> GenerationPlan:
    """Validate and resolve ``definition`` into generation instructions."""
    _assert_generatable(definition)
    _assert_capability_coherence(definition)

    package_name = to_package_name(definition.name)
    features = _resolve_features(definition)
    runtime_deps, dev_deps = _resolve_dependencies(definition, features)
    database_url = _database_url_example(definition, package_name)
    mongodb_url, mongodb_db = _mongodb_examples(definition, package_name)
    redis_url = _redis_url_example(definition)
    entry_file, app_module, run_command, migrate_command, check_command = (
        _commands_and_entry(definition, features, package_name)
    )
    primary_app = _primary_app(definition)
    environment_variables = _environment_variables(
        definition,
        features,
        package_name=package_name,
        database_url=database_url,
        mongodb_url=mongodb_url,
        mongodb_database=mongodb_db,
        redis_url=redis_url,
    )
    docker_services = _docker_services(features)
    health_path = _health_path(definition)

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
        mongodb_url_example=mongodb_url,
        mongodb_database_example=mongodb_db,
        redis_url_example=redis_url,
        app_module=app_module,
        entry_file=entry_file,
        run_command=run_command,
        architecture_label=catalog.ARCHITECTURE_LABELS[definition.architecture],
        framework_label=catalog.FRAMEWORK_LABELS.get(
            definition.framework, definition.framework
        ),
        environment_variables=environment_variables,
        docker_services=docker_services,
        health_path=health_path,
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

    if caps.migrations and framework == "django" and caps.orm == _SQLALCHEMY_ORM:
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
        if caps.sql_database is None:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Migrations require a compatible SQL database/ORM configuration."
            )


def _resolve_features(definition: ProjectDefinition) -> GenerationFeatures:
    caps = definition.capabilities
    sql = caps.sql_database
    nosql = caps.nosql_database
    orm = _resolve_orm(definition)
    migration_system = _resolve_migration_system(definition, orm)
    nosql_client = catalog.nosql_client_for(nosql) if nosql else None
    rest_framework = (
        definition.framework == "django"
        and definition.project_type is ProjectType.REST_API
    )
    return GenerationFeatures(
        database=sql is not None,
        postgresql=sql == "postgresql",
        sqlite=sql == "sqlite",
        mongodb=nosql == "mongodb",
        redis=nosql == "redis",
        nosql=nosql is not None,
        migrations=migration_system is not None,
        docker=caps.docker,
        testing=caps.testing,
        linting=caps.linting,
        ci_provider=caps.ci,
        orm=orm,
        migration_system=migration_system,
        nosql_client=nosql_client,
        rest_framework=rest_framework,
    )


def _resolve_orm(definition: ProjectDefinition) -> str | None:
    caps = definition.capabilities
    if caps.sql_database is None:
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
    if caps.sql_database is None or orm is None:
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
    _append_nosql_dependencies(runtime, features)
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


def _append_nosql_dependencies(
    runtime: list[str],
    features: GenerationFeatures,
) -> None:
    if features.mongodb:
        runtime.append("pymongo>=4.13")
    if features.redis:
        runtime.append("redis>=5.0")


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
    if caps.sql_database is None:
        return ""
    if definition.framework == "django":
        if caps.sql_database == "postgresql":
            return (
                "postgres://postgres:postgres@localhost:5432/"
                f"{package_name}"
            )
        if caps.sql_database == "sqlite":
            return "sqlite:///db.sqlite3"
        return ""
    # FastAPI / Flask (SQLAlchemy)
    if caps.sql_database == "postgresql":
        return (
            "postgresql+psycopg://postgres:postgres@localhost:5432/"
            f"{package_name}"
        )
    if caps.sql_database == "sqlite":
        return f"sqlite:///./{package_name}.db"
    return ""


def _mongodb_examples(
    definition: ProjectDefinition,
    package_name: str,
) -> tuple[str, str]:
    if definition.capabilities.nosql_database != "mongodb":
        return "", ""
    return "mongodb://localhost:27017", package_name


def _redis_url_example(definition: ProjectDefinition) -> str:
    if definition.capabilities.nosql_database != "redis":
        return ""
    return "redis://localhost:6379/0"


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


def _docker_services(features: GenerationFeatures) -> tuple[str, ...]:
    """Compose dependency service names (not the application container)."""
    if not features.docker:
        return ()
    services: list[str] = []
    if features.postgresql:
        services.append("db")
    if features.mongodb:
        services.append("mongodb")
    if features.redis:
        services.append("redis")
    return tuple(services)


def _health_path(definition: ProjectDefinition) -> str:
    """Liveness path currently generated for this stack (not a future ideal)."""
    framework = definition.framework
    if framework == "django":
        return "/api/health/"
    if framework == "flask":
        return "/api/health"
    if framework == "fastapi":
        if definition.architecture is ArchitectureStyle.CLEAN:
            return "/api/health"
        return "/health"
    return "/health"


def _environment_variables(
    definition: ProjectDefinition,
    features: GenerationFeatures,
    *,
    package_name: str,
    database_url: str,
    mongodb_url: str,
    mongodb_database: str,
    redis_url: str,
) -> tuple[EnvVarSpec, ...]:
    """Env vars that match current generated settings / ``.env.example``."""
    specs: list[EnvVarSpec] = []

    if definition.framework == "django":
        # Django always requires SQL for REST API; .env.example always includes
        # these when the file is emitted.
        specs.append(
            EnvVarSpec(
                name="DJANGO_SECRET_KEY",
                example="dev-insecure-change-me",
                purpose="Django secret key",
            )
        )
        specs.append(
            EnvVarSpec(
                name="DJANGO_DEBUG",
                example="true",
                purpose="Enable Django debug mode",
            )
        )
        if features.postgresql:
            specs.extend(
                [
                    EnvVarSpec(
                        name="POSTGRES_DB",
                        example=package_name,
                        purpose="PostgreSQL database name",
                    ),
                    EnvVarSpec(
                        name="POSTGRES_USER",
                        example="postgres",
                        purpose="PostgreSQL user",
                    ),
                    EnvVarSpec(
                        name="POSTGRES_PASSWORD",
                        example="postgres",
                        purpose="PostgreSQL password",
                    ),
                    EnvVarSpec(
                        name="POSTGRES_HOST",
                        example="localhost",
                        purpose="PostgreSQL host",
                    ),
                    EnvVarSpec(
                        name="POSTGRES_PORT",
                        example="5432",
                        purpose="PostgreSQL port",
                    ),
                ]
            )
    else:
        # FastAPI / Flask — SQLAlchemy URL model.
        if features.database:
            specs.append(
                EnvVarSpec(
                    name="DATABASE_URL",
                    example=database_url,
                    purpose="SQLAlchemy database URL",
                )
            )
        # Compose Postgres credentials (app still uses DATABASE_URL).
        if features.docker and features.postgresql:
            specs.extend(
                [
                    EnvVarSpec(
                        name="POSTGRES_USER",
                        example="postgres",
                        purpose="PostgreSQL user for Docker Compose",
                    ),
                    EnvVarSpec(
                        name="POSTGRES_PASSWORD",
                        example="postgres",
                        purpose="PostgreSQL password for Docker Compose",
                    ),
                    EnvVarSpec(
                        name="POSTGRES_DB",
                        example=package_name,
                        purpose="PostgreSQL database name for Docker Compose",
                    ),
                ]
            )

    if features.mongodb:
        specs.extend(
            [
                EnvVarSpec(
                    name="MONGODB_URL",
                    example=mongodb_url,
                    purpose="MongoDB connection URL",
                ),
                EnvVarSpec(
                    name="MONGODB_DATABASE",
                    example=mongodb_database,
                    purpose="MongoDB database name",
                ),
            ]
        )
    if features.redis:
        specs.append(
            EnvVarSpec(
                name="REDIS_URL",
                example=redis_url,
                purpose="Redis connection URL",
            )
        )

    return tuple(specs)
