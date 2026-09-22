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
from forge.generator.errors import GenerationError
from forge.generator.plan import GenerationFeatures, GenerationPlan

# Alembic is only wired for SQLAlchemy-backed stacks today.
_ALEMBIC_COMPATIBLE_ORMS = frozenset({"sqlalchemy"})


def resolve_plan(definition: ProjectDefinition) -> GenerationPlan:
    """Validate and resolve ``definition`` into generation instructions."""
    _assert_generatable(definition)
    _assert_capability_coherence(definition)

    package_name = to_package_name(definition.name)
    features = _resolve_features(definition)
    runtime_deps, dev_deps = _resolve_dependencies(definition, features)
    database_url = _database_url_example(definition, package_name)
    entry_file = f"src/{package_name}/main.py"
    app_module = f"{package_name}.main:app"

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
        run_command=_run_command(definition, entry_file),
        architecture_label=catalog.ARCHITECTURE_LABELS[definition.architecture],
        framework_label=catalog.FRAMEWORK_LABELS.get(
            definition.framework, definition.framework
        ),
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
            "Currently supported: Python FastAPI REST API "
            "(simple or modular-monolith)."
        )


def _assert_capability_coherence(definition: ProjectDefinition) -> None:
    caps = definition.capabilities

    if caps.migrations:
        if not caps.database:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Alembic requires a compatible database/ORM configuration."
            )
        if caps.orm not in _ALEMBIC_COMPATIBLE_ORMS:
            raise GenerationError(
                "Cannot generate this project:\n\n"
                "Alembic requires SQLAlchemy. "
                f"Selected ORM is {caps.orm!r}."
            )

    if caps.database and definition.framework == "django" and caps.orm == "sqlalchemy":
        # Defensive: ProjectDefinition normally prevents this; keep resolve strict.
        raise GenerationError(
            "Cannot generate this project:\n\n"
            "Django with SQLAlchemy is not a supported combination."
        )


def _resolve_features(definition: ProjectDefinition) -> GenerationFeatures:
    caps = definition.capabilities
    engine = caps.database_engine
    return GenerationFeatures(
        database=caps.database,
        postgresql=caps.database and engine == "postgresql",
        sqlite=caps.database and engine == "sqlite",
        migrations=caps.migrations,
        docker=caps.docker,
        testing=caps.testing,
        linting=caps.linting,
    )


def _resolve_dependencies(
    definition: ProjectDefinition,
    features: GenerationFeatures,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Map framework + features to package constraints.

    Dependency selection is framework-specific and lives here—not in the CLI
    and not as business logic inside Jinja templates.
    """
    if definition.framework == "fastapi":
        return _fastapi_dependencies(features)

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


def _database_url_example(definition: ProjectDefinition, package_name: str) -> str:
    caps = definition.capabilities
    if not caps.database:
        return ""
    if caps.database_engine == "postgresql":
        return (
            "postgresql+psycopg://postgres:postgres@localhost:5432/"
            f"{package_name}"
        )
    if caps.database_engine == "sqlite":
        return f"sqlite:///./{package_name}.db"
    return ""


def _run_command(definition: ProjectDefinition, entry_file: str) -> str:
    if definition.framework == "fastapi":
        return f"uv run fastapi dev {entry_file}"
    # Placeholder for future frameworks — resolve already rejects unsupported ones.
    return f"uv run {entry_file}"
