"""Supported option catalog and compatibility rules.

Concrete data for adaptive prompting and validation — not a plugin system.
"""

from __future__ import annotations

from forge.core.types import ArchitectureStyle, Language, ProjectType

# Display labels for CLI / summaries. Keys are stable definition values.
PROJECT_TYPE_LABELS: dict[ProjectType, str] = {
    ProjectType.REST_API: "REST API",
    ProjectType.CLI: "CLI Application",
    ProjectType.WORKER: "Worker",
}

LANGUAGE_LABELS: dict[Language, str] = {
    Language.PYTHON: "Python",
}

ARCHITECTURE_LABELS: dict[ArchitectureStyle, str] = {
    ArchitectureStyle.SIMPLE: "Simple",
    ArchitectureStyle.MODULAR_MONOLITH: "Modular Monolith",
    ArchitectureStyle.CLEAN: "Clean Architecture",
}

# framework value → human label
FRAMEWORK_LABELS: dict[str, str] = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "typer": "Typer",
    "click": "Click",
    "celery": "Celery",
    "arq": "ARQ",
    "plain": "Plain Python",
}

DATABASE_ENGINE_LABELS: dict[str, str] = {
    "postgresql": "PostgreSQL",
    "sqlite": "SQLite",
}

# language → project_type → frameworks
FRAMEWORKS_BY_LANGUAGE_AND_TYPE: dict[Language, dict[ProjectType, tuple[str, ...]]] = {
    Language.PYTHON: {
        ProjectType.REST_API: ("fastapi", "django", "flask"),
        ProjectType.CLI: ("typer", "click"),
        ProjectType.WORKER: ("celery", "arq", "plain"),
    },
}

# Architectures offered in the CLI. Clean is reserved until a generator exists.
ARCHITECTURES_BY_TYPE: dict[ProjectType, tuple[ArchitectureStyle, ...]] = {
    ProjectType.REST_API: (
        ArchitectureStyle.SIMPLE,
        ArchitectureStyle.MODULAR_MONOLITH,
    ),
    ProjectType.CLI: (ArchitectureStyle.SIMPLE,),
    ProjectType.WORKER: (
        ArchitectureStyle.SIMPLE,
        ArchitectureStyle.MODULAR_MONOLITH,
    ),
}

# Combinations the generation engine can materialize today.
GENERATABLE: frozenset[tuple[str, str, str]] = frozenset(
    {
        (
            Language.PYTHON.value,
            "fastapi",
            ProjectType.REST_API.value,
        ),
        (
            Language.PYTHON.value,
            "django",
            ProjectType.REST_API.value,
        ),
        (
            Language.PYTHON.value,
            "flask",
            ProjectType.REST_API.value,
        ),
    }
)

GENERATABLE_ARCHITECTURES: frozenset[ArchitectureStyle] = frozenset(
    {
        ArchitectureStyle.SIMPLE,
        ArchitectureStyle.MODULAR_MONOLITH,
    }
)

DATABASE_CAPABLE_FRAMEWORKS: frozenset[str] = frozenset(
    {"fastapi", "django", "flask", "celery"}
)

DATABASE_ENGINES: tuple[str, ...] = ("postgresql", "sqlite")

ORM_BY_FRAMEWORK: dict[str, str] = {
    "fastapi": "sqlalchemy",
    "flask": "sqlalchemy",
    "django": "django-orm",
    "celery": "sqlalchemy",
}


def frameworks_for(language: Language, project_type: ProjectType) -> tuple[str, ...]:
    by_type = FRAMEWORKS_BY_LANGUAGE_AND_TYPE.get(language, {})
    return by_type.get(project_type, ())


def architectures_for(project_type: ProjectType) -> tuple[ArchitectureStyle, ...]:
    return ARCHITECTURES_BY_TYPE.get(project_type, (ArchitectureStyle.SIMPLE,))


def is_framework_compatible(
    language: Language, project_type: ProjectType, framework: str
) -> bool:
    return framework in frameworks_for(language, project_type)


def supports_database(framework: str) -> bool:
    return framework in DATABASE_CAPABLE_FRAMEWORKS


def default_orm_for(framework: str) -> str | None:
    return ORM_BY_FRAMEWORK.get(framework)


def is_generatable(
    language: Language,
    framework: str,
    project_type: ProjectType,
    architecture: ArchitectureStyle,
) -> bool:
    key = (language.value, framework, project_type.value)
    return key in GENERATABLE and architecture in GENERATABLE_ARCHITECTURES
